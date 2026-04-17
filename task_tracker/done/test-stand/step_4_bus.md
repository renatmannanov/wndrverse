# Step 4: Доработать bus.py — поддержка токена агента

> Статус: done

## Что сделано

bus.py обновлён:

1. **`post_to_bus()`** — добавлен параметр `bot_token`, возвращает `Message`
2. **`reply_in_bus()`** — новая функция для реплаев с `reply_to_message_id`

## Изменения

```python
# Было
async def post_to_bus(text: str, key: str | None = None):
    bot = Bot(token=CURATOR_BOT_TOKEN)
    await bot.send_message(...)

# Стало
async def post_to_bus(text: str, bot_token: str | None = None, key: str | None = None) -> Message | None:
    token = bot_token or CURATOR_BOT_TOKEN
    bot = Bot(token=token)
    msg = await bot.send_message(...)
    return msg

async def reply_in_bus(text: str, reply_to_message_id: int, bot_token: str | None = None) -> Message:
    ...
```

## Критерии готовности

- [x] post_to_bus принимает bot_token
- [x] post_to_bus возвращает Message
- [x] reply_in_bus создана
