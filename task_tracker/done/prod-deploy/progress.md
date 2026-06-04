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

### Инфра / VPS (СВЕРЕНО С СЕРВЕРОМ 2026-06-03)
- VPS: rm_agent@62.238.31.95 (Hetzner CX33, Ubuntu 24.04). SSH ключ
  ~/.ssh/openclaw_hetzner. НЕ трогать ~/.openclaw ~/.hermes ~/.codex ~/.claude.
- ⚠️ **Docker НЕ установлен** (нет docker/podman/нативного postgres). Прежняя строка
  «Docker уже стоит» была НЕВЕРНА. Ставим в step_1: apt install docker.io +
  usermod -aG docker rm_agent + перелогин. docker.io в репах = 29.1.3.
- Порт 5434 на VPS СВОБОДЕН (проверено, нет ни одного DB-порта).
- sudo passwordless у rm_agent — РАБОТАЕТ (M2 снят).
- Диск 21G свободно, RAM 6G свободно — хватает (дамп ~130МБ).
- **Каталог core = `~/wndrverse`** (`/home/rm_agent/wndrverse`). НЕ ~/claude-hub —
  тот отдельный git-репо-scaffold под Claude-агентов (его projects/ пустой). Путь
  подставлен во все systemd-юниты step_2/step_3.
- `~/wndrverse_agent_claude` существует (деплой агента, отдельная вещь) — не трогаем.

### Решения
- Корпус на прод = ПОЛНЫЙ дамп локальной БД (pg_dump БЕЗ --data-only → restore в
  пустую БД, БЕЗ предварительного core.db init — фикс K1, решение 2026-06-03). PII
  (имена) едет на VPS — осознанно. *.sql в gitignore (подтверждено). Дамп удаляется
  с VPS и локально после restore (V7).
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

### 2026-06-03 — ревью-фиксы применены к плану (ДО старта деплоя)
Ревью (_review_summary.md, 3 агента) писалось до завершения data-corpus. Часть
находок устарела/закрыта, часть применена к step-файлам:
- K3 (*.sql в gitignore) — уже закрыт в data-corpus. ✅
- V3 (requirements.txt) — есть, step_1 п.3 использует `-r requirements.txt`. ✅
- V4 (ветка влития) — решено: master (data-corpus влит ff c095854). step_1 п.0:
  нужен `git push origin master` ДО clone на VPS (локально пока не запушено).
- K1+K2 (способ дампа) — ЗАФИКСИРОВАН: полный pg_dump без init. step_1 п.5-7
  переписаны (init убран). Явный шаг создания дампа добавлен (п.6).
- K4 (путь в юнитах) — `~/wndrverse` подставлен во ВСЕ юниты step_2/3.
- V1 (OnCalendar) — добавлен `systemd-analyze calendar` verify в step_3 п.3.
- V7 (PII-дамп) — step_1 п.8 удаляет .sql с VPS и локально.
- M1 (PYTHONUTF8 в embedder), M2 (sudo OK) — применено/снято.

### 2026-06-03 — сверка с реальным VPS (главное)
**Docker НЕ установлен** (план/progress говорили обратное). Это был бы блокер на
step_1. Добавлен под-шаг установки Docker. Остальное на сервере: порт 5434 свободен,
sudo passwordless, ресурсов хватает, wndr-юнитов нет, claude-hub/projects пустой.
---
