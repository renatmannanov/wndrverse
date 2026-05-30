# realtime-bot-ingest

> Статус: pending
> Дата: 2026-05-30
> Тип: фича
> Ветка: feature/realtime-bot-ingest (от feature/community-brain-mvp)
> Ревью: пройдено (code+risks+structure, 2026-05-30) — 10 находок применены

## Цель

Подключить Telegram-бота (python-telegram-bot, polling) к ядру `core/` так, чтобы
новые сообщения из групп в реалтайме писались в БД `fragments` через существующий
funnel `core/ingest/loaders.py:ingest()`. Бот пишем **с нуля** — в репо его нет,
заложен только funnel. Маппинг источника на топик закладываем сразу под всю
телеграм-структуру `(chat_id, thread_id) → topic`, чтобы потом подключать что
угодно (4 группы сейчас → 1 чат с топиками-threads → другие чаты) без переписывания
кода.

## Ключевые решения (зафиксированы, не обсуждаются в ходе работы)

1. **Стек:** `python-telegram-bot` (как весь остальной репо). Режим — **polling**
   (`run_polling()` + `MessageHandler`). Не webhook (не нужен публичный HTTPS).
2. **Маппинг `(chat_id, thread_id) → topic`** — конфиг-файл (не ENV; список пар
   будет расти при переходе на «1 чат много топиков»). Ключ — кортеж
   `(channel_id, message_thread_id)`; для 4 групп `message_thread_id = None`.
3. **Ingest по одному сообщению.** В async-хендлере зовём синхронный `ingest()`
   через `asyncio.to_thread(ingest, [frag])` — не блокируем event loop. Батчинг —
   преждевременная оптимизация, не в этом MVP.
4. **external_id:** `tgbot_{chat_id}_{message_id}` — chat_id в ключе обязателен,
   иначе при «1 чат много групп» / разных чатах message_id пересекутся.
   (Файловый ingest использует `wndr_{chat_name}_{id}` — у нас свой префикс,
   не конфликтует.)
5. **Происхождение в БД:** заполняем `channel_id` (chat_id), `sender_id` (user_id),
   `message_thread_id` (topic/thread id), `topic` (имя). **Все колонки уже есть** —
   `core/store/fragments_db.py:56-58`, `insert_fragments_batch` уже принимает
   `channel_id`. **Схему БД НЕ меняем.**
6. **Переиспользуем `message_to_fragment`.** Адаптер бота приводит `Update.message`
   к тому же плоскому dict, что ждёт `core/ingest/normalize.py`, и зовёт его —
   не дублируем логику нормализации. Адаптер только: (а) собирает flat dict из
   PTB-объекта, (б) задаёт ботовый `external_id`, (в) докладывает `channel_id`.
7. **PII не ломаем** (решение 8 из community-brain-mvp): в OpenAI уходит только
   текст + `[#id]`, имена подставляются локально. Адаптер пишет `author_name` /
   `username` в те же поля, что файловый ingest — поведение enrich не меняется.

## Шаги

| # | Файл | Статус |
|---|------|--------|
| 1 | step_1_topic_map.md         | [x] |
| 2 | step_2_bot_adapter.md       | [x] |
| 3 | step_3_bot_listener.md      | [x] |
| 4 | step_4_edge_cases.md        | [x] |
| 5 | step_5_smoke_one_group.md   | [ ] | блок: токен бота + chat_id группы |
| 6 | step_6_enrich_digest.md     | [ ] |
| 7 | step_7_completion.md        | [ ] |

## Критерии готовности

- [ ] `core/ingest/topic_map.json` в `.gitignore` (реальные chat_id не в git);
      `conftest.py` в корне обеспечивает импорт `core.*`/`bot.*` в тестах.
- [ ] Конфиг маппинга `(chat_id, thread_id) → topic` есть, загрузчик возвращает
      `topic` по паре; неизвестная пара → явное поведение (skip + лог).
- [ ] `core/ingest/bot_adapter.py` собирает Fragment dict из PTB `Message` и
      переиспользует `message_to_fragment`; заполнен `channel_id`,
      `external_id = tgbot_{chat_id}_{msg_id}`.
- [ ] Бот-листенер на polling запускается отдельным процессом, на новое сообщение
      зовёт `ingest()` через `asyncio.to_thread`.
- [ ] Edge cases (media-only без текста, служебные, edits) не падают и не плодят
      мусор — по аналогии с `message_to_fragment` (None → skip).
- [ ] Smoke на 1 группе: ~5 сообщений → появились в БД с правильными
      `topic` / `channel_id` / `message_thread_id`; повторный приём того же
      `message_id` → 0 новых (дедуп по `external_id`).
- [ ] enrich/digest на боевых данных группы прошёл; перед тратой OpenAI был
      `--estimate` (стоп-точка).
- [ ] `pytest` (если в репо есть тесты адаптера) — зелёный.
- [ ] Раздел «Что НЕ в этом MVP» соблюдён (см. ниже).

## Что НЕ в этом MVP (защита от scope creep)

- ❌ Разовая выгрузка истории через telegram-gather API — **другая задача,
  отдельное окно**.
- ❌ Доставка дайджестов обратно в Telegram.
- ❌ Расписания / cron на enrich/digest.
- ❌ Webhook (только polling).
- ❌ Изменение схемы БД (`core/store/`) — нужные колонки уже есть.
- ❌ Правка `curator/` и `agent-template/` — рабочий код, не трогаем.
- ❌ Telethon / userbot (история и приватные чаты — не сюда).

## Открытые вопросы пользователю (не блокируют написание плана, нужны перед smoke)

- Токен тестового бота (`BOT_TOKEN_INGEST` в `.env`) — кто заведёт у @BotFather.
- chat_id 4 тестовых групп (мужская / женская / вопросы мужчинам / вопросы
  женщинам) — нужны для конфига маппинга. Узнаём после добавления бота в группы.
- Какая из 4 групп — для smoke (step_5).
