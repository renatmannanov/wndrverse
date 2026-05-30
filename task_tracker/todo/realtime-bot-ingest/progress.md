# Progress Log — realtime-bot-ingest

## Контекст для агента (факты, которых нет в коде)

### Откуда взялась задача
Future-шаг из `task_tracker/done/community-brain-mvp/` (решение 7: «realtime — бот
для нового, Telethon разово для истории»). Funnel под это заложен заранее. Читай
тот PLAN.md и progress.md — там 9 шагов, PII-решение, грабли.

### Разведка (Фаза 1, сделана 2026-05-30) — что в репо ЕСТЬ и чего НЕТ
- **Бота-приёмника НЕТ.** Ни одного кода, который принимает входящие сообщения
  из групп. Проверено grep'ом по `MessageHandler / Application.builder /
  start_polling / telethon / aiogram / @client.on` — только в ДОКАХ
  (`mvp-agent-network/step_8_bot_to_bot.md` как пример) и в раннем скаффолде
  `agents/_claude/bus_client.py` (разовый getUpdates, читает Bus, не группы,
  `_`-префикс = deprecated).
- `setup_bots.py` — только админка токенов (getMe, getManagedBotToken). Не слушает.
- `agent-template/*`, `curator/bus.py`, `curator/showcase.py` — пишут в Bus/Showcase.
- `curator/reader.py` — читает через HTTP telegram-gather API, не из TG напрямую.
- `telethon`, `aiogram` — 0 файлов. Весь TG-код на `python-telegram-bot`.

### Funnel и формат (образец интерфейса)
- `core/ingest/loaders.py:ingest(messages: list[dict]) -> dict` — единый funnel,
  батчит по 500, дедуп по `external_id`, возвращает
  `{'indexed', 'duplicates_skipped'}`. **Синхронный** (важно для async-бота).
- `core/ingest/normalize.py:message_to_fragment(msg, *, topic, chat_name,
  thread_root_id)` — ждёт ПЛОСКИЙ dict (`msg['id']`, `msg['date']` ISO-строка,
  `msg.get('text')`, `user_id`, `sender_name`, `username`, `reply_to_msg_id`).
  Возвращает Fragment dict или **None** для пустых/служебных (нет текста).
  **НЕ заполняет `channel_id`** — для файлов chat_id не было; адаптер бота должен.
- Образец вызова — `load_export_file()` в loaders.py.

### БД готова к «что откуда пришло» (схему НЕ менять)
`core/store/fragments_db.py`, модель `Fragment`:
- `sender_id` BigInteger — user_id (строка 56)
- `channel_id` BigInteger — `# Telegram chat ID (-100 format)` (строка 57) = chat_id
- `message_thread_id` BigInteger — `# Forum topic / thread root id` (строка 58)
- `topic` String — имя топика
`insert_fragments_batch` уже принимает `channel_id` (строка 180). Менять нечего.

### Что не ломать
- `core/` (funnel, store, enrich, brain) — только ДОПОЛНЯЕМ адаптером. Не править
  normalize/loaders без явной нужды (если кажется надо — сначала спросить).
- `curator/`, `agent-template/` — рабочий код, не трогать.
- PII-решение: имена/username не уходят в OpenAI. Адаптер кладёт их в те же поля
  (`author_name`, `metadata.username`) — поведение enrich не меняется.

### Деньги
enrich на новых данных (step_6) = трата OpenAI. **Стоп-точка:** сначала
`python -m core.enrich.embedder --estimate`, потом явное «ок».

### Режимы маппинга (заложить сразу оба)
- Сейчас: 4 отдельные группы → разные `chat_id`, `thread_id = None`.
- Потом: 1 супергруппа с топиками → один `chat_id`, разные `message_thread_id`.
Ключ маппинга — кортеж `(chat_id, thread_id)`. Переход = новые строки конфига.

### VPS
НЕ лезть. Разведка/разработка локальные. Если критично знать про прод —
выписать как открытый вопрос, не ssh-ить.

## Learnings

### Steps 1-4 сделаны (2026-05-30, ветка feature/realtime-bot-ingest)
- `tests/` уже существовал (1 файл `test_ingest_normalize.py` с ручным sys.path).
  `conftest.py` в корне добавлен — новые тесты импортят `core.*`/`bot.*` без хака.
- PTB версия в окружении: **22.5**. `pytest-asyncio` установлен, но pytest.ini нет →
  тесты хендлера гоняем через `asyncio.run(on_message(...))`, без зависимости от
  asyncio_mode. Патчим `ingest_bot.ingest` и `ingest_bot.resolve_topic` (to_thread
  резолвит имя модуля в рантайме — патч работает).
- `topic_map`: добавил `reload()` для сброса кэша (нужно тестам с tmp-конфигами и
  при правке topic_map.json на лету).
- `.env`: токен кладётся как `BOT_TOKEN_INGEST` (НЕ `BOT_TOKEN` — это куратор).
  `.env.example` дополнен BOT_TOKEN_INGEST + WNDR_TOPIC_MAP.
- 23 теста зелёные. normalize.py / fragments_db.py — git diff пуст (не тронуты).

### Блок на step_5 (нужно от пользователя)
- `BOT_TOKEN_INGEST` в `.env` (бот у @BotFather).
- chat_id тестовой группы (узнать @getmyid_bot/@userinfobot, НЕ нашим ботом).
- какая из 4 групп для smoke (пользователь думает).
- chat_id внести в `core/ingest/topic_map.json` (файл в .gitignore, скопировать
  из topic_map.example.json).
---
