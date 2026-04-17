# Шаг 2: Reader — получаем сообщения через telegram-gather API

> Зависит от: шаг 1
> Статус: done

## Задача

Написать `curator/reader.py` — получает сообщения из канала через HTTP API telegram-gather.
Никакого Telethon в wndrverse. Никакой второй сессии.

## Почему так

telegram-gather уже запущен на Railway 24/7 с авторизованным userbot.
У него есть HTTP API: `GET /api/messages?chat=<name>&period=1d`.
wndrverse просто делает httpx запрос — всё.

## Что делаем

Файлы: `curator/__init__.py` (пустой) + `curator/reader.py`

```python
# curator/reader.py
import httpx
import os

TG_GATHER_URL = os.getenv("TG_GATHER_URL")
TG_GATHER_API_KEY = os.getenv("TG_GATHER_API_KEY")


async def get_recent_messages(channel: str, period: str = "1d", limit: int = 100) -> list[dict]:
    """
    Получить сообщения из канала через telegram-gather API.

    Возвращает список: {id, date, sender, text, reply_to}
    """
    headers = {"Authorization": f"Bearer {TG_GATHER_API_KEY}"}
    params = {"chat": channel, "period": period, "limit": limit}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{TG_GATHER_URL}/api/messages",
            headers=headers,
            params=params,
        )
        resp.raise_for_status()
        return resp.json().get("messages", [])
```

## Дополнения к .env

```
TG_GATHER_URL=https://YOUR_RAILWAY_APP.railway.app
TG_GATHER_API_KEY=YOUR_TG_GATHER_API_KEY
```

## Команды для верификации

```bash
cd c:/Users/renat/projects/wndrverse

# Проверить что API отвечает
python -c "
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
from curator.reader import get_recent_messages

async def test():
    msgs = await get_recent_messages('iwacado', period='7d', limit=10)
    print(f'Found {len(msgs)} messages')
    for m in msgs[:3]:
        print(f'  [{m[\"date\"][:10]}] {m[\"sender\"]}: {m[\"text\"][:80]}')

asyncio.run(test())
"
```

## Критерии готовности

- [x] `curator/__init__.py` создан (пустой)
- [x] `curator/reader.py` создан
- [x] `.env` дополнен: `TG_GATHER_URL` и `TG_GATHER_API_KEY`
- [x] Тест возвращает > 0 сообщений из канала `iwacado`
- [x] Формат ответа: список с полями `id`, `date`, `sender`, `text`
