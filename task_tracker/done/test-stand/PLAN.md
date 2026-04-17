# WNDRverse Test Stand — обкатка логики ботов

> Статус: done
> Дата: 2026-04-16
> Тип: тестовый стенд
> Предыдущий план: done/mvp-agent-network/

## Контекст

WNDRverse — сеть агентов в Telegram для community networking.
Архитектура: один бот-родитель (@rm_curator_bot) создаёт дочерних ботов для участников
через Telegram Managed Bots API. Дочерние боты пишут в Bus (топик 1), куратор выбирает
лучшее и постит в Showcase (топик 2). Bot-to-Bot Communication позволяет ботам видеть
и реагировать на сообщения друг друга.

**Что уже сделано (mvp-agent-network):**
- Супергруппа "re-verse" с 2 топиками (Bus id=3, Showcase id=1)
- @rm_curator_bot — родитель, Bot Management Mode ON, b2b ON
- @test_wndr_agentbot — первый дочерний бот, в группе как админ
- Managed Bots + Bot-to-Bot протестированы и работают
- curator/reader.py — читает каналы через telegram-gather API (Railway)
- curator/bus.py — постит в Bus (сейчас только от куратора)
- curator/showcase.py — постит в Showcase
- curator/prompts/ — промпты агентов и куратора (написаны, нужно адаптировать)
- sources.json — каналы Рената по категориям

**Что НЕ сделано:**
- agents.py, main.py — автоматическая фильтрация через Claude API (дорого тестировать)
- members.json — участники с промптами и mode
- loop_guard.py — защита от b2b петель
- Сквозной автотест

## Цель тестового стенда

Обкатать логику взаимодействия ботов **без Claude API**. Всё через подписку —
человек (Ренат) через Claude Code генерирует ответы за каждого агента, скрипт постит
от имени нужного бота в Telegram. Когда логика и промпты обкатаны — заменяем ручной ввод
на Claude API (следующая итерация).

## Ключевой принцип: один канал → разные глаза

Все боты читают **один и тот же канал** (iwacado — приватный канал Рената).
У Рената — реальный канал через telegram-gather.
У Васи и Маши — те же самые сообщения, но фильтрация через свой промпт (свои интересы).
Из одного потока рождаются разные находки → обсуждение в Bus → мэтчинг.

```
Приватный канал Рената (iwacado) — 20-30 сообщений за день
  │
  │ telegram-gather API (одинаковые данные для всех)
  │
  ├─ Агент Рената: фильтр "AI, vibe-coding" → 0-2 поста в Bus
  ├─ Агент Васи: фильтр "парсинг, автоматизация" → 0-2 поста в Bus
  ├─ Агент Маши: фильтр "дети, образование, AI" → 0-2 поста в Bus
  │
  ▼
Bus: 2-6 сообщений от разных агентов
  │
  │ Агенты видят Bus друг друга (b2b) → реплаи на пересечения
  │ "Маша тоже интересуется AI для детей!"
  │
  ▼
Куратор: читает Bus + реплаи → выбирает лучшее / формирует мэтч → Showcase
```

## Как работает (Вариант C — полуавтомат)

```
test_stand.py — интерактивный скрипт-оркестратор

Цикл:
1. Читает реальный канал iwacado через telegram-gather API
2. Читает members.json → список участников с промптами и интересами
3. random.shuffle(members) — порядок случайный, как будто агенты независимы
4. Для каждого участника (одни и те же сообщения, разные промпты):
   → Показывает: "Промпт Васи + сообщения из канала"
   → Ренат вводит ответ (как если бы был Claude API с этим промптом)
   → Скрипт постит от @wndr_vasya_bot в Bus
5. Показывает Bus целиком — каждый пост с автором бота
   → random.shuffle(members) — опять случайный порядок
   → "Промпт Маши. Она видит Bus (кроме своих постов). Реагирует?"
   → Ренат вводит → скрипт постит реплай от @wndr_masha_bot
6. Показывает Bus + все реплаи
   → "Промпт куратора. Что в Showcase?"
   → Ренат вводит → скрипт постит в Showcase от @rm_curator_bot
```

## Что нужно создать

### 1. members.json — 3 участника, один канал

Все читают один канал (iwacado), но у каждого свой промпт и интересы.

```json
{
  "source_channel": "iwacado",
  "members": [
    {
      "name": "Renat",
      "tg_username": "ray_mann",
      "agent_bot": "test_wndr_agentbot",
      "agent_token_env": "AGENT_RENAT_TOKEN",
      "mode": "managed",
      "prompt_file": "prompts/renat.md",
      "interests": ["AI", "агенты", "автоматизация", "vibe-coding", "дети"]
    },
    {
      "name": "Vasya",
      "tg_username": "vasya_test",
      "agent_bot": "<создать через managed bots>",
      "agent_token_env": "AGENT_VASYA_TOKEN",
      "mode": "managed",
      "prompt_file": "prompts/vasya.md",
      "interests": ["парсинг", "авито", "автоматизация", "Python"]
    },
    {
      "name": "Masha",
      "tg_username": "masha_test",
      "agent_bot": "<создать через managed bots>",
      "agent_token_env": "AGENT_MASHA_TOKEN",
      "mode": "managed",
      "prompt_file": "prompts/masha.md",
      "interests": ["дети", "образование", "AI для детей", "vibe-coding"]
    }
  ]
}
```

Все боты получают одни и те же сообщения из iwacado через telegram-gather.
Разница — в промпте: каждый фильтрует через свои интересы.

### 2. Дочерние боты (создать через Managed Bots)

Нужно создать ещё 2 дочерних бота:
- `@wndr_vasya_bot` (или аналог) — для Васи
- `@wndr_masha_bot` (или аналог) — для Маши

Процесс:
1. Сформировать ссылку: `t.me/newbot/rm_curator_bot/<username>?name=<name>`
2. Открыть в Telegram → подтвердить
3. Получить токен: `getManagedBotToken(user_id=<bot_id>)` — ВАЖНО: параметр `user_id`, не `bot_id`
4. Добавить бота в группу как админа (вручную, API не позволяет)
5. Записать токен в .env

Уже есть: @test_wndr_agentbot (id: 8733226908, токен получен).

### 3. Промпты участников — адаптировать

Сейчас в curator/prompts/ есть agent_one.md и agent_two.md — "агент Рената".
Нужно переделать под конкретных участников:

- `prompts/renat.md` — интересы Рената (AI, дети, vibe-coding)
- `prompts/vasya.md` — интересы Васи (парсинг, автоматизация)
- `prompts/masha.md` — интересы Маши (дети, образование, AI)
- `prompts/curator.md` — уже есть, возможно нужно обновить

### 4. bus.py — доработать

Сейчас bus.py постит только от CURATOR_BOT_TOKEN.
Нужно: принимать токен как параметр (каждый агент постит от своего бота).

```python
async def post_to_bus(text: str, bot_token: str | None = None, key: str | None = None):
    token = bot_token or CURATOR_BOT_TOKEN
    bot = Bot(token=token)
    ...
```

### 5. test_stand.py — скрипт-оркестратор

Интерактивный скрипт. Постит сразу в Telegram (без dry-run).
Порядок агентов рандомизируется в каждой фазе — как будто действуют независимо.

```python
# test_stand.py
import random

async def main():
    members = load_members()

    # Один канал для всех
    source = members_config["source_channel"]  # "iwacado"
    messages = await get_recent_messages(source, period="1d")
    print(f"Канал {source}: {len(messages)} сообщений\n")

    # Фаза 1: Каждый агент фильтрует ОДНИ И ТЕ ЖЕ сообщения через свой промпт
    bus_posts = []
    order = list(members)
    random.shuffle(order)  # случайный порядок

    for member in order:
        prompt = load_prompt(member)

        print(f"\n{'='*60}")
        print(f"АГЕНТ: {member['name']} (@{member['agent_bot']})")
        print(f"ИНТЕРЕСЫ: {member['interests']}")
        print(f"ПРОМПТ: {prompt[:200]}...")
        print(f"\nСООБЩЕНИЯ ИЗ КАНАЛА ({len(messages)}):")
        for m in messages:
            print(f"  [{m['date'][:10]}] {m['text'][:100]}")
        print(f"\nЧто агент {member['name']} постит в Bus? (или SKIP)")

        response = input("> ")
        if response.strip().upper() != "SKIP":
            msg = await post_to_bus(response, bot_token=member_token(member))
            bus_posts.append({
                "member": member["name"],
                "bot": member["agent_bot"],
                "text": response,
                "msg_id": msg.message_id,
            })

    # Фаза 2: Агенты видят Bus друг друга (b2b) → реплаи на пересечения
    print(f"\n{'='*60}")
    print("BUS содержит:")
    for i, p in enumerate(bus_posts, 1):
        print(f"  {i}. [@{p['bot']}] {p['text'][:100]}")

    order2 = list(members)
    random.shuffle(order2)  # другой случайный порядок

    for member in order2:
        # Показать только ЧУЖИЕ посты
        others = [(i, p) for i, p in enumerate(bus_posts, 1) if p["member"] != member["name"]]
        if not others:
            continue
        print(f"\nАГЕНТ {member['name']} (@{member['agent_bot']}) видит Bus:")
        for i, p in others:
            print(f"  {i}. [@{p['bot']}] {p['text'][:100]}")
        print("Реагирует? (номер поста или SKIP)")

        choice = input("> ")
        if choice.strip().upper() != "SKIP":
            post_num = int(choice) - 1
            reply_text = input("  Текст реплая: ")
            await reply_in_bus(reply_text, reply_to_message_id=bus_posts[post_num]["msg_id"],
                               bot_token=member_token(member))

    # Фаза 3: Куратор → Showcase
    print(f"\n{'='*60}")
    print("КУРАТОР видит Bus + реплаи. Что в Showcase?")
    response = input("> ")
    await post_to_showcase(response)
```

### 6. loop_guard.py — защита от петель (для фазы 2)

Когда заменим ручной ввод на Claude API — обязательно добавить:
- Rate limit: max 1 реплай на пару ботов в 30 секунд
- Max depth: не больше 2 реплаев в цепочке
- Deduplication

Для ручного тестового стенда не нужен — человек не создаёт петли.

## Шаги

| # | Что делаем | Файл | Статус |
|---|-----------|------|--------|
| 1 | Создать 2 дочерних бота (Vasya, Masha), добавить в группу | step_1_bots.md | [x] |
| 2 | Написать members.json с 3 участниками (один канал-источник) | step_2_members.md | [x] |
| 3 | Адаптировать промпты под конкретных участников | step_3_prompts.md | [x] |
| 4 | Доработать bus.py — поддержка токена агента | step_4_bus.md | [x] |
| 5 | Написать test_stand.py — интерактивный оркестратор | step_5_orchestrator.md | [x] |
| 6 | Прогнать 3-5 сценариев, обкатать промпты | step_6_scenarios.md | [x] |
| 7 | Зафиксировать результаты: что работает, что нет | step_7_results.md | [x] |
| 8 | Завершение плана | step_8_completion.md | [x] |

## Критерии готовности

- [x] 3 бота в группе (Renat, Vasya, Masha) пишут от разных имён
- [x] Bus содержит сообщения от разных агентов в формате [author|source]
- [x] Хотя бы 1 мэтч найден (агенты реагируют на пересечение)
- [x] Showcase содержит 1 пост куратора (мэтч или лучший пост дня)
- [x] Промпты обкатаны: фильтрация работает (0-2 из 10+ сообщений)
- [x] Результаты зафиксированы для перехода к Claude API

## Ключевые файлы проекта

```
wndrverse/
├── CLAUDE.md                     ← инструкции проекта
├── .env                          ← токены (не в git)
├── sources.json                  ← каналы Рената (справочно)
├── members.json                  ← участники + общий канал-источник (создать)
├── curator/
│   ├── reader.py                 ← telegram-gather API (готов)
│   ├── bus.py                    ← Bus постинг (доработать — токен агента)
│   ├── showcase.py               ← Showcase постинг (готов)
│   └── prompts/                  ← промпты (адаптировать)
├── test_stand.py                 ← интерактивный оркестратор (создать)
└── task_tracker/
    ├── todo/ARCHITECTURE.md      ← архитектура (обновлена)
    └── done/mvp-agent-network/   ← предыдущий план
```

## Telegram инфра (уже работает)

- Группа: `re-verse` (id: -1003968221945)
- Bus topic id: 3
- Showcase topic id: 15
- Родитель: @rm_curator_bot (Bot Management Mode ON, b2b ON)
- Дочерний: @test_wndr_agentbot (id: 8733226908, токен в .env)
- Managed Bots API: `getManagedBotToken(user_id=<bot_id>)` — параметр `user_id`!
- Ссылка создания: `t.me/newbot/rm_curator_bot/<username>?name=<name>` (открывать в TG клиенте)
- Добавление в группу: только вручную (API ограничение)

## Архитектурные заметки (для следующих итераций)

### Дедупликация — TODO

Сейчас `_posted_keys` в bus.py живёт в памяти процесса.
Для тест-стенда ок (один запуск скрипта), но при переходе к проду нужна
персистентная дедупликация (файл `data/dedup.json` или SQLite).

### Хранение сообщений — TODO

При 100 участниках и 7000 сообщений/6 мес — каждый раз парсить заново дорого.
Решение: кэшировать локально.

```
data/
├── raw/{channel}/{date}.json     — сырые сообщения из каналов (1 запрос → файл → все агенты)
├── bus/{date}.json               — Bus-посты (мы сами постим — знаем что постили)
├── showcase/{date}.json          — Showcase-посты (история мэтчей)
├── processed/{agent}.json        — set обработанных message_id (не платить Claude за повтор)
└── runs/{timestamp}.json         — логи прогонов test_stand.py
```

JSON-файлы: git-friendly, ~50 MB на 6 мес. SQLite — когда перерастём файлы.

### Стоимость при масштабе (100 участников)

**Telegram Bot API:** бесплатно. Managed Bots — каждый со своим rate limit.

**telegram-gather:** если N участников мониторят один канал — 1 запрос, результат в кэш.
В WNDR реально: много людей в одних группах. Без кэша: ~400 запросов/день.

**Claude API (главная статья):**
- 100 агентов × 1 вызов/день × ~2.2K tokens = ~6.6M tokens/мес
- Sonnet: ~$27/мес. Haiku: ~$3/мес.
- Оптимизации: prompt caching, Haiku для агентов + Sonnet для куратора,
  token matching без AI для первичной фильтрации (v1).

### telegram-gather не видит Bus

telegram-gather возвращает `{id, date, sender, text, reply_to}` — без `message_thread_id`.
Нельзя отфильтровать Bus от Showcase от General.

Варианты для автоматизации:
1. getUpdates/webhook через токен бота — видит thread_id
2. Допилить telegram-gather (добавить поле)
3. Хранить Bus-посты локально (мы сами постим — знаем что постили) ← самый простой

Для тест-стенда: вариант 3 (логи прогонов в data/runs/).

## Принятые решения (2026-04-17)

- source_channel: один на тест-стенд (iwacado) — ОК, тестовый формат
- b2b: включить у ВСЕХ трёх дочерних ботов (чтобы каждый мог реплаить каждого)
- Showcase topic_id: из env (SHOWCASE_TOPIC_ID), не хардкод
- task_tg_gather_thread_id: уже выполнена (шаг 0), файл перенесён в done/
- dry-run: не нужен, сразу постим в TG
- Промпты: 3 самодостаточных файла (curator/prompts/renat.md, vasya.md, masha.md)
- Порядок агентов: random.shuffle() в каждой фазе
- Фаза 2 UX: каждому агенту показывать только ЧУЖИЕ посты с именем бота-автора

## Важные learnings из предыдущего плана

- Промпты должны жёстко ограничивать: MAX 2 сообщения на агента, лучше 0 чем 3
- Первый прогон дал 19 из 26 — без ограничений агент репостит всё
- telegram-gather не возвращает message_thread_id — Bus нельзя перечитать через него
- Для b2b достаточно включить mode у одного бота (родителя), но включаем у всех чтобы каждый мог реплаить
