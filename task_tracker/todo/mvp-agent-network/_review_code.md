# Review: Code

> Reviewer: Claude Code
> Date: 2026-04-11
> Scope: plan files vs реальный код и установленные библиотеки

---

## Критичное (блокирует выполнение)

### 1. `client.beta.managed_agents` не существует в SDK 0.84.0

**Файлы:** `step_3_agents.md` (agents.py псевдокод), `step_4_curator.md` (main.py псевдокод), `agent-template/agent_managed.py` (существующий код)

Установлен `anthropic==0.84.0`. В `beta` есть только: `files`, `messages`, `models`, `skills`.
Атрибута `managed_agents` нет — `AttributeError` при первом вызове.

```python
# Падает:
client.beta.managed_agents.agents.create(...)
client.beta.managed_agents.sessions.create(...)
```

Это блокирует весь шаг 3 (`create_agents()`, `run_agent_session()`) и шаг 4 (`run_agents()`).
Существующий `agent_managed.py` сломан по той же причине — это не новая проблема плана, а уже сломанный код.

**Вариант решения:** обновить SDK до версии с managed agents, либо заменить на обычный `client.messages.create()` без агентов.

---

### 2. `BUS_TOPIC_ID` и `SHOWCASE_TOPIC_ID` — URL-строки, но код делает `int()`

**Файлы:** `step_1_infra.md` (.env шаблон), `step_3_agents.md` (bus.py), `step_4_curator.md` (main.py)

В `.env` шаблоне шага 1:
```
BUS_TOPIC_ID=https://t.me/c/3968221945/3
SHOWCASE_TOPIC_ID=https://t.me/c/3968221945/1
```

Но в bus.py (шаг 3) и main.py (шаг 4):
```python
BUS_TOPIC_ID = int(os.getenv("BUS_TOPIC_ID"))      # ValueError: invalid literal
SHOWCASE_TOPIC_ID = int(os.getenv("SHOWCASE_TOPIC_ID"))  # ValueError: invalid literal
```

Реальные topic ID — это числа в конце URL: `3` и `1` соответственно. `.env` нужно заполнять числом, не URL.

---

## Важное (стоит исправить до начала)

### 3. Несовпадение имён env-переменных: `BUS_CHAT_ID` vs `GROUP_CHAT_ID`

**Файлы:** `CLAUDE.md`, `agent-template/agent_cron.py` vs `step_3_agents.md` (bus.py), `step_4_curator.md` (main.py)

`CLAUDE.md` и `agent_cron.py` используют `BUS_CHAT_ID` (прямой chat_id группы).
Шаги 3–4 вводят новую переменную `GROUP_CHAT_ID` + отдельный `BUS_TOPIC_ID`.

При этом `agent_cron.py` постит в Bus без `message_thread_id` (нет топика), а новый код постит с `message_thread_id`. Это два разных способа: если группа — супергруппа с топиками, `agent_cron.py` будет постить в General, а не в Bus.

Нужно либо: обновить `agent_cron.py` под топиковую архитектуру, либо явно документировать что это разные сценарии.

---

### 4. Два бота в шаге 1, но один `BOT_TOKEN` в шагах 3–4

**Файлы:** `step_1_infra.md` (.env шаблон), `step_3_agents.md` (bus.py), `step_4_curator.md` (main.py)

Шаг 1 создаёт и сохраняет `CURATOR_BOT_TOKEN` и `AGENT_ONE_BOT_TOKEN`.
Шаги 3–4 читают единый `BOT_TOKEN` — нет связи с теми именами. При старте план всё равно потребует понять: какой токен куда идёт. Это не упоминается в переходах между шагами.

---

### 5. `curator/` — не Python-пакет, нет `__init__.py`

**Файлы:** `step_3_agents.md`, `step_4_curator.md`

Папка `curator/` существует, но пуста (только пустая `sources/`). `__init__.py` отсутствует.

Импорты вида `from curator.reader import ...` и `from curator.agents import ...` работают через namespace packages (Python 3.3+) при запуске из корня проекта командой `python -m curator.main`. Но `python curator/main.py` — упадёт, потому что relative imports не сработают.

Команда верификации в шаге 4 правильная (`python -m curator.main`). Команды верификации в шагах 2–3 используют `python -c "from curator.reader import ..."` — это тоже корректно если запускать из корня. Риск невысокий, но `__init__.py` лучше создать явно.

---

## Мелочи (можно по ходу)

### 6. `session.output` — неизвестный формат ответа managed_agents

**Файл:** `step_3_agents.md` (agents.py)

```python
return session.output  # текст для Bus или "SKIP"
```

Если managed_agents когда-то появится — нужно проверить реальную структуру ответа. В существующем `agent_managed.py` возвращается `session.id`, а не `session.output`. Возможно поле называется иначе.

---

### 7. Верификационная команда шага 2 использует абсолютный Windows-путь

**Файл:** `step_2_reader.md`

```bash
cd c:/Users/renat/projects/wndrverse
```

Нормально для текущей машины, но не переносимо. Можно заменить на `.` или убрать — команды в step-файлах должны работать относительно рабочей директории проекта.

---

### 8. `members.json` — поля `tg_channel`, `github` пустые

**Файл:** `members.json`

У единственного участника все источники пустые строки. `agent_cron.py` корректно проверяет `if not TG_CHANNEL` и `if not GITHUB_USERNAME` — пропустит. Но если шаг 5 ожидает данные из источников, тест упадёт тихо (без ошибки, просто 0 постов).

---

## Не найдено проблем

- `Bot.send_message(message_thread_id=...)` — параметр существует в python-telegram-bot 22.5. ✓
- `msg.reactions.results` — `MessageReactions.results: List[ReactionCount]`, у `ReactionCount` есть `.count`. Код `_count_reactions` корректен. ✓
- `TelegramClient` поддерживает `async with` — `__aenter__`/`__aexit__` есть. ✓
- `client.messages.create(...)` в `curator_pick()` — стандартный API, работает в 0.84.0. ✓
- `response.content[0].text` — корректный формат ответа messages API. ✓
- Telethon `client.get_entity("iwacado")` принимает username без `@`. ✓
