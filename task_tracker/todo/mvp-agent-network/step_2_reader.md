# Шаг 2: Reader — Telethon читает приватный канал

> Зависит от: шаг 1
> Статус: pending

## Задача

Написать reader.py — Telethon userbot читает приватный канал Рената
и отдаёт последние N сообщений с метаданными.

## Что делаем

Файлы: `curator/__init__.py` (пустой) + `curator/reader.py`

```python
# curator/reader.py
from telethon import TelegramClient
from telethon.tl.types import Message
from datetime import datetime, timedelta
import os

API_ID = os.getenv("TG_API_ID")
API_HASH = os.getenv("TG_API_HASH")
SESSION = "wndrverse_reader"

async def get_recent_messages(channel: str, hours: int = 24) -> list[dict]:
    """
    Читает сообщения из канала за последние N часов.
    Возвращает список: {id, text, date, views, forwards, reactions}
    """
    async with TelegramClient(SESSION, API_ID, API_HASH) as client:
        entity = await client.get_entity(channel)
        since = datetime.utcnow() - timedelta(hours=hours)
        messages = []
        async for msg in client.iter_messages(entity, limit=50):
            if msg.date.replace(tzinfo=None) < since:
                break
            if msg.text:
                messages.append({
                    "id": msg.id,
                    "text": msg.text,
                    "date": msg.date.isoformat(),
                    "views": msg.views or 0,
                    "forwards": msg.forwards or 0,
                    "reactions": _count_reactions(msg),
                })
        return messages

def _count_reactions(msg: Message) -> int:
    if not msg.reactions:
        return 0
    return sum(r.count for r in msg.reactions.results)
```

## Авторизация Telethon (первый запуск)

Telethon требует интерактивной авторизации через номер телефона + OTP:

```bash
cd c:/Users/renat/projects/wndrverse
python -c "
from telethon.sync import TelegramClient
import os
client = TelegramClient('wndrverse_reader', os.getenv('TG_API_ID'), os.getenv('TG_API_HASH'))
client.start()  # спросит номер телефона и OTP код из Telegram
print('Авторизация успешна, сессия сохранена')
client.disconnect()
"
```

После этого появится файл `wndrverse_reader.session` — повторная авторизация не нужна.

## Дополнения к .env

```
TG_API_ID=...      # получить на my.telegram.org
TG_API_HASH=...    # получить на my.telegram.org
```

## Создать `curator/__init__.py`

```bash
# Пустой файл — нужен чтобы curator был Python-пакетом
echo "" > c:/Users/renat/projects/wndrverse/curator/__init__.py
```

## Команды для верификации

```bash
cd c:/Users/renat/projects/wndrverse

python -c "
import asyncio
from curator.reader import get_recent_messages
import os

async def test():
    msgs = await get_recent_messages(os.getenv('PRIVATE_CHANNEL'), hours=48)
    print(f'Found {len(msgs)} messages')
    for m in msgs[:3]:
        print(m['text'][:80])

asyncio.run(test())
"
```

## Критерии готовности

- [ ] `curator/__init__.py` создан (пустой)
- [ ] `curator/reader.py` создан
- [ ] Telethon сессия авторизована (`.session` файл есть)
- [ ] Тест возвращает > 0 сообщений из приватного канала `iwacado`
- [ ] Метаданные (views, reactions) читаются корректно
