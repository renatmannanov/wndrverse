# Progress Log — digest-scheduler

## Контекст для агента (факты, которых нет в коде)

### Откуда задача
Продолжение `done/realtime-bot-ingest/`. Бот теперь пишет сообщения групп в БД.
Эта задача — обвязать УЖЕ РАБОТАЮЩЕЕ ядро дайджеста расписанием и доставкой в ЛС.
Читай `done/realtime-bot-ingest/progress.md` — там про topic_map, бот, PII.

### Что в репо УЖЕ ЕСТЬ (не переписывать, обвязываем)
- `delivery/cli.py:_run_digest(topic_arg, period, channel)` — полный путь:
  get_fragments → synthesize_and_save → humanize_refs (PII локально) → channels.send.
  Принимает `channel` как параметр — sched дёргает с `channel="telegram_dm"`.
- `delivery/cli.py:parse_period` — '1d'/'1w'/'12h'/'1m'/'all' → since-datetime (UTC).
- `core/brain/synthesis.py:synthesize()` — two-pass (Pass1 отбор если >30 фрагментов,
  Pass2 синтез). `TOPIC_HINTS` (строки 28-39) — семантика топиков в промпт.
  `_synthesize_fragments` (~122) зовёт `complete()` — сюда добавить max_tokens.
- `core/llm/client.py:complete(prompt, *, model, temperature, max_tokens)` — уже
  принимает max_tokens. НЕ менять client, только звать с параметром.
- `delivery/channels.py:send(text, *, channel)` — `telegram_dm`/`telegram_group`
  сейчас `raise NotImplementedError` (extension point). Реализуем `telegram_dm`.
- `core/store/fragments_db.py`: таблица `artifacts` (id, topic, content,
  fragment_ids[], created_at). `save_artifact` (стр. 591) уже пишет дайджест.
  fragment_ids в artifacts = фундамент будущего триггера по накоплению.

### Окружение / стек
- python-telegram-bot **22.5**, async-only — для ЛС использовать `Bot.send_message`
  через короткий `asyncio.run(...)` в синхронном channels.send.
- **APScheduler НЕ установлен** — планировщик пишем как sleep-loop на stdlib
  (`zoneinfo` + `datetime` + `time.sleep`). `zoneinfo.ZoneInfo('Asia/Almaty')` работает.
- COMPLETION_MODEL = gpt-4o-mini. EMBED = text-embedding-3-small.
- conftest.py в корне уже есть (от прошлого плана) — импорт core.*/digest.*/delivery.*
  в тестах без sys.path-хаков.

### Источник (WNDR chat) — реальные значения
- chat_id = **-1002924475859** (из ссылки t.me/c/2924475859/...→ +(-100)).
- thread 16139 → «Вопросы к Женскому миру» → ключ `questions_to_women`.
- thread 16138 → «Вопросы к Мужскому миру» → ключ `questions_to_men`.
- Это многотопиковая супергруппа → в topic_map ключ (chat_id, thread_id), НЕ None.
- Отличается от raymann_agents (-1003905781841, thread None) из прошлого плана.

### Доставка
- В ЛС user_id = **423915315** (это же sender_id Renat из прошлого smoke — сходится).
- Шлёт тот же бот BOT_TOKEN_INGEST. Пользователь обязан написать боту /start.
- plain text, без parse_mode (Markdown Telegram ломается на спецсимволах дайджеста).

### Деньги
Синтез тратит OpenAI. Стоп-точка в step_5: сначала проверить наличие данных +
`--estimate` если есть неэмбедженные, дождаться «ок».

### Что не ломать
- PII: в OpenAI только [#id]+текст, имена локально в humanize_refs. Не менять.
- Ядро two-pass synthesis, схему БД, client.py, curator/, agent-template/,
  bot/ingest_bot.py — не трогать.

### Закладки на будущее (НЕ строить)
- `--angle` уточнение угла: в step_4 есть только `--now`; угол прокинется в
  topic_hint позже без переделки. Упомянуть в бэклог-файле.
- Триггер по накоплению контекста → `task_tracker/backlog/digest-trigger-by-context.md`
  (создаётся в step_6).

### VPS
НЕ лезть. Расписание привязано к зоне Asia/Almaty явно (zoneinfo), чтобы при
будущем переезде на VPS (там TZ=UTC) момент отправки не сдвинулся. Деплой — отдельно.

## Learnings

### Ревью плана пройдено (2026-06-01, /review-plan: code+risks+structure)
Применены 10 правок (C1-C3 критичные, V1-V7 важные):
- C1 step_1: правило «git check-ignore ДО git add» (chat_id не в git).
- C2 step_2: `telegram_dm`/`telegram_group` разнесены на отдельные ветки send()
  (group остаётся NotImplementedError).
- C3 step_1: example.json показывает thread-режим (ненулевой thread_id), не дубль null.
- V1 step_4: guard в run_once — 0 фрагментов по топику → skip без синтеза (не тратим
  OpenAI на пустоту). Импорты get_fragments_for_digest/parse_period/_run_digest —
  наверху модуля scheduler.py (для патча в тестах через scheduler.*).
- V2 step_5: пред-чек count по топикам; 0 данных → СТОП, синтез не гнать.
- V3 step_5: estimate усилен — показать WNDR-фрагменты vs весь unembedded-корпус.
- V4 step_6: перед мержем влить родительскую feature/realtime-bot-ingest (ветка от
  неё, не от dev).
- V5 PLAN.md «Что НЕ в MVP»: пропущенный запуск не догоняется — осознанно.
- V6: DM_USER_ID в .env.example добавляет step_2 (вводит его), step_4 — только свои
  4 ENV. Граница ответственности зафиксирована.
- V7 step_6: конкретные места вставки в CLAUDE.md (новая секция после bot/, ENV в
  блок Env vars).
Противоречие code vs structure про «параллельные шаги 2/3»: разные файлы, конфликта
НЕТ; связка длины проверяется на smoke — ложную сериализацию не вводили.

## Learnings (выполнение)
(заполняется в процессе работы)
---
