# Review: Code
> digest-output-quality plan vs. реальный код  
> Проверено: core/brain/synthesis.py, core/llm/client.py, core/store/fragments_db.py,  
> delivery/cli.py, core/prompts/digest_synthesis.md, bot/ingest_bot.py, tests/*.py

---

## Критичное (блокирует выполнение)

### 1. `tests/__init__.py` отсутствует — `python -m tests.golden.run` не заработает

**Файл:** `tests/` (нет `__init__.py`)

Шаг 5 предполагает запуск `python -m tests.golden.run`. Python требует, чтобы `tests` был пакетом (т.е. имел `__init__.py`) для `-m tests.golden.run`. Без него будет `ModuleNotFoundError`. `conftest.py` добавляет корень репо в `sys.path`, но это помогает только pytest — не `python -m`.

**Что делать:** создать пустой `tests/__init__.py` в шаге 5. Добавить его в критерии готовности.

---

### 2. `synthesis.py` не импортирует `json` — `_critique` упадёт при импорте

**Файл:** `core/brain/synthesis.py` — нет `import json` (проверено: grep по файлу)

Шаг 4 реализует `_critique`, которая делает `json.loads(...)`. Без `import json` будет `NameError` при первом вызове. Шаг 4 не упоминает добавление этого импорта.

**Что делать:** добавить `import json` в шаге 4 вместе с реализацией `_critique`.

---

## Важное (стоит исправить до начала)

### 3. Комментарий `bot/ingest_bot.py:257` устареет после шага 3

**Файл:** `bot/ingest_bot.py`, строка 257

```python
NOTE: the counts here follow get_topics_with_counts' filter (min_chars=150)
```

После шага 3 дефолт `get_topics_with_counts` меняется на 80. Комментарий останется с захардкоженным `150`. Шаг 3 явно говорит «комментарий править не нужно», но аргументирует это другим поводом (несовпадение двух разных count-функций). Фактически сам `min_chars=150` в тексте комментария становится неверным.

**Что делать:** в шаге 3 обновить строку 257: `min_chars=150` → `min_chars=80` (или убрать конкретное число).

---

### 4. Шаг 2: `result['model']` в ветке `< 3` фрагментов не упомянут

**Файл:** `core/brain/synthesis.py`, строки 94–96

```python
return {'content': content, 'fragment_ids': [f['id'] for f in fragments],
        'author_refs': {}, 'found': found, 'model': COMPLETION_MODEL}
```

Шаг 2 говорит «в `result['model']` указывать модель синтеза», но это касается только основного пути. В ветке `< 3` синтеза нет — там правильно оставить `COMPLETION_MODEL` (mini). Шаг 2 не оговаривает это явно, что может запутать исполнителя.

**Что делать:** уточнить в тексте шага 2: ветку `< 3` (`'model': COMPLETION_MODEL`) не трогать — там синтеза нет, mini корректен.

---

### 5. Шаг 4: `_critique` вызывается на `grouped_text`, но переменная доступна — порядок нужен точный

**Файл:** `core/brain/synthesis.py`, строки 115–128

```python
grouped_text, author_refs = _group_by_author(selected)   # строка 115
content = _synthesize_fragments(...)                      # строка 120
result = { ... }                                          # строка 122
```

`_critique(content, grouped_text)` нужно вставить ПОСЛЕ строки 120 и ДО строки 122. Переменная `grouped_text` доступна. Шаг 4 описывает это верно. Всё ок, но стоит убедиться, что `defects = _critique(content, grouped_text)` не перепутают порядок аргументов (в промпте критика `{digest}` = `content`, `{sources}` = `grouped_text`).

---

### 6. Шаг 5: `build_digest` не возвращает `critic_issues` — золотой раннер получит `None`

**Файл:** `delivery/cli.py`, функция `build_digest` (строки 162–200)

`build_digest` возвращает `{'text', 'found', 'used'}` — `critic_issues` туда не прокидывается. Шаг 5 говорит «если build_digest их прокинет — опционально», признавая это. Но раннер в `run.py` вызывает именно `build_digest`, а не `synthesize` напрямую. Значит `critic_issues` будет недоступен, и раздел сводки по дефектам всегда будет пуст.

Это не блокирует шаг 5, но если хочется видеть дефекты в сводке раннера — надо либо прокинуть через `build_digest`, либо раннер должен это явно учитывать. Уточнить ожидания в шаге 5.

---

## Мелочи (можно по ходу)

### 7. Шаг 1: `_looks_truncated` — символ `"` (кавычка) в множестве терминальных

**Файл:** шаг 1, спецификация `_looks_truncated`

В тексте шага множество терминальных: `{'.', '!', '?', '…', ')', '»', '"'}`. Обычная прямая кавычка `"` смотрится странно (в реальном дайджесте она редка как финальный символ, скорее нужна `"` и `»`). Это не ошибка, но стоит дважды проверить, нужна ли именно ASCII `"` (0x22) или подразумевалась типографская `"` (U+201D). Тест-кейс `"Цитата»"` есть, а для `"` — нет.

---

### 8. Шаг 3: `_summary_help` (строка 90 ingest_bot.py) и комментарий `min_chars=150`

**Файл:** `bot/ingest_bot.py`, `_summary_help` (строка 86-101) — сам текст хелпа не содержит `min_chars`, поэтому пользователю ничего не сломается. Упомянуто в п.3 выше (комментарий строки 257). Дублировать не нужно.

---

### 9. Шаг 5: кейс `offerings_all.json` с `since=null, till=null` — проверить доступность данных

**Файл:** шаг 5 (план структуры `cases/`)

`offerings_all.json` ("since": null, "till": null) означает весь корпус. Шаг 5 говорит уточнить реальные даты у пользователя перед финальным набором кейсов. Это корректный кейс (pass `since=None, until=None` → весь корпус), но OpenAI-расходы могут быть велики при большом корпусе. Предупредить при реализации.

---

## Не найдено проблем

- Существующие тесты (`test_synthesis_prompt.py`, `test_group_by_author.py`, `test_date_range.py`, `test_summary_command.py`, `test_topics_command.py`, `test_scheduler.py`) не затрагиваются шагами 1–4: нигде не проверяется значение `max_tokens`, не ассертируется `result['model']`, не проверяется `min_chars=150` как число.
- `test_no_bounds_behaves_as_before` (test_date_range.py строка 128): проверяет количество SQL-фильтров (= 3), не значение `min_chars`. После шага 3 тест останется зелёным.
- `get_fragments_for_digest` и `get_topics_with_counts` — сигнатуры точно совпадают с описанием в плане (обе имеют `min_chars: int = 150` как дефолт, обе в `fragments_db.py`).
- `get_embedded_fragments_for_period` — в плане указано «не трогать». Дефолт там `min_chars=1` — корректно.
- PII-контракт: `_group_by_author` возвращает `grouped_text` без имён (проверено: тест `test_names_never_in_grouped_text_pii`). `_critique` может безопасно использовать `grouped_text` + `content` без нарушения.
- `_synthesize_fragments` вызывается без явного `model=` → берёт дефолт `COMPLETION_MODEL` (mini). После шага 2 нужно будет передать `model=COMPLETION_MODEL_SYNTHESIS` явно — это точно описано в шаге 2.
- `core/prompts/digest_critic.md` — не существует (ожидаемо, создаётся в шаге 4).
- `tests/golden/` — не существует (ожидаемо, создаётся в шаге 5).
- `synthesize_and_save` мокается целиком в `test_synthesize_and_save_keeps_author_refs` — критик там не вызовется, тест останется зелёным после шага 4.
- `_select_fragments` вызывает `complete(prompt, temperature=0.0)` без явного `model=` — возьмёт дефолт `COMPLETION_MODEL` (mini). Шаг 2 явно говорит не трогать эту функцию.
