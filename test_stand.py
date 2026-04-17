"""
WNDRverse Test Stand — interactive orchestrator.

Runs 3 phases:
  1. Each agent filters the same channel messages through their prompt
  2. Agents see each other's Bus posts (b2b) and can reply
  3. Curator picks the best / finds a match → Showcase

Human provides responses (simulating Claude API), script posts from the right bot.
"""
import argparse
import asyncio
import json
import os
import random
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Import project modules
from curator.reader import get_recent_messages
from curator.bus import post_to_bus, reply_in_bus
from curator.showcase import post_to_showcase


def load_members() -> dict:
    with open("members.json", encoding="utf-8") as f:
        return json.load(f)


def load_prompt(member: dict) -> str:
    path = member["prompt_file"]
    with open(path, encoding="utf-8") as f:
        return f.read()


def get_token(member: dict) -> str:
    return os.getenv(member["agent_token_env"])


def save_run_log(log: dict):
    runs_dir = Path("data/runs")
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = runs_dir / f"{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"\nLog saved: {path}")


async def phase_1(members: list, messages: list) -> list:
    """Phase 1: Each agent filters channel messages through their prompt."""
    bus_posts = []
    order = list(members)
    random.shuffle(order)

    print(f"\n{'='*60}")
    print("PHASE 1: Agent filtering")
    print(f"Agent order: {[m['name'] for m in order]}")
    print(f"{'='*60}")

    for member in order:
        prompt = load_prompt(member)
        token = get_token(member)

        print(f"\n{'-'*60}")
        print(f"AGENT: {member['name']} (@{member['agent_bot']})")
        print(f"INTERESTS: {', '.join(member['interests'])}")
        print(f"\n--- PROMPT ---")
        print(prompt)
        print(f"--- END PROMPT ---")
        print(f"\nCHANNEL MESSAGES ({len(messages)}):")
        for i, m in enumerate(messages, 1):
            text = (m.get("text") or "").replace("\n", " ")
            date = (m.get("date") or "")[:10]
            sender = m.get("sender") or "?"
            print(f"  {i}. [{date}] @{sender}: {text[:120]}")

        print(f"\nWhat does {member['name']}'s agent post to Bus? (or SKIP)")
        response = input("> ").strip()

        if response.upper() == "SKIP":
            bus_posts.append({
                "member": member["name"],
                "bot": member["agent_bot"],
                "action": "skip",
            })
            print(f"  -> {member['name']} skipped")
        else:
            msg = await post_to_bus(response, bot_token=token)
            if msg:
                bus_posts.append({
                    "member": member["name"],
                    "bot": member["agent_bot"],
                    "action": "post",
                    "text": response,
                    "message_id": msg.message_id,
                })
                print(f"  -> Posted from @{member['agent_bot']} (msg_id={msg.message_id})")
            else:
                print(f"  -> Failed to post (duplicate?)")
                bus_posts.append({
                    "member": member["name"],
                    "bot": member["agent_bot"],
                    "action": "failed",
                    "text": response,
                })

    return bus_posts


async def phase_2(members: list, bus_posts: list) -> list:
    """Phase 2: Agents see each other's Bus posts and can reply (b2b)."""
    replies = []
    actual_posts = [p for p in bus_posts if p.get("message_id")]

    if not actual_posts:
        print(f"\n{'='*60}")
        print("PHASE 2: No posts in Bus — skipping b2b phase")
        return replies

    print(f"\n{'='*60}")
    print("PHASE 2: b2b replies")
    print(f"{'='*60}")
    print("\nBUS contains:")
    for i, p in enumerate(actual_posts, 1):
        print(f"  {i}. [@{p['bot']}] {p['text'][:120]}")

    order = list(members)
    random.shuffle(order)
    print(f"\nAgent order: {[m['name'] for m in order]}")

    for member in order:
        # Show only OTHER agents' posts
        others = [(i, p) for i, p in enumerate(actual_posts, 1)
                  if p["member"] != member["name"]]
        if not others:
            continue

        prompt = load_prompt(member)
        token = get_token(member)

        print(f"\n{'-'*60}")
        print(f"AGENT: {member['name']} (@{member['agent_bot']}) sees Bus:")
        for i, p in others:
            print(f"  {i}. [@{p['bot']}] {p['text'][:120]}")

        print(f"\n--- PROMPT ---")
        print(prompt)
        print(f"--- END PROMPT ---")

        print(f"\n{member['name']} reacts? (post number or SKIP)")
        choice = input("> ").strip()

        if choice.upper() == "SKIP":
            print(f"  -> {member['name']} skipped")
            continue

        try:
            post_idx = int(choice) - 1
            target = actual_posts[post_idx]
        except (ValueError, IndexError):
            print(f"  -> Invalid number, skipping")
            continue

        print(f"  Reply text:")
        reply_text = input("  > ").strip()
        if not reply_text:
            continue

        msg = await reply_in_bus(
            reply_text,
            reply_to_message_id=target["message_id"],
            bot_token=token,
        )
        replies.append({
            "agent": member["name"],
            "bot": member["agent_bot"],
            "reply_to": target["message_id"],
            "reply_to_agent": target["member"],
            "text": reply_text,
            "message_id": msg.message_id,
        })
        print(f"  -> Reply from @{member['agent_bot']} to @{target['bot']} (msg_id={msg.message_id})")

    return replies


async def phase_3(bus_posts: list, replies: list):
    """Phase 3: Curator picks the best / finds a match → Showcase."""
    actual_posts = [p for p in bus_posts if p.get("message_id")]

    print(f"\n{'='*60}")
    print("PHASE 3: Curator -> Showcase")
    print(f"{'='*60}")

    if not actual_posts and not replies:
        print("\nNothing in Bus today. Curator has nothing to work with.")
        print("SKIP Showcase? (or type a message)")
        response = input("> ").strip()
        if response.upper() == "SKIP":
            return None
    else:
        print("\nBus summary:")
        for p in actual_posts:
            print(f"  [@{p['bot']}] {p['text'][:120]}")
        if replies:
            print("\nReplies:")
            for r in replies:
                print(f"  [@{r['bot']}] -> @{bus_posts_by_id(bus_posts, r['reply_to'])}: {r['text'][:120]}")

        curator_prompt_path = "curator/prompts/curator.md"
        if os.path.exists(curator_prompt_path):
            with open(curator_prompt_path) as f:
                print(f"\n--- CURATOR PROMPT ---")
                print(f.read())
                print(f"--- END PROMPT ---")

        print("\nWhat does the curator post to Showcase? (or SKIP)")
        response = input("> ").strip()

    if response.upper() == "SKIP":
        return None

    await post_to_showcase(response)
    print(f"  -> Posted to Showcase")
    return response


def bus_posts_by_id(bus_posts, msg_id):
    for p in bus_posts:
        if p.get("message_id") == msg_id:
            return p["bot"]
    return "?"


async def main():
    parser = argparse.ArgumentParser(description="WNDRverse Test Stand")
    parser.add_argument("--period", default="1d", help="Message fetch period (e.g. 1d, 7d, 30d)")
    args = parser.parse_args()

    config = load_members()
    source = config["source_channel"]
    members = config["members"]

    print(f"WNDRverse Test Stand")
    print(f"Source channel: {source}")
    print(f"Members: {[m['name'] for m in members]}")
    print(f"Period: {args.period}")
    print(f"Fetching messages from @{source}...")

    messages = await get_recent_messages(source, period=args.period)
    print(f"Got {len(messages)} messages\n")

    if not messages:
        print("No messages found. Try a longer --period (e.g. --period 30d)")
        return

    # Phase 1
    bus_posts = await phase_1(members, messages)

    # Phase 2
    replies = await phase_2(members, bus_posts)

    # Phase 3
    showcase_text = await phase_3(bus_posts, replies)

    # Save run log
    log = {
        "timestamp": datetime.now().isoformat(),
        "source_channel": source,
        "source_messages_count": len(messages),
        "phase_1": [p for p in bus_posts],
        "phase_2": replies,
        "phase_3": {"showcase_text": showcase_text},
    }
    save_run_log(log)

    print(f"\n{'='*60}")
    print("DONE!")
    actual = [p for p in bus_posts if p.get("message_id")]
    print(f"  Bus posts: {len(actual)}")
    print(f"  Replies: {len(replies)}")
    print(f"  Showcase: {'yes' if showcase_text else 'no'}")


if __name__ == "__main__":
    asyncio.run(main())
