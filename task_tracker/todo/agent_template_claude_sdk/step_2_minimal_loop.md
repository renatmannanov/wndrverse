# Step 2: Minimal loop

> Status: done (код), smoke-тест откладывается до развёртки на VPS
> Depends on: step_1

## Цель шага

Минимальный рабочий скрипт `agents/claude/main.py`, который при запуске:

1. Стартует Claude Agent SDK-сессию через OAuth (Max-подписка владельца)
2. Через своего TG-бота читает новые сообщения из Bus за последние 24 часа
3. Сохраняет их в локальную SQLite, помечает прочитанные
4. Завершается

**Ничего больше.** Никакого фильтра, никакого дайджеста, никакой записи обратно в Bus. Только "прочитал → сохранил → ушёл".

## Локация файлов (новая структура)

```
agents/
└── claude/
    ├── main.py              ← entrypoint
    ├── bus_client.py        ← read-only часть на этом шаге, write на step_4
    ├── state_db.py          ← обвязка над SQLite
    ├── .local/
    │   └── state.db         ← локальная SQLite, не в git
    ├── .env.example         ← создать на этом шаге
    └── README.md            ← создать заглушку, наполнить на step_5
```

`.gitignore` обновить: добавить `agents/*/.local/`, `agents/*/.env`.

## Конфиг (`.env` агента Клода — внутри `agents/claude/.env`)

**Принцип:** каждый агент хранит свой `.env` в своей папке. Никаких общих корневых файлов на этом этапе. Дубли (например `GROUP_CHAT_ID` будет повторяться в 3 файлах) принимаем сознательно для чистоты изоляции — устраним позже когда стабилизируется.

```
# Telegram (свой бот для агента Клода)
AGENT_CLAUDE_TOKEN=...      # токен бота от @BotFather
GROUP_CHAT_ID=-1003968221945   # Telegram supergroup
BUS_TOPIC_ID=3                 # топик Bus

# Кого этот агент представляет
OWNER_USERNAME=ray_mann        # из members.json — agent_pick/agent_summary будут от его имени

# Опциональный Telethon (для шага после MVP)
# TG_API_ID=...
# TG_API_HASH=...
# TG_TELETHON_SESSION=.local/telethon.session

# Claude Agent SDK — НИКАКОГО ANTHROPIC_API_KEY здесь.
# Аутентификация через `claude login`, OAuth-сессия живёт в стандартном месте Claude Code.
```

**Жёсткие правила для Клода:**
1. **`ANTHROPIC_API_KEY` НЕ должен быть в `.env` Клода.** Если он там окажется — SDK может уйти через API биллинг вместо Max-подписки. Дополнительная защита в `main.py`: `os.environ.pop("ANTHROPIC_API_KEY", None)` перед инициализацией SDK (на случай если переменная пришла из системного env).
2. **Клод не читает `.env` других агентов и наоборот.** Никаких `load_dotenv("../openclaw/.env")`.
3. **Клод не импортирует Python-модули из `agents/openclaw/`, `agents/hermes/`, `curator/`.** Только из `agents/claude/`.

## Схема SQLite (`agents/claude/.local/state.db`)

Минимальная, без переусложнения:

```sql
CREATE TABLE IF NOT EXISTS bus_messages (
    tg_message_id INTEGER PRIMARY KEY,    -- ID сообщения в TG
    posted_at     TEXT NOT NULL,           -- ISO timestamp
    author        TEXT NOT NULL,           -- из [author|source]
    source        TEXT NOT NULL,           -- из [author|source]
    text          TEXT NOT NULL,           -- тело
    raw           TEXT NOT NULL,           -- полный текст сообщения "[a|s] text"
    seen_at       TEXT NOT NULL            -- когда наш агент впервые увидел
);

CREATE INDEX IF NOT EXISTS idx_posted_at ON bus_messages(posted_at);
CREATE INDEX IF NOT EXISTS idx_author ON bus_messages(author);
```

Схема будет расти на step_3-4 (поля для важности, фильтров) — миграцию через `ALTER TABLE ADD COLUMN`, без сложных систем.

## Поток выполнения

```
1. load_config()
   ├─ CLAUDE_AGENT_BOT_TOKEN, GROUP_CHAT_ID, BUS_TOPIC_ID, OWNER_USERNAME
   └─ проверка обязательных переменных

2. init_db("agents/claude/.local/state.db")
   └─ создать таблицу если её нет

3. get_last_seen_message_id() → int | None
   └─ SELECT MAX(tg_message_id) FROM bus_messages

4. fetch_new_bus_messages(since_id)
   ├─ через python-telegram-bot
   ├─ только из топика BUS_TOPIC_ID
   ├─ только сообщения в формате [author|source] text
   └─ парсить header

5. для каждого нового сообщения:
   ├─ INSERT в bus_messages (idempotent — игнор PK conflict)
   └─ если parse-ошибка — лог + skip (не падать)

6. лог: "fetched N new messages, total in db: M"

7. exit
```

**На этом шаге Claude Agent SDK ещё не вызываем** — только инициализируем сессию для проверки что OAuth работает (вызов "ping" или session.create без полезного промпта). Реальная работа SDK — на step_3.

Цель: на этом шаге убедиться что (а) OAuth сессия валидна, (б) TG-чтение работает, (в) БД пишется. Три отдельные мелкие проблемы, проще ловить отдельно.

## Важные технические решения

### 2.1. Чем читаем Bus

**По умолчанию: `python-telegram-bot`**, тот же подход что в `curator/bus.py` (но свой инстанс с своим токеном).

Бот должен быть **членом supergroup** и иметь права читать сообщения в Bus-топике. Возможные грабли:
- TG-бот может НЕ видеть исторические сообщения, только те что пришли после `getUpdates`. Для исторических нужен Telethon (userbot).
- Если упрёмся — для Bus тоже подключим Telethon как fallback (но не на этом шаге).

Решение: пробуем `python-telegram-bot` с long-polling за последний батч сообщений; если не хватает — делаем заметку и переходим на Telethon в step_3 или на интеграцию с общей БД сообщества.

### 2.2. Где живёт OAuth Claude Agent SDK

После `claude login` сессия живёт в стандартном месте Claude Code (на Linux обычно `~/.claude/`). Скрипт **не управляет** OAuth — просто полагается что юзер залогинился. Если не залогинен — SDK выкинет понятную ошибку, мы её ловим и пишем "Run `claude login` first".

### 2.3. Idempotency

Скрипт можно запускать сколько угодно раз — повторный INSERT с тем же `tg_message_id` даст PK conflict, ловим `IntegrityError` и игнорируем. Cron можно ставить с overlap'ом, ничего не сломается.

### 2.4. Hard timeout

Вся сессия должна уложиться в **5 минут**. Если не уложилась — kill процесс. Реализация: `asyncio.wait_for(main(), timeout=300)` или внешний `signal.SIGALRM` для синхронных кусков.

Лог "timeout, will retry next cron tick", exit-code ≠ 0.

### 2.5. Почему не тащим из curator/

`curator/bus.py` использует `CURATOR_BOT_TOKEN` и глобальный модуль-стейт `_posted_keys` (in-memory дедупликация). Он завязан на куратор-процесс. Импортировать это в агенте — значит ломать его автономность и тащить за собой ребро. Свой `bus_client.py` короче и понятнее.

## Smoke-тест шага

```bash
# 1. Залогиниться (если ещё не сделано)
claude login

# 2. Создать .env агента
cp agents/claude/.env.example agents/claude/.env
# заполнить CLAUDE_AGENT_BOT_TOKEN, OWNER_USERNAME

# 3. Запустить вручную
python agents/claude/main.py

# 4. Проверить что появилась БД и в ней есть строки
sqlite3 agents/claude/.local/state.db "SELECT count(*) FROM bus_messages;"
```

Ожидаемый результат: `count >= 0` (если в Bus за сутки 0 сообщений — это валидно, главное что скрипт завершился сам без ошибок).

## Критерии готовности

- [ ] `agents/claude/main.py` создан, минимальный loop работает
- [ ] `agents/claude/bus_client.py` создан (read-only часть)
- [ ] `agents/claude/state_db.py` создан с миграцией
- [ ] `agents/claude/.env.example` создан
- [ ] `agents/claude/.local/state.db` создаётся при первом запуске
- [ ] При повторном запуске не дублирует сообщения (idempotent)
- [ ] При отсутствии OAuth — выводит понятную ошибку и завершается с кодом ≠ 0
- [ ] Hard timeout 5 минут реализован
- [ ] `.gitignore` обновлён (`agents/*/.local/`, `agents/*/.env`)
- [ ] Smoke-тест прошёл — скрипт завершился, БД создана, парсинг работает
- [ ] Статус в PLAN.md → done

## Чего НЕ делаем

- Не строим дайджест (step_3)
- Не пишем в Bus (step_4)
- Не подключаем Telethon (опциональная фича на потом)
- Не импортируем из `curator/`
- Не делаем красивый CLI с аргументами — простой `python agents/claude/main.py`
