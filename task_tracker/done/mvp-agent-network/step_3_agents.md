# Шаг 3: Агенты — читают канал, пишут в Bus

> Зависит от: шаг 1, шаг 2
> Статус: pending

## Задача

Создать 2 агента Рената, каждый заточен под тему.
Агенты читают приватный канал → выбирают самое важное → пишут в Bus.
Реализация: `client.messages.create()` + промпты из файлов.

## Темы агентов (MVP — 2 агента)

- **agent_one** — AI, агенты, автоматизация, vibe-coding
- **agent_two** — сообщества, дети, образование

## Ключевое: агенты ФИЛЬТРУЮТ, а не репостят

Из 26 сообщений канала агент должен выбрать МАКСИМУМ 2.
Если выбрал 19 из 26 — это не фильтр, это репост. Промпты настроены жёстко:
- Максимум 2 сообщения на агента
- Лучше 0 чем 3
- Критерии отсева: бытовые заметки, реакции, перепосты без мнения

## Файл: `curator/agents.py`

```python
# curator/agents.py
import anthropic
import os
from pathlib import Path

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PROMPTS_DIR = Path(__file__).parent / "prompts"

AGENTS = [
    {"name": "agent_one", "prompt_file": "agent_one.md"},
    {"name": "agent_two", "prompt_file": "agent_two.md"},
]


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def run_agent(agent_name: str, prompt_file: str, messages: list[dict]) -> str | None:
    """Запустить агента с набором сообщений, получить его посты для Bus."""
    system_prompt = _load_prompt(prompt_file)

    messages_text = "\n\n".join(
        f"[{m.get('date', '')[:10]}] {m.get('text', '')[:500]}"
        for m in messages
        if m.get("text")
    )

    if not messages_text:
        return None

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": f"Сообщения из канала за последние сутки:\n\n{messages_text}",
        }],
    )

    result = response.content[0].text.strip()
    if result == "SKIP":
        return None
    return result
```

## Файл: `curator/bus.py` — уже создан, работает

Использует `CURATOR_BOT_TOKEN`, постит в Bus топик с дедупликацией.

## Команды для верификации

```bash
cd c:/Users/renat/projects/wndrverse

# Тест агента на реальных данных
python -c "
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
from curator.reader import get_recent_messages
from curator.agents import run_agent, AGENTS

async def test():
    msgs = await get_recent_messages(os.getenv('PRIVATE_CHANNEL'), period='3d')
    print(f'Сообщений в канале: {len(msgs)}')
    for agent in AGENTS:
        result = run_agent(agent['name'], agent['prompt_file'], msgs)
        print(f'\n{agent[\"name\"]}:')
        print(result or '  SKIP')

asyncio.run(test())
"
```

Ожидаемый результат:
- Из ~26 сообщений каждый агент выбирает 0-2
- Формат: `[renat|tg] оригинальный текст`
- Если агент выбрал >2 — промпт нужно ужесточить

## Критерии готовности

- [ ] `curator/agents.py` создан
- [ ] Промпты читаются из `curator/prompts/agent_one.md` и `agent_two.md`
- [ ] Агент возвращает 0-2 сообщения в формате `[renat|tg] текст` или `None`
- [ ] Бот успешно постит результат в Bus топик
- [ ] В Bus видны сообщения от разных агентов с разными темами
