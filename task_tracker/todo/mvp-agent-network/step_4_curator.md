# Шаг 4: Куратор — читает Bus, постит в Showcase

> Зависит от: шаг 3
> Статус: pending

## Задача

Куратор читает сообщения из Bus и решает что постить в Showcase.
Два сценария реализуем параллельно и тестируем какой лучше.

## Сценарий 1: Агенты договариваются сами

Агенты в Bus пишут не только факты, но и "голосуют":
```
[renat-agent-ai|bus] Предлагаю в Showcase: "Ренат написал про multi-agent..."
[renat-agent-community|bus] Поддерживаю. Или это: "..."
```
Куратор смотрит на теги `Предлагаю` / `Поддерживаю` → выбирает победителя.

## Сценарий 2: Куратор решает сам

Куратор — отдельный Claude Managed Agent.
Читает все сообщения из Bus за день → выбирает самое интересное → постит в Showcase.

## Файл: `curator/main.py`

```python
# curator/main.py
import asyncio
import os
from telegram import Bot
from curator.reader import get_recent_messages
from curator.agents import run_agent_session, AGENTS_CONFIG
from curator.bus import post_to_bus
import anthropic

CURATOR_BOT_TOKEN = os.getenv("CURATOR_BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID"))
SHOWCASE_TOPIC_ID = int(os.getenv("SHOWCASE_TOPIC_ID"))
BUS_TOPIC_ID = int(os.getenv("BUS_TOPIC_ID"))
PRIVATE_CHANNEL = os.getenv("PRIVATE_CHANNEL")

# Agent IDs (заполнить после create_agents())
AGENT_IDS = {
    "ai": os.getenv("AGENT_ID_AI"),
    "community": os.getenv("AGENT_ID_COMMUNITY"),
}


async def run_agents(messages: list[dict]) -> list[str]:
    """Запустить всех агентов, собрать их посты для Bus."""
    results = []
    for name, agent_id in AGENT_IDS.items():
        if not agent_id:
            continue
        output = run_agent_session(agent_id, messages)
        if output and output.strip() != "SKIP":
            results.append(output.strip())
            await post_to_bus(output.strip())
    return results


async def curator_pick(bus_messages: list[str]) -> str:
    """Куратор выбирает лучшее из Bus (Сценарий 2)."""
    client = anthropic.Anthropic()
    bus_text = "\n".join(f"- {m}" for m in bus_messages)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"""Вот что агенты написали в Bus сегодня:

{bus_text}

Выбери 1 самое интересное и перепиши для людей (не для агентов).
Формат: живое, короткое, без технических тегов. До 200 символов.
Можешь добавить "Кстати:" или "Сегодня:" в начале."""
        }]
    )
    return response.content[0].text


async def post_to_showcase(text: str):
    bot = Bot(token=CURATOR_BOT_TOKEN)
    await bot.send_message(
        chat_id=GROUP_CHAT_ID,
        message_thread_id=SHOWCASE_TOPIC_ID,
        text=text,
    )


async def main():
    print("1. Читаем приватный канал...")
    messages = await get_recent_messages(PRIVATE_CHANNEL, hours=24)
    print(f"   Найдено сообщений: {len(messages)}")

    print("2. Запускаем агентов...")
    bus_posts = await run_agents(messages)
    print(f"   Агенты написали в Bus: {len(bus_posts)} сообщений")

    if not bus_posts:
        print("   Агенты ничего не нашли. Выход.")
        return

    print("3. Куратор выбирает для Showcase...")
    showcase_text = await curator_pick(bus_posts)
    print(f"   Текст: {showcase_text}")

    print("4. Постим в Showcase...")
    await post_to_showcase(showcase_text)
    print("   Готово!")


if __name__ == "__main__":
    asyncio.run(main())
```

## Команды для верификации

```bash
cd c:/Users/renat/projects/wndrverse

# Запустить полный цикл
python -m curator.main

# Проверить что пост появился в Showcase топике
# (открыть Telegram и посмотреть)
```

## Критерии готовности

- [ ] `curator/main.py` создан
- [ ] Сценарий 2 работает: куратор читает Bus → постит в Showcase
- [ ] Сценарий 1 задокументирован (голосование в Bus) — даже если не реализован
- [ ] Showcase топик: видно красиво оформленное сообщение
- [ ] Нет дублей: если агент не нашёл ничего — молчит
