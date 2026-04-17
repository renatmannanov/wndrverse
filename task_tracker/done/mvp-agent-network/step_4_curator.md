# Шаг 4: Куратор — читает Bus, постит в Showcase

> Зависит от: шаг 3
> Статус: pending

## Задача

Куратор получает сообщения агентов из Bus и решает что постить в Showcase.
MVP: Сценарий 2 (куратор решает сам). Сценарий 1 — stretch goal.

## Логика куратора

Промпт в `curator/prompts/curator.md`:
1. Ищет **пересечения** между участниками (общие темы, идеи)
2. Если пересечение есть → "@участник1 и @участник2 оба думают про X"
3. Если нет пересечений → выбирает 1 самый интересный оригинал
4. Без обработки текста — показывает оригиналы
5. На русском, живо и коротко

> Для MVP с 1 участником пересечений не будет — куратор просто выберет лучшее.
> Когда добавим участников — логика пересечений заработает.

## Файл: `curator/main.py`

```python
# curator/main.py
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from curator.reader import get_recent_messages
from curator.agents import run_agent, AGENTS
from curator.bus import post_to_bus
from curator.showcase import post_to_showcase
import anthropic

PRIVATE_CHANNEL = os.getenv("PRIVATE_CHANNEL")

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
CURATOR_PROMPT = (Path(__file__).parent / "prompts" / "curator.md").read_text(encoding="utf-8")


async def run_agents(messages: list[dict]) -> list[str]:
    """Запустить всех агентов, собрать их посты для Bus."""
    results = []
    for agent in AGENTS:
        output = run_agent(agent["name"], agent["prompt_file"], messages)
        if output:
            results.append(output)
            await post_to_bus(output, key=f"{agent['name']}_{messages[0].get('date', '')[:10]}")
            print(f"  {agent['name']}: posted to Bus")
        else:
            print(f"  {agent['name']}: SKIP")
    return results


def curator_pick(bus_messages: list[str]) -> str:
    """Куратор выбирает лучшее из Bus (Сценарий 2)."""
    bus_text = "\n".join(bus_messages)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=CURATOR_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Вот что агенты написали в Bus сегодня:\n\n{bus_text}",
        }],
    )
    return response.content[0].text.strip()


async def main():
    print("1. Читаем приватный канал...")
    messages = await get_recent_messages(PRIVATE_CHANNEL, period="1d")
    print(f"   Найдено сообщений: {len(messages)}")

    if not messages:
        print("   Нет сообщений. Выход.")
        return

    print("2. Запускаем агентов...")
    bus_posts = await run_agents(messages)
    print(f"   Агенты написали в Bus: {len(bus_posts)} сообщений")

    if not bus_posts:
        print("   Агенты ничего не нашли. Выход.")
        return

    print("3. Куратор выбирает для Showcase...")
    showcase_text = curator_pick(bus_posts)
    print(f"   Текст: {showcase_text}")

    print("4. Постим в Showcase...")
    await post_to_showcase(showcase_text)
    print("   Готово!")


if __name__ == "__main__":
    asyncio.run(main())
```

## Почему куратор не перечитывает Bus из Telegram

В MVP `main.py` запускает агентов и куратора в одном процессе.
Агенты возвращают текст → куратор получает его в переменной `bus_posts`.
Перечитывать Bus из Telegram не нужно — данные уже в памяти.

В будущем (когда агенты и куратор работают асинхронно) — добавим чтение Bus
через Telegram Bot API или расширим telegram-gather для поддержки topic_id.

## Команды для верификации

```bash
cd c:/Users/renat/projects/wndrverse

# Полный цикл
python -m curator.main

# Проверить результат в Telegram:
# Bus: 1-4 сообщения от агентов (формат [renat|tg] текст)
# Showcase: 1 красивый пост от куратора
```

## Критерии готовности

- [ ] `curator/main.py` создан
- [ ] Куратор использует промпт из `curator/prompts/curator.md`
- [ ] Сценарий 2 работает: агенты → Bus → куратор → Showcase
- [ ] Showcase: читабельное сообщение для людей
- [ ] Нет дублей: дедупликация по ключу agent_name + date
- [ ] Сценарий 1 задокументирован как stretch goal
