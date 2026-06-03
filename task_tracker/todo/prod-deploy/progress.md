# Progress Log — prod-deploy

## Контекст для агента (факты, которых нет в коде)

### Откуда задача
Часть 2 из двух. Часть 1 — `data-corpus` (работа с данными, локально). Разделили
чтобы не мешать данные и инфраструктуру. **Этот план ЗАВИСИТ от data-corpus** —
начинать ТОЛЬКО после его done (код дедупа влит, локальный корпус чистый, дамп готов).

### Что приходит из data-corpus
- Код дедупа исправлен: единый `external_id = tg_{chat_id}_{msg_id}` у backfill и
  бота. На прод едет уже исправленный код (бот не задвоит сообщения поверх дампа).
- Локальный корпус: все топики WNDR, старые мигрированы, всё эмбеджено, dup_keys=0.
- Дамп этой БД (pg_dump) → restore на VPS. Это решение пользователя (НЕ повторный
  Telethon-парсинг на проде — без лишних трат, корпус идентичен).

### Инфра / VPS
- VPS: rm_agent@62.238.31.95 (Hetzner CX33, Ubuntu 24.04). SSH ключ
  ~/.ssh/openclaw_hetzner. НЕ трогать ~/.openclaw ~/.hermes ~/.codex ~/.claude.
- Docker уже стоит. docker-compose поднимает db на host:5434 (проверить что свободен).
- Каталог core на VPS — решается в step_1 (deploy-карта его не содержит). Предложение:
  ~/claude-hub/projects/wndrverse.

### Решения
- Корпус на прод = ДАМП локальной БД (pg_dump→restore). PII (имена) едет на VPS —
  осознанно (свой сервер, имена нужны для humanize). Дамп НЕ коммитить (*.sql в
  gitignore).
- Шедулер = systemd-timer + `--now` (НЕ sleep-loop). Время задаёт OnCalendar таймера,
  НЕ WNDR_DIGEST_AT. Persistent=true (не пропускает после ребута).
- Эмбеддинг на проде = wndr-embedder.timer раз в 6ч, батч по embedding IS NULL.
  Корпус из дампа уже эмбеджен → таймер обрабатывает лишь новое от бота.
- Дайджест-топики: сначала questions_to_* (WNDR_DIGEST_TOPICS), после прод-тестов →
  все топики (правка ENV, код не меняем).

### Реальные значения
- chat_id = -1002924475859. thread 16139 → questions_to_women; 16138 → questions_to_men.
- ЛС WNDR_DIGEST_DM_USER_ID = 423915315.
- Бот в WNDR chat — ГОТОВО (подтверждено пользователем 2026-06-01). privacy mode OFF —
  подтвердить в @BotFather (step_2).

### Что НЕ ломать
- PII: в OpenAI только [#id]+текст, имена локально. Не менять.
- bot/ingest_bot.py, ядро synthesis, client.py — не трогать (готовы).
- Существующие systemd-юниты OpenClaw/Hermes на VPS.

## Learnings (выполнение)
(заполняется в процессе работы)
---
