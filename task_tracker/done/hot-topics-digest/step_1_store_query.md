# Шаг 1: Запрос «embeddings за период+топик»

> Зависит от: нет
> Статус: [ ] pending

## Задача

В `core/store/fragments_db.py` добавить НОВУЮ функцию
`get_embedded_fragments_for_period(topic, since, until, min_chars)`.
НЕ менять `get_all_embedded_fragments` и `get_fragments_for_digest`.

Функция = срез для кластеризации. Возвращает только фрагменты с embedding
(`embedding IS NOT NULL`), не дубликаты, заданного топика и периода, и отдаёт
ВСЕ поля, нужные дальше по пайплайну:

```python
def get_embedded_fragments_for_period(
    topic: str,
    since: datetime | None = None,
    until: datetime | None = None,
    min_chars: int = 1,        # вход-фильтр флуда живёт в brain.topics, не здесь
) -> list[dict]:
    """Embedded fragments of ONE topic in a period, for hot-topic clustering.

    Filters: topic == topic, created_at in [since, until) (until EXCLUSIVE),
    embedding IS NOT NULL, is_duplicate IS NOT TRUE, char_length >= min_chars.
    Sorted by created_at (so the FIRST message of a cluster = the anchor).

    Returns [{id, text, created_at(ISO str), sender_id, embedding(list[float]),
              channel_id, external_id, reactions(list|None), tags}, ...].
    reactions = metadata->'reactions' (JSONB → python list). PII (sender_id) stays
    local; only `text` is ever sent to OpenAI downstream.
    """
```

Детали:
- Требует pgvector (как `get_all_embedded_fragments`) — тот же guard
  `if not _pgvector_available(): return []` + warning.
- `embedding` вернуть как `list(r.embedding)` (как в `get_all_embedded_fragments`).
- `reactions`: ВНИМАНИЕ — отдельной колонки `reactions` в модели `Fragment` НЕТ,
  она лежит ВНУТРИ JSONB-поля `metadata_`. Доступ — `Fragment.metadata_['reactions']`
  (НЕ `Fragment.reactions`, НЕ `r.reactions` без алиаса). Нужен сам JSON-массив, а
  НЕ `.astext` (в отличие от `username` в `get_fragments_for_digest`). Выбрать с
  алиасом: `.label('reactions')`. SQLAlchemy для JSONB-массива отдаёт python list
  напрямую — но это НАДО ПРОВЕРИТЬ командой ниже: если придёт str (JSON-текст),
  обернуть `json.loads(r.reactions) if isinstance(r.reactions, str) else r.reactions`.
  None оставить None. Итог в dict: `'reactions': <list[{count,emoji}] | None>`.
- `external_id` нужен для msg_id (парсится в рендере, шаг 4).
- `created_at` → ISO string (как все остальные query-функции в этом файле).
- Сортировка `order_by(Fragment.created_at)` — обязательна (якорь = первое).

## Тесты

- Ручная проверка через python -c (см. ниже). Юнит-тест необязателен — это
  тонкий SQL-запрос, проверяется командой.
- Что может сломаться: НИЧЕГО существующего (новая функция, старые не тронуты).

## Команды для верификации

```bash
# Возвращает непустой список с нужными полями
python -c "
from dotenv import load_dotenv; load_dotenv()
from core.store.fragments_db import get_embedded_fragments_for_period
from datetime import datetime
rows = get_embedded_fragments_for_period('boltalka', datetime(2026,5,1), datetime(2026,6,1))
print('rows:', len(rows))
r = rows[0]
print('keys:', sorted(r.keys()))
print('has embedding:', isinstance(r['embedding'], list), 'dim', len(r['embedding']))
print('channel_id:', r['channel_id'])
print('external_id:', r['external_id'])
print('reactions sample:', [x for x in rows if x['reactions']][:1])
"
# until=None работает (открытая верхняя граница — весь период от since до сейчас)
python -c "
from dotenv import load_dotenv; load_dotenv()
from core.store.fragments_db import get_embedded_fragments_for_period
from datetime import datetime
rows = get_embedded_fragments_for_period('boltalka', datetime(2026,5,1), None)
print('until=None rows:', len(rows))
"
# Старые функции не сломаны
python -c "from core.store.fragments_db import get_all_embedded_fragments, get_fragments_for_digest; print('imports ok')"
```

## Критерии готовности

- [ ] Функция возвращает >0 строк для boltalka за май 2026.
- [ ] Каждая строка содержит: id, text, created_at, sender_id, embedding (list,
      dim 1536), channel_id, external_id, reactions, tags.
- [ ] reactions у части строк — список `[{count, emoji}]`, у части None — без краша.
- [ ] Строки отсортированы по created_at возрастанию.
- [ ] `until=None` не падает и отдаёт строки (открытая верхняя граница).
- [ ] `get_all_embedded_fragments` / `get_fragments_for_digest` импортируются.
