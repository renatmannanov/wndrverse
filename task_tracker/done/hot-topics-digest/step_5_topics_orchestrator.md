# Шаг 5: Оркестратор build_topics + фильтр флуда + LLM-название

> Зависит от: шаг 1 (store query), шаг 2 (cluster_embeddings), шаг 3 (hotness)
> Статус: [ ] pending

## Задача

Новый модуль `core/brain/topics.py` — мозг фичи. Возвращает СТРУКТУРУ
(`list[TopicCluster]`), НЕ текст. Это главный шаг — здесь живёт КАЧЕСТВО кластеров
(3 слоя фильтрации).

```python
def build_topics(
    fragments: list[dict],
    *,
    min_chars: int = 80,        # слой 1: вход-фильтр коротких/флуда
    min_cluster_size: int = 3,  # слой 2: HDBSCAN — тема ≥ N сообщений
    min_authors: int = 2,       # слой 3: тема — это ≥2 человек, не монолог
    min_probability: float = 0.05,  # слой 3: дропнуть рыхло привязанные точки
    limit: int | None = None,   # топ-N тем; None = все прошедшие фильтры
) -> list[dict]:
    """Сообщения одного топика → ранжированные горячие темы.

    Возвращает [{name, msgs, anchor_channel_id, anchor_external_id}, ...]
    отсортированные по убыванию горячести (hotness.score). PII: в OpenAI уходят
    только тексты, имена/sender_id остаются здесь.
    """
```

Пайплайн внутри (порядок строгий):

1. **Слой 1 — отсев мусора ДО кластеризации.** Из `fragments` выкинуть:
   - `char_length(text) < min_chars`;
   - низкоинформативные: `len(set(слова)) < 3` ИЛИ текст состоит почти из эмодзи/
     пунктуации (эвристика: доля буквенно-цифровых символов < 0.3).
   Вынести в `_is_substantive(text) -> bool`. Если после фильтра < min_cluster_size
   фрагментов → вернуть `[]` (нечего кластеризовать).

2. **Кластеризация.** `vectors = [f['embedding'] for f in kept]` (порядок строго
   как в `kept`, чтобы `labels[i]`/`probs[i]` соответствовали `kept[i]`);
   `labels, probs = cluster_embeddings(vectors, min_cluster_size=min_cluster_size)`.
   Сгруппировать kept по label, **пропуская label == -1 (noise)** И точки с
   `probs[i] < min_probability` (слой 3 — рыхлые отсекаются ЗДЕСЬ, ДО сбора
   members, чтобы они НЕ попали в cluster_stats и не завысили msgs/likes).

3. **Сбор кластеров.** Для каждого кластера (members = уже отфильтрованные по
   probability точки этого label):
   - `stats = hotness.cluster_stats(members)` — считается на УЖЕ очищенных members;
   - **слой 3 фильтр авторов**: `if stats['authors'] < min_authors: skip`;
   - `anchor` = сообщение кластера с МИНИМАЛЬНЫМ created_at —
     `anchor = min(members, key=lambda m: m['created_at'])`. НЕ полагаться на
     позицию `members[0]`: группировка по label могла не сохранить порядок входа.
     Запомнить `anchor_channel_id=anchor['channel_id']`,
     `anchor_external_id=anchor['external_id']`.

4. **Ранжирование.** `maxes` = max msgs/likes/authors по всем собранным кластерам;
   `score(stats, maxes)` каждому; сортировка по убыванию; `limit` если задан.

5. **LLM-название** (только после ранга, только для финальных кластеров — экономим
   токены). Для каждого кластера: взять до 5 репрезентативных СТРОК ТЕКСТА — строго
   `m['text']`, а НЕ объект фрагмента (как в `clustering.generate_cluster_names`:
   каждый step-й, до 5). Собрать `sample_texts = "\n---\n".join(f['text'] for f in
   samples)` — в строку попадает ТОЛЬКО текст. Промпт `topic_label.md` → короткое
   русское название. Темп 0.3, max_tokens 30.
   ⚠️ PII (правило проекта): в промпт уходит ИСКЛЮЧИТЕЛЬНО `f['text']`. НИКОГДА не
   подставлять `f` целиком, `sender_id`, `author_name`, `username`, `external_id` —
   ничего, кроме текста сообщения.

ВАЖНО (правило #1): все пороги — фиксированные дефолты в сигнатуре. CLI (шаг 6)
их прокидывает, но НЕ выдумывает альтернативных стратегий. Один путь.

ВАЖНО (правило #2): на этом шаге LLM-название можно временно заглушить как
`name = f"тема {i+1}"` (тот же тип-результат — str), чтобы прогнать пайплайн без
OpenAI-спенда при отладке. Финальная версия зовёт `topic_label.md`. API не меняется.

## Промпт `core/prompts/topic_label.md`

Новый файл (НЕ трогать `cluster_name.md`):
```
Дай короткое название темы (2-5 слов, на русском) для группы сообщений из чата
сообщества. Название должно цепляюще и точно отражать, О ЧЁМ говорили. Без
кавычек, без точки в конце. Верни ТОЛЬКО название.

Сообщения:
{sample_texts}
```

## Тесты

- `tests/test_topics_build.py` (без БД, без LLM — заглушить название):
  - `_is_substantive`: «+»→False, «ахаха»→False (мало уникальных слов),
    длинный осмысленный текст→True, строка из эмодзи→False.
  - `build_topics` на синтетике: 2 облака векторов по 5, у каждого 3+ автора,
    осмысленные тексты, лайки разные → 2 темы, отсортированы по горячести (то,
    что с большим msgs+likes+authors — первое).
  - кластер с 1 автором отсекается (min_authors=2).
- Что может сломаться: ничего существующего (новый модуль).

## Команды для верификации

```bash
python -m pytest tests/test_topics_build.py -q
# End-to-end на реальных данных (тратит OpenAI на названия — мало, ~N*30 токенов)
python -c "
from dotenv import load_dotenv; load_dotenv()
from core.store.fragments_db import get_embedded_fragments_for_period
from core.brain.topics import build_topics
from datetime import datetime
frags = get_embedded_fragments_for_period('boltalka', datetime(2026,5,1), datetime(2026,6,1))
topics = build_topics(frags, limit=10)
for t in topics:
    print(t['msgs'], '|', t['name'], '|', t['anchor_external_id'])
print('total topics:', len(topics))
"
```

## Критерии готовности

- [ ] Файл `core/prompts/topic_label.md` создан (см. секцию «Промпт» выше).
- [ ] `_is_substantive` режет «+»/«ахаха»/эмодзи-строки, пропускает осмысленный текст.
- [ ] `build_topics` возвращает list[dict] с ключами
      name/msgs/anchor_channel_id/anchor_external_id, отсортирован по горячести.
- [ ] Кластеры < min_authors и noise (-1) не попадают в результат.
- [ ] Рыхлые точки (probs < min_probability) отсекаются ДО cluster_stats (msgs/likes
      считаются только по очищенным members).
- [ ] anchor = сообщение с минимальным created_at (через min(), не members[0]).
- [ ] На boltalka за май даёт непустой осмысленный список тем (визуально вменяемо).
- [ ] `python -m pytest tests/test_topics_build.py -q` зелёный.
- [ ] PII: в промпт topic_label идёт только f['text'] (grep по коду topics.py — в
      строке промпта нет sender_id/author_name/username/external_id).
