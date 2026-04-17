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

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(
            f"{TG_GATHER_URL}/api/messages",
            headers=headers,
            params=params,
        )
        resp.raise_for_status()
        return resp.json().get("messages", [])
