# Шаг 2: модуль chains.py — сборка reply-цепочек в документы

> Зависит от: нет (использует поля шага 1, но пишется и тестируется на
> синтетических dict'ах — реальная склейка проверяется в шаге 4)
> Статус: [x] done (2026-06-10; серийная склейка переделана в шаге 4 на
> пер-автора смежность — см. progress.md)

## Задача

Новый модуль `core/brain/chains.py` — ЧИСТЫЙ (без DB/LLM/Telegram, как
hotness.py). Одна публичная функция:

```python
SERIES_GAP_S = 300  # серия: тот же автор, разрыв ≤ 5 мин (части лонгридов
                    # публикуются подряд без reply; калибровано на кейсе
                    # 14067/14069/14070, см. PLAN.md «Факты»)

def build_chains(
    fragments: list[dict],
    *,
    min_chars: int = 80,           # те же значения, что в build_topics —
    series_gap_s: int = SERIES_GAP_S,
) -> list[dict]:
    """Сообщения периода → документы-треды для кластеризации.

    Объединение (union-find по индексам fragments):
      1. reply-связь: fragment.reply_to_msg_id == другой fragment.msg_id
         (строковое сравнение; родитель вне выборки → связь игнорируется,
         сообщение остаётся корнем своей компоненты).
      2. серийная связь: соседние ПО ВРЕМЕНИ сообщения одного sender_id
         (sender_id is not None) с разрывом created_at ≤ series_gap_s секунд.
         Сортировка по created_at, проверяются только соседние пары — O(n).

    Каждая компонента → документ:
      messages    = члены компоненты, sorted by created_at
      substantive = [m for m in messages
                     if len(m['text']) >= min_chars and _is_substantive(m['text'])]
      embedding   = среднее embedding'ов substantive, взвешенное по
                    len(m['text']) (numpy.average(..., weights=...), результат
                    -> list[float])
      root        = messages[0]

    Документы БЕЗ substantive-сообщений в результат НЕ попадают (это флуд;
    текущее поведение build_topics их тоже выбрасывало — деградации нет).
    PII: функция не читает и не возвращает ничего нового — те же dict'ы
    fragments, сгруппированные.
    """
```

Детали реализации (один путь):
- `_is_substantive` и `_WORD_RE` ПЕРЕЕЗЖАЮТ из `core/brain/topics.py` сюда
  (cut, не copy): в topics.py их определения удалить и заменить на
  `from core.brain.chains import _is_substantive` (реэкспорт — существующий
  `test_is_substantive` импортирует из core.brain.topics и остаётся зелёным).
  Направление импорта одно: topics → chains; chains НЕ импортирует из topics —
  иначе циклический ImportError (найдено ревью 2026-06-10).
- Все обращения к полям `msg_id` и `reply_to_msg_id` — только через
  `f.get(...)`, НЕ `f[...]`: синтетические dict'ы существующих тестов
  (test_topics_build._frag) этих ключей не имеют; отсутствие ключей =
  «сообщение без reply-связей», не ошибка.
- union-find: простой parent-массив с path compression, без библиотек.
- created_at в fragments — ISO-строка; для разрывов парсить
  `datetime.fromisoformat` один раз перед сортировкой.
- msg_id == None (мусорный external_id) → сообщение участвует только в
  серийной склейке, reply-связи с ним невозможны.
- Самоссылка / reply на сообщение НЕ из выборки → игнор связи (без падения).

## Тесты

`tests/test_chains.py` — чистые юниты на синтетических dict'ах (без БД):
- reply-пара склеивается; reply на отсутствующего родителя — нет.
- цепочка глубины 3 (внук → родитель → корень) — одна компонента.
- серия: 3 сообщения одного автора с шагом 60с — один документ;
  с шагом 400с — три документа; разные авторы с шагом 60с — НЕ склеены.
- кейс лонгрида: серия из 3 длинных + reply-ответы на каждую часть →
  ОДИН документ, root = первая часть.
- substantive: документ из коротких реакций (<80) вокруг одного длинного —
  substantive == [длинное], embedding == embedding длинного.
- документ целиком из коротких → отсутствует в результате.
- взвешивание: два substantive с разными длинами → embedding смещён к
  длинному (проверить численно на 2-мерных векторах).
- root = самое раннее сообщение компоненты, даже если оно короткое.

Что может сломаться: `test_is_substantive` и всё, что импортирует
`_is_substantive` из `core.brain.topics` — должен остаться зелёным через
реэкспорт (проверяется прогоном всех тестов).

## Команды для верификации

```bash
PYTHONUTF8=1 python -m pytest tests/test_chains.py -q
PYTHONUTF8=1 python -m pytest tests/ -q
```

## Критерии готовности

- [ ] `build_chains` покрывает все кейсы из списка тестов выше.
- [ ] Модуль не импортирует DB/LLM/telegram И не импортирует из
      `core.brain.topics` (чистый, без циклов).
- [ ] `_is_substantive` определена в chains.py; в topics.py — только импорт;
      `test_is_substantive` зелёный без правок.
- [ ] Поля `msg_id`/`reply_to_msg_id` читаются через `f.get(...)` (юнит:
      dict'ы без этих ключей не падают).
- [ ] `python -m pytest tests/test_chains.py -q` зелёный.
- [ ] `python -m pytest tests/ -q` — все зелёные.
