# Plan: wndrverse — passive window into each other's lives

> Status: in progress (MVP infra done, next: test-stand)
> Priority: medium
> Depends on: wndr-contacts-parsing (Phase 0)
> Completed sub-plans: done/mvp-agent-network/

## The Problem

Renat (and many others) suck at maintaining social connections. The pattern:
- Meet cool people in a community/event
- Promise to stay in touch
- Forget in 2 weeks
- Repeat

WNDR community (100 people, 2 seasons since Sep 2025) is ending mid-April 2026. Without a "glue", everyone disperses and the connections die.

## Why "just subscribe to everyone" doesn't work

You CAN follow everyone on Instagram, subscribe to all TG channels, add to contacts. But:

1. **Noise kills attention** — 100 channels = 100 unread badges you ignore. The problem isn't access to content, it's the inability to process it.
2. **No context** — you see Vasya's post about AI, but don't realize Masha posted about the same thing. There's no cross-pollination.
3. **No bridge to action** — you see a story and... scroll past. There's no nudge to actually connect.
4. **Passive ≠ zero-effort subscription** — subscribing is passive consumption. What we need is passive *connection*.

## Real example: why this matters

A WNDR member posted about her journey into vibe-coding as a non-technical person ("гуманитарий"). She built an AI course for her kid, the kid (10 years old) now vibe-codes multiplication games and presented at an MGIMO forum. She set up her own OpenClaw, created bots, designed a brand — all without a programming background.

Renat has `make-kid` — a summer coding camp for children, teaching them to build with AI. He's also a non-programmer who vibe-codes 8+ projects. The overlap is massive.

**Without wndrverse:** Renat might scroll past this post in a busy group chat. Two people in the same community, working on the same problem, never connect.

**With wndrverse:** The bot sees the match — "Masha writes about AI education for kids + vibe-coding for non-techies. Renat, you have make-kid and 8 vibe-coded projects. Maybe talk?"

We call it "being in the right place at the right time." But it's not luck — it's attention we don't have. wndrverse creates more of these "right times and right places" systematically.

## The Idea: Curated, not aggregated

**wndrverse** is NOT another feed. It's a curator-bot that:

- Monitors TG channels (and optionally Instagram) of community members
- Picks ONE interesting thing per day and shares it in a common channel
- Adds context: "Petya from WNDR writes about X — btw Masha was thinking about the same thing last week"
- Periodically matches people: "You and @vasya both posted about running this month"
- Random coffee: weekly random pair suggestion

**Key principle:** 1 curated post/day > 100 stories nobody watches.

The bot is the "friend who reads everything and tells you the interesting bits."

## What makes this different from existing tools

| Existing | wndrverse difference |
|----------|---------------------|
| Personal CRM (Fabriq, Monica) | Those track YOUR effort. We track THEIR content passively. |
| Channel aggregators (Feedgram) | Those dump everything. We curate 1/day with context. |
| Random coffee bots | Those are standalone. We combine with content context. |
| Instagram/TG subscriptions | That's raw feed. We add WHY you should care. |
| Cappuccino (audio updates) | Requires active participation. We work with existing content. |

## Architecture (MVP)

```
[TG channels of members] → Parser (Telethon)
                                ↓
                          [Content DB]
                                ↓
                    [Curator bot] — selects 1 post/day
                                ↓
                    [wndrverse TG channel] — members subscribe
```

### Stack
- **Telethon** (userbot) — read members' public TG channels
- **Python + cron** — daily curator job
- **GPT/Claude API** — summarize, find connections between posts
- **Telegram Bot API** — post to the wndrverse channel
- **PostgreSQL** (shared with ayda-think) — store posts + member profiles

### Instagram integration (optional, Phase 2)
- RSS bridges (RSSHub) for public profiles — unstable but free
- OR: members manually forward interesting posts to bot
- OR: Apify/PhantomBuster for monitoring — paid but reliable

## Steps

| # | Step | Status | Phase |
|---|------|--------|-------|
| 1 | Define MVP scope and channel format | pending | discovery |
| 2 | Set up wndrverse TG channel + bot | pending | MVP |
| 3 | Collect TG channel links from WNDR members | pending | MVP (from Phase 0 data) |
| 4 | Build channel parser — fetch latest posts | pending | MVP |
| 5 | Build curator logic — select 1 best post/day | pending | MVP |
| 6 | Deploy daily cron job | pending | MVP |
| 7 | Invite WNDR members, test for 2 weeks | pending | MVP |
| 8 | Add interest matching ("you both write about X") | pending | v2 |
| 9 | Add random coffee pairing | pending | v2 |
| 10 | Instagram integration (optional) | pending | v2 |
| 11 | GitHub integration — interesting commits | pending | v2 |
| 12 | Strava integration — running/sports activity | pending | v2 |

## Step details

### Step 1: Define MVP scope and channel format

Decide:
- Channel name, description, positioning (what do members see when invited?)
- Post format: just forward? Summary + link? Quote + context?
- Frequency: 1/day? 3/week?
- "Goodbye message" for WNDR — how to pitch this to the community

**Done when:** written post format template + invite message draft

### Step 2: Set up wndrverse TG channel + bot

- Create TG channel "wndrverse" (or name TBD)
- Create bot via @BotFather with posting rights
- Bot can post to channel but members can also discuss (linked group?)

**Done when:** channel exists, bot can post to it

### Step 3: Collect TG channel links from WNDR members

Use data from wndr-contacts-parsing plan.
Filter members who have public TG channels.
Result: list of channels to monitor.

**Done when:** JSON list of member channels with metadata

### Step 4: Build channel parser

Telethon script that:
- Reads latest posts from each member's channel (last 24-48h)
- Saves to DB: text, date, author, media type, engagement (views/reactions)
- Runs on schedule (every 6h or daily)

**Done when:** parser runs, DB has posts from member channels

### Step 5: Build curator logic

Select the "post of the day":
- Filter: skip reposts, ads, very short posts
- Score: engagement + recency + diversity (don't show same person twice in a row)
- AI summary: 2-3 sentence intro in Russian
- Format and post to wndrverse channel

Simple v1: random post from a random member's channel (no AI needed).
v1.5: AI picks the most interesting one.

**Done when:** bot posts 1 curated message/day to the channel

### Step 6: Deploy

- Railway or simple VPS cron
- Health monitoring (reuse telegram-gather patterns)

**Done when:** runs autonomously for 3+ days without intervention

### Step 7: Invite and test

- Write "goodbye + hello wndrverse" message for WNDR group
- Invite members
- Track: how many join, do they read, do they react, does anyone DM someone because of a post?

**Done when:** 2 weeks of data, decision on whether to continue

## Success criteria for MVP

- 30+ WNDR members join the channel
- Posts get 20+ views consistently
- At least 3 DM conversations happen because of a wndrverse post (self-reported or observable)
- Renat himself discovers something about a member he didn't know

## Open questions

- [ ] Should this be a channel (broadcast) or a group (discussion)?
- [ ] Do we need member consent to repost their channel content?
- [ ] How to handle members without TG channels? (Instagram only, or skip?)
- [ ] Can this be open-sourced so members contribute via vibe-coding?
- [ ] How does ralph-loop fit into development process?
- [ ] GitHub as a content source — many WNDR members vibe-code, commits are content too
- [ ] Strava integration — sports activity as a signal (Renat runs but doesn't post about it)
- [ ] Pitch message for WNDR group — short, compelling, "I'm leaving but here's a thing"
- [ ] Alternative model: not a channel, but a personal agent that monitors GROUP CHATS
  - Real data: WNDR has 8 sub-groups, 1000+ unread messages across them
  - Plus other communities: vibe-coding group (228 people), free community (408 people, 269 unread)
  - Nobody reads all this. The interesting stuff (like today's AI-for-kids offering) gets lost
  - Agent passively reads groups, finds messages matching YOUR specific interests
  - NOT "here's a summary" (bullshit at scale) — but "here are 2 messages out of 1000 that match your topics"
  - Matching via token similarity / RAG (same approach as fraud-sharing uses for fuzzy word matching)
  - User defines interest topics: e.g. "обучение детей школьников", "производство напитков"
  - Narrow niche interests are MORE valuable — broad topics (vibe-coding) you can find yourself
  - This is closer to telegram-gather's existing capabilities (fetch_chat + matching)
  - Could be a separate mode: "community listener" vs "channel curator"

## Research: existing tools and analogues

See: `internal/projects/wndrverse/research.md`

Key finding: no single tool combines content curation + people matching + community glue.
Closest in spirit: **Cappuccino** (passive audio updates from friends).
Closest in tech: **telegram-digest-bot** (GitHub) + **Random_Coffee** (GitHub).
