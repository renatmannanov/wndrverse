# Contributing to WNDRverse

## Ways to contribute

### Add yourself as a member
Edit `members.json`, open a PR. That's it.

### Add a new source
Want to pull from a new platform (LinkedIn, YouTube, Letterboxd...)?
1. Add a file to `agent-template/sources/your_source.py`
2. Update `members.json` schema with the new field
3. Update `curator/sources/` to support reading it
4. Open a PR with a short description

### Improve the curator
The curator logic lives in `curator/matcher.py` and `curator/publisher.py`.
If you have a better matching algorithm or post format — PRs welcome.

### Run it for your own community
Fork the repo, change `members.json`, deploy your own curator.
If you build something interesting on top — tell us.

## Message format (Bus protocol)

All agent messages to the Bus must follow this format:
```
[author|source] text

Examples:
[vasya|github] new commit: avito parser without auth
[masha|tg] post about vibe-coding for non-techies
[petya|strava] 10km in 52min, Almaty
```

The curator parses `[author|source]` to know who and where. Free-form text after that.

## Code style

- Python 3.10+
- No frameworks for simple scripts — just stdlib + httpx + python-telegram-bot
- Keep agent-template minimal — it's the entry point for non-technical people

## Questions

Open an issue or write in the community channel.
