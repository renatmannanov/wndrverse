# Шаг 3: Бот-команда /topics (хендлер + валидация + регистрация)

> Зависит от: шаг 1 (count), шаг 2 (build_topics_digest)
> Статус: [x] done

## Задача

В `bot/ingest_bot.py` добавить команду `/topics <топик> <YYYY-MM-DD>
<YYYY-MM-DD> [limit]` по образцу `/summary` (on_summary, строки ~130-207).
В DM вызывающему. Тот же вайтлист `ALLOWED`. Точные даты (как /summary), плюс
опциональный 4-й аргумент limit (int, дефолт 10).

### 3.1 Импорты

В `bot/ingest_bot.py` уже есть (строки ~20-22): `TOPIC_HINTS`,
`MAX_FRAGMENTS_WITHOUT_SELECTION` из synthesis; `get_topics_with_counts` из
fragments_db; `build_digest, count_fragments, parse_date_range` из delivery.cli;
`send_formatted_dm` из delivery.markup. ИХ НЕ ДУБЛИРОВАТЬ.

ДОБАВИТЬ только новое:
- к импорту из `delivery.cli` дописать `build_topics_digest` (шаг 2);
- к импорту из `core.store.fragments_db` дописать
  `count_embedded_fragments_for_period` (шаг 1).

```python
# было: from delivery.cli import build_digest, count_fragments, parse_date_range
from delivery.cli import (
    build_digest, count_fragments, parse_date_range, build_topics_digest)
# было: from core.store.fragments_db import get_topics_with_counts
from core.store.fragments_db import (
    get_topics_with_counts, count_embedded_fragments_for_period)
```
ВНИМАНИЕ: `count_fragments` (уже импортирован) у `/topics` НЕ используется — для
ack берём `count_embedded_fragments_for_period` (тот же фильтр, что у hot-topics).
`parse_date_range` переиспользуется (точные даты как у /summary).

### 3.2 Константа дефолта + класс ошибки

```python
DEFAULT_TOPICS_LIMIT = 10
```
Переиспользовать существующий паттерн ошибки — НЕ плодить новый класс. Сделать
по образцу `SummaryArgError`:
```python
class TopicsArgError(ValueError):
    """Raised for any bad /topics input — message is the user-facing reply."""
```

### 3.3 Чистая валидация (тестируемая, без БД/LLM/Telegram)

```python
def validate_topics_args(args: list[str]) -> tuple[str, object, object, int]:
    """Validate `/topics <topic> <from> <till> [limit]` -> (topic, since, until, limit).

    Raises TopicsArgError with a friendly Russian message on any problem
    (wrong arg count, unknown topic, 'all', bad date, from>till, bad limit).
    Pure — no DB/OpenAI/Telegram, so it's unit-testable. The 0-fragments case is
    handled later (after the DB count) so we never spend OpenAI on an empty period.
    """
```
Логика (правило #1 — один путь, без «либо»):
- `len(args) not in (3, 4)` → TopicsArgError с форматом-подсказкой.
- `topic, from_s, till_s = args[0], args[1], args[2]`.
- `if topic == "all"` → TopicsArgError («/topics работает с ОДНИМ топиком, не all»).
- `if topic not in TOPIC_HINTS` → TopicsArgError со списком известных топиков.
- `since, until = parse_date_range(from_s, till_s)` в try/except ValueError →
  TopicsArgError («Неверные даты. Формат YYYY-MM-DD, и from ≤ till.»).
- limit: если `len(args) == 4` → `int(args[3])` в try/except ValueError →
  TopicsArgError («limit должен быть числом»); `if limit <= 0` → TopicsArgError;
  иначе `limit = DEFAULT_TOPICS_LIMIT`.
- Вернуть `(topic, since, until, limit)`.

### 3.4 Help-текст

```python
def _topics_help() -> str:
    """Format help + the list of topics that actually have fragments."""
```
По образцу `_summary_help`, но текст про /topics:
- «Формат: /topics <topic> <YYYY-MM-DD> <YYYY-MM-DD> [limit]»
- «Пример: /topics boltalka 2026-05-01 2026-05-31 10»
- список топиков через `get_topics_with_counts(only=set(TOPIC_HINTS))` (как summary).
  ⚠️ Числа в этом списке — по фильтру get_topics_with_counts (min_chars=150) и НЕ
  совпадут с ack-числом (count_embedded_fragments_for_period, другой фильтр). Это
  норма: help — грубый ориентир «какие топики вообще есть», ack — точный счёт за
  период. Не пытаться их синхронизировать.

### 3.5 Хендлер on_topics (по образцу on_summary)

```python
async def on_topics(update, context):
    """/topics <topic> <from> <till> [limit] — hot-topics digest, DM the caller."""
```
ТЕРМИНОЛОГИЯ (важно, чтобы не путать каналы — как в on_summary):
- «reply» = `update.message.reply_text(...)` — идёт в ТОТ ЖЕ чат, откуда пришла
  команда (ack, ошибки, подсказки). У /summary это группа/личка по месту вызова.
- «DM-дайджест» = `send_formatted_dm(context.bot, user_id, ...)` — сам дайджест,
  в ЛИЧКУ вызывающему, отдельным сообщением. Только результат идёт сюда.

Шаги (КОПИЯ структуры on_summary, заменить вызовы):
1. whitelist: `if user_id not in ALLOWED:` → reply «Команда доступна только
   администраторам.» + log + return. (fail-closed.)
2. no args: `if not context.args:` → reply `_topics_help()` + return.
3. validate: `try: topic, since, until, limit = validate_topics_args(args)
   except TopicsArgError as e: reply(str(e)); return`.
4. ACK (дешёвый COUNT, no OpenAI) — всё это reply в чат команды:
   `found = await asyncio.to_thread(count_embedded_fragments_for_period, topic,
   since, until)` в try/except (ошибка сервера → reply дружелюбно + log).
   - `if found == 0:` → reply «Топик: … | Период: from..till\nЗа этот период
     сообщений нет.» + return (БЕЗ спенда, БЕЗ DM-дайджеста).
   - иначе reply-ack: «Топик: {topic} | Период: {from_s}..{till_s}\nНайдено
     {found} сообщений, собираю горячие темы…». (Без MAX_FRAGMENTS — у hot-topics
     нет порога селекции; спенд идёт на названия тем.)
5. сборка off event loop:
   `result = await asyncio.to_thread(build_topics_digest, topic, since, until, limit)`
   в try/except (ошибка → reply дружелюбно + log). `build_topics_digest` НЕ
   кидает ValueError здесь (topic уже провалидирован, не 'all').
   - `if result is None:` → reply «За этот период по топику нет сообщений.» (гонка:
     опустело между count и сборкой — спенда не было), return. БЕЗ DM-дайджеста.
   - ВНИМАНИЕ: `result` НЕ содержит ключа `'used'` (build_topics_digest отдаёт
     только `{'text','found'}`). При копировании лога из on_summary УБРАТЬ
     `result['used']` — иначе KeyError. Логировать: `found=%d len=%d`.
6. DM-дайджест: `digest = result['text'][:TG_MSG_LIMIT]`;
   `await send_formatted_dm(context.bot, user_id, digest)` в try/except Forbidden →
   reply «Напиши мне в личку и нажми /start…». (send_formatted_dm переиспользуем
   как есть — наши t.me-ссылки голые, без < > &, Telegram автолинкует; markdown-
   конвертер их не трогает.)
   ⚠️ Усечение `[:TG_MSG_LIMIT]` режет RAW-текст ДО HTML-escape внутри
   send_formatted_dm — унаследованное поведение от /summary (ingest_bot.py:198).
   НЕ чинить в этом плане (иначе трогаем и /summary). Ядро hot-topics целит
   ~2800 символов, до 4096 далеко; при переполнении сработает plain-text fallback
   в send_formatted_dm. Зафиксировано решением (см. _review_summary.md #5).

### 3.6 Регистрация в main()

ДО catch-all MessageHandler (как /summary — PTB берёт первый матчящий хендлер):
```python
app.add_handler(CommandHandler("summary", on_summary))
app.add_handler(CommandHandler("topics", on_topics))   # <-- добавить
app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, on_message))
```

ВАЖНО (правило #1): один путь обработки каждой ошибки, без «либо так либо эдак».
ВАЖНО (PII): бот НЕ подмешивает имена — `result['text']` приходит из ядра, где в
OpenAI ушли только тексты (ядро не тронуто). Бот только пересылает текст в DM.

## Тесты

`tests/test_topics_command.py` — по образцу `tests/test_summary_command.py`
(фейковые Bot/Message, asyncio.run, monkeypatch; БЕЗ БД/LLM/Telegram):
- `validate_topics_args`:
  - good 3 args → (topic, since, until, 10) [дефолт limit].
  - good 4 args → limit из args[3].
  - wrong arg count (0/1/2/5) → TopicsArgError.
  - unknown topic → TopicsArgError.
  - `'all'` топик → TopicsArgError.
  - bad date / from>till → TopicsArgError.
  - bad limit ('foo', '0', '-3') → TopicsArgError.
- `on_topics` handler:
  - denied user → ни count, ни build_topics_digest не вызваны; reply про админа.
  - no args → help (содержит «Формат:» и топик из мок-списка); ничего не вызвано.
  - valid call → ack (содержит found-число + «from..till») ДО сборки;
    build_topics_digest вызван ровно 1 раз; чистый текст в DM вызывающему
    (chat_id == uid, без stats-строки).
  - empty period (count=0) → ack «нет»; build_topics_digest НЕ вызван; в DM
    ничего не отправлено.
  - Forbidden при отправке DM → reply с «/start».

Что может сломаться: существующая `/summary` (общий модуль) — её тесты должны
остаться зелёными.

## Команды для верификации

```bash
# Юнит-тесты новой команды
PYTHONUTF8=1 python -m pytest tests/test_topics_command.py -q
# /summary не сломан
PYTHONUTF8=1 python -m pytest tests/test_summary_command.py -q
# Всё вместе
PYTHONUTF8=1 python -m pytest tests/ -q
# Модуль импортируется (хендлер зарегистрирован) — без запуска polling
PYTHONUTF8=1 python -c "from bot.ingest_bot import on_topics, validate_topics_args, TopicsArgError; print('ok')"
```

Ручной smoke (требует живого бота — делать ОТДЕЛЬНО, не в CI):
напиши боту в DM `/topics boltalka 2026-05-01 2026-05-31` → ack → дайджест.

## Критерии готовности

- [x] `validate_topics_args` покрывает все кейсы (см. тесты), TopicsArgError с
      понятным русским текстом.
- [x] `on_topics`: denial не вызывает count/build; no-args→help; valid→ack+DM;
      empty→ack без спенда; Forbidden→hint /start.
- [x] ACK приходит ДО OpenAI-спенда (count дешёвый); 0 фрагментов → без спенда.
- [x] `CommandHandler("topics")` зарегистрирован ДО MessageHandler.
- [x] limit опционален (дефолт 10), плохой limit → дружелюбная ошибка.
- [x] `python -m pytest tests/test_topics_command.py -q` зелёный.
- [x] `python -m pytest tests/test_summary_command.py -q` зелёный (не сломали).
- [x] `python -m pytest tests/ -q` — все зелёные.
