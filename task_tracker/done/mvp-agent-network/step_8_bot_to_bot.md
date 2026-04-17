# Шаг 8: Bot-to-Bot Communication — агенты реагируют друг на друга

> Зависит от: шаг 7 (managed bots) или шаг 3 (хотя бы 2 бота в группе)
> Статус: частично done (b2b работает, loop_guard не написан)

## Задача

Протестировать Bot-to-Bot Communication в Bus.
Цель: один бот видит сообщение другого бота и реагирует реплаем.

## Предусловия

- Минимум 2 бота в группе (родитель + дочерний, или 2 дочерних)
- Оба бота — админы группы (или privacy mode отключён)

## Что делаем

### 8.1 Включить Bot-to-Bot Communication Mode

1. Открыть BotFather → найти @wndrverse_bot
2. Bot Settings → включить "Bot-to-Bot Communication"
3. Повторить для дочернего бота (если нужно чтобы он тоже видел)

> Правило: хотя бы один из двух ботов должен иметь b2b mode ON.
> Рекомендация: включить для всех ботов в группе.

### 8.2 Тест: бот видит сообщение другого бота

```python
# test_b2b.py
import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters

load_dotenv()

PARENT_TOKEN = os.getenv("CURATOR_BOT_TOKEN")
CHILD_TOKEN = os.getenv("AGENT_TEST_TOKEN")  # из шага 7
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID"))
BUS_TOPIC_ID = int(os.getenv("BUS_TOPIC_ID"))


async def on_message(update: Update, context):
    """Обработчик: родительский бот видит сообщение дочернего."""
    msg = update.message
    if msg and msg.from_user and msg.from_user.is_bot:
        print(f"B2B received: [{msg.from_user.username}] {msg.text}")


async def main():
    # 1. Запустить родительский бот на приём
    app = Application.builder().token(PARENT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, on_message))

    # 2. Отправить сообщение от дочернего бота
    child_bot = Bot(token=CHILD_TOKEN)
    await child_bot.send_message(
        chat_id=GROUP_CHAT_ID,
        message_thread_id=BUS_TOPIC_ID,
        text="[test_agent|managed] Hello from child bot!",
    )
    print("Child bot sent message to Bus")

    # 3. Подождать и проверить что родитель получил update
    print("Starting parent bot polling (10 sec)...")
    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.sleep(10)
        await app.updater.stop()
        await app.stop()


asyncio.run(main())
```

### 8.3 Тест: бот реплаит на сообщение другого бота

```python
# test_b2b_reply.py — расширение предыдущего теста

async def on_message(update: Update, context):
    msg = update.message
    if not msg or not msg.from_user or not msg.from_user.is_bot:
        return

    bot_username = msg.from_user.username
    text = msg.text or ""

    # Реагируем только на сообщения от дочерних ботов (не от себя)
    if bot_username == "wndrverse_bot":
        return

    print(f"B2B: [{bot_username}] {text}")

    # Простой pre-matching: если в сообщении есть ключевое слово
    keywords = ["парсинг", "AI", "агенты", "дети", "образование"]
    matched = [kw for kw in keywords if kw.lower() in text.lower()]

    if matched:
        reply_text = f"🔗 Совпадение по: {', '.join(matched)}"
        await msg.reply_text(reply_text)
        print(f"  → Replied with match: {matched}")
```

### 8.4 Защита от петель (обязательно!)

```python
# curator/loop_guard.py

import time
from collections import defaultdict

# Rate limiter: max 1 reply per bot pair per 30 seconds
_last_reply: dict[tuple[str, str], float] = defaultdict(float)
_reply_depth: dict[int, int] = defaultdict(int)  # message_id → depth

MAX_DEPTH = 2
MIN_INTERVAL = 30  # seconds


def can_reply(from_bot: str, to_bot: str, reply_to_msg_id: int | None) -> bool:
    """Проверить можно ли ответить. False = заблокировано."""
    pair = tuple(sorted([from_bot, to_bot]))
    now = time.time()

    # Rate limit
    if now - _last_reply[pair] < MIN_INTERVAL:
        return False

    # Depth limit
    if reply_to_msg_id and _reply_depth[reply_to_msg_id] >= MAX_DEPTH:
        return False

    return True


def record_reply(from_bot: str, to_bot: str, reply_to_msg_id: int | None, new_msg_id: int):
    """Зафиксировать реплай."""
    pair = tuple(sorted([from_bot, to_bot]))
    _last_reply[pair] = time.time()

    depth = 0
    if reply_to_msg_id:
        depth = _reply_depth[reply_to_msg_id] + 1
    _reply_depth[new_msg_id] = depth
```

## Команды для верификации

```bash
cd c:/Users/renat/projects/wndrverse

# Тест 1: дочерний бот пишет, родитель видит
python test_b2b.py
# Ожидаем: "B2B received: [test_agent_wndr] ..."

# Тест 2: родитель реплаит на сообщение дочернего
python test_b2b_reply.py
# Ожидаем: реплай от @wndrverse_bot в Bus

# Визуально в Telegram:
# Bus должен содержать сообщение от @test_agent_wndr
# и реплай от @wndrverse_bot (или наоборот)
```

## Результаты теста (2026-04-16)

- b2b mode включён для @rm_curator_bot
- @rm_curator_bot видит сообщения от @test_wndr_agentbot в Bus (подтверждено через getUpdates)
- Реплай работает: message_id=48 (реплай на message_id=47)
- Для дочернего бота b2b mode НЕ нужно включать — достаточно что у родителя включён
- Loop guard ещё не реализован — сделать при подключении автоматических агентов (фаза 2)

## Критерии готовности

- [x] Bot-to-Bot Communication Mode включён для @rm_curator_bot
- [x] Родительский бот видит сообщения дочернего в Bus (update получен)
- [x] Родительский бот может реплаить на сообщение дочернего
- [ ] Loop guard работает: max 2 реплая в цепочке, rate limit 30 сек → фаза 2
- [x] Визуально в Telegram: видна цепочка бот → бот в Bus топике

## Если не работает

- **Бот не видит сообщения другого бота:** проверить что b2b mode ON хотя бы у одного. Проверить что бот — админ или privacy mode OFF.
- **getUpdates не содержит сообщения от бота:** убедиться что бот добавлен в группу ПОСЛЕ включения b2b mode. Если нет — удалить и добавить заново.
- **Петля сообщений:** немедленно остановить бота. Проверить loop_guard.py. Увеличить MIN_INTERVAL.
