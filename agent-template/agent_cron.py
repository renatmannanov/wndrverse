"""
WNDRverse Agent — Option A: Script + Railway/cron

Run daily via cron:
  0 9 * * * python agent_cron.py

Or deploy to Railway as a cron job.
"""

import asyncio
import os
from telegram import Bot

# ── Config ────────────────────────────────────────────────────────────────────
BUS_CHAT_ID = int(os.getenv("BUS_CHAT_ID", "0"))   # get from community admin
BOT_TOKEN = os.getenv("BOT_TOKEN", "")               # create at @BotFather
MY_USERNAME = os.getenv("MY_USERNAME", "")           # your telegram username

# Your sources — fill in what you have, leave empty string to skip
TG_CHANNEL = os.getenv("TG_CHANNEL", "")            # your public TG channel
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")  # your GitHub username
STRAVA_ID = os.getenv("STRAVA_ID", "")              # your Strava athlete ID
# ──────────────────────────────────────────────────────────────────────────────


async def post_to_bus(bot: Bot, source: str, text: str):
    """Post a structured message to the WNDRverse Bus."""
    message = f"[{MY_USERNAME}|{source}] {text}"
    await bot.send_message(chat_id=BUS_CHAT_ID, text=message)
    print(f"Posted: {message[:80]}...")


async def check_github() -> str | None:
    """Get latest public commit from GitHub."""
    if not GITHUB_USERNAME:
        return None

    import httpx
    url = f"https://api.github.com/users/{GITHUB_USERNAME}/events/public"
    r = httpx.get(url, headers={"Accept": "application/vnd.github.v3+json"})

    if r.status_code != 200:
        return None

    events = r.json()
    push_events = [e for e in events if e["type"] == "PushEvent"]

    if not push_events:
        return None

    latest = push_events[0]
    repo = latest["repo"]["name"]
    commits = latest["payload"]["commits"]
    if not commits:
        return None

    msg = commits[-1]["message"].split("\n")[0]  # first line only
    return f"new commit in {repo}: {msg}"


async def check_tg_channel() -> str | None:
    """Get latest post from your TG channel via RSS."""
    if not TG_CHANNEL:
        return None

    import httpx
    # RSSHub public instance — may be unstable
    url = f"https://rsshub.app/telegram/channel/{TG_CHANNEL}"
    r = httpx.get(url, timeout=10)

    if r.status_code != 200:
        return None

    # Parse first item from RSS
    import re
    titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", r.text)
    if len(titles) > 1:  # first is feed title
        return f"new post: {titles[1][:200]}"

    return None


async def main():
    if not BOT_TOKEN or not BUS_CHAT_ID or not MY_USERNAME:
        print("Error: BOT_TOKEN, BUS_CHAT_ID, MY_USERNAME are required")
        return

    bot = Bot(token=BOT_TOKEN)

    # Check each source and post if there's something new
    github_text = await check_github()
    if github_text:
        await post_to_bus(bot, "github", github_text)

    tg_text = await check_tg_channel()
    if tg_text:
        await post_to_bus(bot, "tg", tg_text)

    # TODO: add strava, instagram sources
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
