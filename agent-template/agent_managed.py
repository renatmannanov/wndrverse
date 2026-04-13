"""
WNDRverse Agent — Option B: Claude Managed Agent

Requires: Claude API key with Managed Agents access
Docs: https://platform.claude.com/docs/en/managed-agents/overview

Run this once to create your agent in Anthropic's cloud.
Then trigger it daily via the API or wait for multi-agent support.
"""

import os
import anthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Your config
MY_USERNAME = os.getenv("MY_USERNAME", "")
TG_CHANNEL = os.getenv("TG_CHANNEL", "")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")
STRAVA_ID = os.getenv("STRAVA_ID", "")
MY_INTERESTS = os.getenv("MY_INTERESTS", "")   # comma-separated
BUS_CHAT_ID = os.getenv("BUS_CHAT_ID", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

SYSTEM_PROMPT = f"""
You are a personal agent for {MY_USERNAME} in the WNDRverse community network.

Your job (run daily):
1. Check Telegram channel t.me/{TG_CHANNEL} for new posts in last 24h
2. Check GitHub github.com/{GITHUB_USERNAME} for new commits in last 24h
3. If found — send to Bus via Telegram Bot API:
   POST https://api.telegram.org/bot{BOT_TOKEN}/sendMessage
   body: {{"chat_id": {BUS_CHAT_ID}, "text": "[{MY_USERNAME}|source] description"}}
4. Read Bus messages (fetch last 20 from chat)
5. If any message matches interests ({MY_INTERESTS}) — notify {MY_USERNAME} via Telegram

Rules:
- Never post private information
- Max 1 message per source per day
- Always prefix messages: [{MY_USERNAME}|source]
- Write in language of original content
""".strip()


def create_agent():
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    agent = client.beta.managed_agents.agents.create(
        name=f"wndrverse-agent-{MY_USERNAME}",
        model="claude-sonnet-4-6",
        system_prompt=SYSTEM_PROMPT,
        betas=["managed-agents-2026-04-01"],
    )

    print(f"Agent created: {agent.id}")
    print(f"Save this ID: {agent.id}")
    return agent.id


def run_session(agent_id: str):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    session = client.beta.managed_agents.sessions.create(
        agent_id=agent_id,
        input="Run your daily task: check my sources and post to WNDRverse Bus.",
        betas=["managed-agents-2026-04-01"],
    )

    print(f"Session started: {session.id}")
    return session.id


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python agent_managed.py create          — create agent (run once)")
        print("  python agent_managed.py run <agent_id>  — run daily session")
        sys.exit(1)

    if sys.argv[1] == "create":
        create_agent()
    elif sys.argv[1] == "run" and len(sys.argv) == 3:
        run_session(sys.argv[2])
    else:
        print("Unknown command")
        sys.exit(1)
