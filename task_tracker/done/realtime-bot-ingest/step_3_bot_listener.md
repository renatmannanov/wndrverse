# Шаг 3: Бот-листенер (polling) → ingest

> Зависит от: шаг 1 (resolve_topic), шаг 2 (bot_message_to_fragment)
> Статус: [ ] pending

## Задача

Создать сам бот — отдельный долгоживущий процесс на `python-telegram-bot`,
polling, который на каждое новое сообщение из отслеживаемых чатов пишет фрагмент
в БД через `ingest()`.

Файлы:
- `bot/__init__.py` — **пустой**, ОБЯЗАТЕЛЬНО (иначе `python -m bot.ingest_bot` и
  `import bot.ingest_bot` упадут `ModuleNotFoundError`).
- `bot/ingest_bot.py` — сам бот.

Каталог `bot/` новый, в корне — отдельно от `core/`, т.к. это процесс-источник,
а не часть ядра.

### Структура
```python
from telegram.ext import Application, MessageHandler, filters
from core.ingest.loaders import ingest
from core.ingest.bot_adapter import bot_message_to_fragment
from core.ingest.topic_map import resolve_topic
import asyncio, logging, os

async def on_message(update, context):
    msg = update.effective_message
    if msg is None:
        return
    topic = resolve_topic(msg.chat_id, msg.message_thread_id)
    if topic is None:
        logging.info("skip: no topic for chat=%s thread=%s", msg.chat_id, msg.message_thread_id)
        return
    frag = bot_message_to_fragment(msg, topic=topic)
    if frag is None:
        return  # пустое/служебное
    # синхронный ingest в отдельном потоке — не блокируем event loop.
    # try/except: падение БД не должно ронять хендлер; сообщение логируем как
    # потерянное, бот продолжает жить.
    try:
        res = await asyncio.to_thread(ingest, [frag])
        logging.info("ingest chat=%s msg=%s topic=%s -> %s",
                     msg.chat_id, msg.message_id, topic, res)
    except Exception:
        logging.exception("ingest FAILED chat=%s msg=%s topic=%s (message lost)",
                          msg.chat_id, msg.message_id, topic)

def main():
    token = os.environ["BOT_TOKEN_INGEST"]
    app = Application.builder().token(token).build()
    # text + media-with-caption; служебные отфильтруются в адаптере (None)
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, on_message))
    app.run_polling(allowed_updates=["message"])
```

### Решения (зафиксированы)
- **Один бот** на все отслеживаемые чаты (один токен `BOT_TOKEN_INGEST`). При
  переходе на «1 чат много топиков» это тем более один бот.
- **polling**, не webhook. `run_polling`.
- `asyncio.to_thread(ingest, [frag])` — `ingest` синхронный (дёргает БД),
  оборачиваем чтобы не блокировать event loop PTB.
- `filters.ALL & ~filters.StatusUpdate.ALL` — берём контент, отсекаем служебные
  апдейты (вход/выход участников, смена названия и т.п.). Остаточные edge cases —
  в шаге 4.
- ENV: `BOT_TOKEN_INGEST` (новый, не путать с `BOT_TOKEN` куратора),
  `WNDR_TOPIC_MAP`, `DATABASE_URL`. Добавить в `.env.example`.

### НЕ делать здесь
- Не ставить бота в группы (это пользователь, вручную, перед smoke).
- Не трогать куратора/agent-template.
- Не добавлять edits/replies/media спецлогику — это шаг 4.
- **НЕ добавлять фильтр `if msg.from_user.is_bot: return`** — он целиком (код +
  тест) в шаге 4, чтобы тест покрывал ту же правку. В step_3 его нет.

### Запуск (единственная форма — зафиксировано)
`python -m bot.ingest_bot` (модульный запуск; `python bot/ingest_bot.py` НЕ
использовать — ломает абсолютные импорты `core.*`). `bot/ingest_bot.py` должен
иметь `if __name__ == "__main__": main()`.

## Тесты

Юнит-тест на `on_message` без реального Telegram (мокнуть `update`/`context`,
замокать `ingest` и проверить что он вызван с правильным фрагментом, а при
`topic is None` — НЕ вызван). Файл `tests/test_ingest_bot.py`.
Полный запуск бота — в шаге 5 (smoke с реальной группой).

## Команды для верификации

```bash
python -m pytest tests/test_ingest_bot.py -q

# импортируется без ошибок (синтаксис, импорты) — требует bot/__init__.py
python -c "import bot.ingest_bot"

# запуск бота — ТОЛЬКО модульной формой (в шаге 5 с реальным токеном):
#   python -m bot.ingest_bot
# здесь только синтаксис/импорт, реальный старт — шаг 5
```

## Критерии готовности

- [ ] `bot/__init__.py` существует (пустой).
- [ ] `bot/ingest_bot.py` импортируется без ошибок (`python -c "import bot.ingest_bot"`).
- [ ] `on_message`: при `resolve_topic → None` ingest НЕ вызывается; иначе вызывается
      с `[frag]`; вызов через `asyncio.to_thread`, обёрнут в try/except.
- [ ] is_bot-фильтр в этом шаге ОТСУТСТВУЕТ (добавляется в step_4).
- [ ] `.env.example` дополнен `BOT_TOKEN_INGEST`, `WNDR_TOPIC_MAP`.
- [ ] `pytest tests/test_ingest_bot.py` зелёный.
