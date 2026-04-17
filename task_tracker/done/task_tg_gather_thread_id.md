# Задача для telegram-gather: добавить message_thread_id

## Контекст

WNDRverse использует Telegram супергруппу с Topics (топиками).
Нам нужно различать сообщения из разных топиков: Bus (topic_id=3), Showcase (topic_id=15), General.

telegram-gather сейчас возвращает `{id, date, sender, text, reply_to}` — без информации о топике.

## Что нужно

Добавить поле `message_thread_id` в ответ API `/api/messages`.

### Где взять в Telethon

В объекте `Message` от Telethon:

```python
# Вариант 1: напрямую из reply_to
if message.reply_to and hasattr(message.reply_to, 'forum_topic'):
    thread_id = message.reply_to.reply_to_top_id

# Вариант 2: атрибут reply_to_top_id (Telethon 1.28+)
thread_id = getattr(message, 'reply_to_top_id', None)

# Вариант 3: если сообщение само является началом топика
# message.reply_to.forum_topic == True → это первое сообщение в топике
```

Telethon хранит это в `MessageReplyHeader`:
- `reply_to_top_id` — ID первого сообщения в топике (= thread_id для Bot API)
- `forum_topic` — флаг "это топик, а не обычный реплай"

### Ожидаемый формат ответа

Было:
```json
{"id": 123, "date": "...", "sender": "...", "text": "...", "reply_to": null}
```

Стало:
```json
{"id": 123, "date": "...", "sender": "...", "text": "...", "reply_to": null, "message_thread_id": 3}
```

`message_thread_id` = `null` если сообщение не в топике (обычная группа / General).

### Зачем

Чтобы фильтровать: "дай мне только сообщения из Bus (topic_id=3)" — либо на стороне API (параметр `?topic_id=3`), либо на нашей стороне (фильтруем по полю в ответе).

Идеально — оба варианта:
1. Поле `message_thread_id` в каждом сообщении (всегда)
2. Опциональный параметр `?topic_id=N` для фильтрации на сервере

### Приоритет

Вариант 1 (поле в ответе) — минимум, нам хватит.
Вариант 2 (параметр фильтрации) — nice to have.
