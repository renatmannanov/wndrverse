"""
Setup script for WNDRverse test stand bots.

Usage:
  1. Create bots via Telegram links (see step_1_bots.md)
  2. Add them to the group as admins
  3. Run: python setup_bots.py get-tokens
  4. Run: python setup_bots.py rename-renat
  5. Run: python setup_bots.py check
"""
import asyncio
import sys
import os
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

CURATOR_BOT_TOKEN = os.getenv("CURATOR_BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))


async def get_managed_token(bot_user_id: int) -> str:
    """Get token for a managed bot via parent bot."""
    bot = Bot(token=CURATOR_BOT_TOKEN)
    # getManagedBotToken — parameter is user_id (not bot_id)
    result = await bot.get_managed_bot_token(user_id=bot_user_id)
    return result.token


async def check_all():
    """Check all 3 bots respond to getMe."""
    tokens = {
        "AGENT_RENAT_TOKEN": os.getenv("AGENT_RENAT_TOKEN") or os.getenv("AGENT_ONE_BOT_TOKEN"),
        "AGENT_VASYA_TOKEN": os.getenv("AGENT_VASYA_TOKEN"),
        "AGENT_MASHA_TOKEN": os.getenv("AGENT_MASHA_TOKEN"),
    }
    for name, token in tokens.items():
        if not token:
            print(f"  MISSING: {name} — not set in .env")
            continue
        try:
            bot = Bot(token=token)
            me = await bot.get_me()
            print(f"  OK: {name} → @{me.username} (id: {me.id})")
        except Exception as e:
            print(f"  FAIL: {name} → {e}")


async def rename_renat():
    """Rename @test_wndr_agentbot to 'Renat Agent'."""
    token = os.getenv("AGENT_RENAT_TOKEN") or os.getenv("AGENT_ONE_BOT_TOKEN")
    if not token:
        print("No AGENT_RENAT_TOKEN or AGENT_ONE_BOT_TOKEN in .env")
        return
    bot = Bot(token=token)
    await bot.set_my_name(name="Renat Agent")
    me = await bot.get_me()
    print(f"Renamed: @{me.username} → '{me.first_name}'")


async def get_tokens():
    """Interactive: get tokens for newly created managed bots."""
    print("Enter bot user IDs (from @BotFather or getUpdates).")
    print("You can find them by sending /start to each bot and checking the update.\n")

    for name in ["VASYA", "MASHA"]:
        bot_id_str = input(f"  Bot ID for {name} (or SKIP): ").strip()
        if bot_id_str.upper() == "SKIP":
            continue
        try:
            bot_id = int(bot_id_str)
            token = await get_managed_token(bot_id)
            print(f"  AGENT_{name}_TOKEN={token}")
            print(f"  → Add this to .env\n")
        except Exception as e:
            print(f"  Error: {e}\n")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"

    if cmd == "check":
        asyncio.run(check_all())
    elif cmd == "rename-renat":
        asyncio.run(rename_renat())
    elif cmd == "get-tokens":
        asyncio.run(get_tokens())
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python setup_bots.py [check|rename-renat|get-tokens]")
