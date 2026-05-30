# Шаг 2: Адаптер bot Message → Fragment dict

> Зависит от: шаг 1 (resolve_topic)
> Статус: [ ] pending

## Задача

Создать `core/ingest/bot_adapter.py` — приводит объект `telegram.Message`
(python-telegram-bot) к Fragment dict, **переиспользуя** `message_to_fragment`
из `core/ingest/normalize.py`. НЕ дублировать логику нормализации.

### Функция
```python
def bot_message_to_fragment(message, *, topic: str) -> dict | None:
    """telegram.Message (PTB) → Fragment dict, через normalize.message_to_fragment.
    Returns None for empty/service messages (no text)."""
```

### Что делает (ровно три вещи поверх normalize)
1. Собирает **плоский dict** в формате, который ждёт `message_to_fragment`:
   - `id`        ← `message.message_id`
   - `text`      ← `message.text or message.caption` (caption — для медиа с подписью)
   - `date`      ← `message.date.isoformat()` (PTB даёт `datetime`; normalize ждёт ISO-строку)
   - `user_id`   ← `message.from_user.id if message.from_user else None`
   - `sender_name` ← `message.from_user.full_name if message.from_user else None`
   - `username`  ← `message.from_user.username if message.from_user else None`
   - `reply_to_msg_id` ← `message.reply_to_message.message_id if message.reply_to_message else None`
   - `reactions`, `char_count` — опционально (можно None / len(text))
2. Зовёт `message_to_fragment(flat, topic=topic, chat_name='tgbot',
   thread_root_id=message.message_thread_id)`.
   - `chat_name='tgbot'` влияет ТОЛЬКО на external_id внутри normalize: тот вернёт
     `external_id = 'wndr_tgbot_{id}'`. **Это НЕ наш формат** — его ОБЯЗАТЕЛЬНО
     перезаписать в п.3. Не оставлять как есть (иначе коллизии message_id между
     разными чатами + неконсистентный префикс).
   - normalize уже кладёт `message_thread_id` в возвращаемый dict (из
     `thread_root_id`) — отдельно его выставлять не нужно.
3. После normalize **перезаписывает два поля** во вернувшемся dict (ОБА обязательны):
   - `external_id = f"tgbot_{message.chat_id}_{message.message_id}"`
     ← перезаписывает `wndr_tgbot_...` из п.2. chat_id в ключе обязателен.
   - `channel_id  = message.chat_id`  (normalize его НЕ ставит — для файлов
     chat_id не было).
   Если normalize вернул `None` (нет текста) → вернуть `None` (поля не трогаем).

### Важно
- НЕ менять `normalize.py`. Все доп-поля выставляем в адаптере.
- `message.chat_id` в супергруппах = `-100...` формат — это и есть наш `channel_id`.
- Caption у медиа: если у фото/видео есть подпись — это валидный текст, берём.
  Если ни text ни caption — normalize вернёт None, фрагмент скипнется (это ок).

## Тесты

`tests/test_bot_adapter.py` — без реального Telegram, на фейковых объектах
(простой класс/namedtuple/`types.SimpleNamespace` имитирующий `Message`):
- обычное текстовое сообщение → dict с правильными
  `external_id == tgbot_{chat}_{msg}`, `channel_id`, `topic`, `sender_id`,
  `message_thread_id`, `text`;
- сообщение без текста и без caption → `None`;
- медиа с caption → берётся caption как text;
- reply → `metadata.reply_to_msg_id` заполнен;
- `from_user is None` (анонимный админ / канал) → `sender_id=None`, не падает.

## Команды для верификации

```bash
python -m pytest tests/test_bot_adapter.py -q

# проверить что normalize не изменён
git diff --stat core/ingest/normalize.py   # ожидаем: пусто
```

## Критерии готовности

- [ ] `bot_message_to_fragment` возвращает Fragment dict с
      `external_id=tgbot_{chat}_{msg}` (НЕ `wndr_tgbot_...`) и заполненным
      `channel_id`.
- [ ] `message_thread_id` в dict совпадает с `message.message_thread_id`
      (для обычной группы — None).
- [ ] Переиспользует `message_to_fragment` (normalize.py не тронут — `git diff` пуст).
- [ ] Пустые/медиа-без-подписи → `None`.
- [ ] `pytest tests/test_bot_adapter.py` зелёный.
