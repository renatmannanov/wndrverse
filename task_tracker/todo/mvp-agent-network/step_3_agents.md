# Шаг 3: Агенты — читают канал, пишут в Bus

> Зависит от: шаг 1, шаг 2
> Статус: pending

## Задача

Создать 2-3 агента Рената, каждый заточен под тему.
Агенты читают приватный канал → берут своё → пишут в Bus.
Реализация: Claude Managed Agents (Option B).

## Темы агентов (MVP — 2 агента)

- **agent_ai** — ищет посты про AI, агентов, технологии
- **agent_community** — ищет посты про сообщества, детей, образование

(темы корректируем под реальное содержимое приватного канала)

## Файл: `curator/agents.py`

```python
# curator/agents.py
import anthropic
import os

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

AGENTS_CONFIG = [
    {
        "name": "wndrverse-renat-ai",
        "topic": "AI, агенты, автоматизация, vibe-coding",
        "keywords": ["AI", "агент", "автоматизация", "код", "LLM", "Claude", "GPT"],
    },
    {
        "name": "wndrverse-renat-community",
        "topic": "сообщества, дети, образование, kids coding",
        "keywords": ["сообщество", "дети", "образование", "camp", "make-kid", "WNDR"],
    },
]

AGENT_SYSTEM_PROMPT = """
Ты агент Рената в сети WNDRverse. Твоя тема: {topic}.

Тебе передадут список сообщений из приватного канала Рената.
Твоя задача:
1. Найди 1-2 сообщения которые относятся к твоей теме
2. Напиши короткий репорт для Bus (1-3 предложения)
3. Формат: "[renat|private] {тема}: {суть сообщения}"

Правила:
- Только факты из сообщений, без домыслов
- Если ничего релевантного — ответь "SKIP"
- Максимум 200 символов на сообщение в Bus
- Пиши на русском
""".strip()


def create_agents():
    """Создать агентов в Anthropic cloud (запустить один раз)."""
    agent_ids = {}
    for cfg in AGENTS_CONFIG:
        agent = client.beta.agents.create(
            name=cfg["name"],
            model="claude-sonnet-4-6",
            system_prompt=AGENT_SYSTEM_PROMPT.format(topic=cfg["topic"]),
        )
        agent_ids[cfg["name"]] = agent.id
        print(f"Created: {cfg['name']} → {agent.id}")
    return agent_ids


def run_agent_session(agent_id: str, messages: list[dict]) -> str:
    """Запустить агента с набором сообщений, получить его репорт для Bus."""
    messages_text = "\n\n".join(
        f"[{m['date'][:10]}] {m['text'][:300]}" for m in messages
    )
    session = client.beta.sessions.create(
        agent_id=agent_id,
        input=f"Вот сообщения из канала за последние 24 часа:\n\n{messages_text}",
    )
    return session.output  # текст для Bus или "SKIP"
```

## Файл: `curator/bus.py`

```python
# curator/bus.py — постит в Bus топик
import os
from telegram import Bot

CURATOR_BOT_TOKEN = os.getenv("CURATOR_BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID"))
BUS_TOPIC_ID = int(os.getenv("BUS_TOPIC_ID"))

# Простая дедупликация — храним ID уже опубликованных постов в памяти
_posted_today: set[str] = set()

async def post_to_bus(text: str, key: str | None = None):
    """key — уникальный ключ для дедупликации (например agent_name + date)."""
    if key and key in _posted_today:
        print(f"  Пропускаем дубль: {key}")
        return
    bot = Bot(token=CURATOR_BOT_TOKEN)
    await bot.send_message(
        chat_id=GROUP_CHAT_ID,
        message_thread_id=BUS_TOPIC_ID,
        text=text,
    )
    if key:
        _posted_today.add(key)
```

## Команды для верификации

```bash
# Создать агентов (один раз)
python -c "from curator.agents import create_agents; create_agents()"

# Запустить агентов с тестовыми данными
python -c "
import asyncio, os
from curator.reader import get_recent_messages
from curator.agents import run_agent_session, AGENTS_CONFIG

async def test():
    msgs = await get_recent_messages(os.getenv('PRIVATE_CHANNEL'), hours=48)
    # Симулируем агента ai
    result = run_agent_session('AGENT_ID_HERE', msgs)
    print('Agent output:', result)

asyncio.run(test())
"
```

## Критерии готовности

- [ ] `curator/agents.py` создан
- [ ] `curator/bus.py` создан
- [ ] 2 агента созданы в Anthropic cloud (ID сохранены в .env)
- [ ] Агент получает сообщения и возвращает текст для Bus или "SKIP"
- [ ] Бот успешно постит в Bus топик
- [ ] В Bus видны 2 разных сообщения от агентов с разными темами
