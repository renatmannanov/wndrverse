# Progress Log — data-corpus

## Контекст для агента (факты, которых нет в коде)

### Откуда задача
Часть 1 из двух (вторая — `prod-deploy`). Разделили чтобы не мешать «работу с
данными» и «инфраструктурный деплой». Этот план = ЛОКАЛЬНО: исправить дедуп,
мигрировать старые, спарсить все топики, эмбеддинги. Результат — чистый локальный
корпус, который дампом поедет на прод (план B).

Предыстория: `done/digest-scheduler/` (коммит 8f4f3c6, ветка
feature/realtime-bot-ingest). Код дайджеста/бота/шедулера готов и протестирован.

### ГЛАВНАЯ техническая проблема (шаг 1) — РАЗНЫЕ external_id
Дедуп в `core/store/fragments_db.py:160` — построчный SELECT по `external_id` (НЕ ON
CONFLICT). Ключи должны совпадать побайтно. Сейчас backfill даёт
`wndr_{chat_name}_{msg_id}` (в БД `wndr_WNDR chat_2265`, С ПРОБЕЛОМ), бот —
`tgbot_{chat_id}_{msg_id}`. → задвоение. Шаг 1 сводит к `tg_{chat_id}_{msg_id}`.

### Состояние локальной БД (на 2026-06-01, до начала плана)
- 6534 фрагмента. 6530 с `channel_id=NULL` (старый backfill без chat_id), 4 —
  raymann_agents от бота.
- Топики: boltalka 2396, offerings 1523, daily 1004, requests 705, intro 305,
  sales 177, commits 154, harvest 133, announcements 85, together 48, raymann_agents 4.
  **questions_to_women/men = 0** (бот ещё не собрал).
- offerings полностью эмбеджен (был smoke в digest-scheduler). unembedded по всему = 0
  на момент конца прошлого плана (но после нового backfill появится дельта).

### Миграция старых (шаг 2) — вариант В, ПРОВЕРЕН при планировании
SQL: `UPDATE fragments SET channel_id=-1002924475859,
external_id='tg_-1002924475859_'||split_part(external_id,'_',3) WHERE channel_id IS NULL`.
Проверки (выполнены, повторить на текущей БД):
- все 6530 → `source=telegram` (один чат WNDR);
- `split_part(external_id,'_',3)` даёт чистый числовой msg_id у ВСЕХ 6530 (пробел в
  "WNDR chat" не мешает — split по '_', 3-й сегмент = число);
- НЕТ коллизий msg_id между топиками (0 строк) → ключ останется уникальным.
Эмбеддинги старых СОХРАНЯЮТСЯ (апдейтим только external_id+channel_id). В этом смысл
В — не платить за эмбеддинги повторно. ДО апдейта — pg_dump бэкап + подтверждение.

### Знак chat_id — ловушка (шаг 1)
Telethon `entity.id` супергруппы = ПОЛОЖИТЕЛЬНЫЙ (2924475859). В БД/topic_map/у бота
(PTB message.chat_id) — `-100…` (`-1002924475859`). Шаг 1 пишет в экспорт `-100…`,
чтобы ключ backfill === ключ бота.

### Реальные значения WNDR
- chat_id = -1002924475859. thread 16139 → questions_to_women; 16138 → questions_to_men.
- ⚠️ thread_id (из ссылок) может ≠ Telethon topic_id — проверить fetch_topics_list.py
  (шаг 3), зафиксировать соответствие ЗДЕСЬ.

### Telethon
- Сессия `telegram_gather_dev.session` ЛОКАЛЬНА (~/projects/telegram-gather). Backfill
  снимаем локально. На прод корпус поедет ДАМПОМ (план B), не повторным парсингом.
- fetch_topic.py / fetch_topics_list.py — в ОТДЕЛЬНОМ репо. Правка fetch_topic.py
  (chat_id) коммитится в ЕГО git, не в wndrverse. Не смешивать коммиты.

### Backfill — ВСЕ топики (решение 4.2)
Не только questions_to_*, а весь чат (~12 топиков). Эмбеддинги — на дельте (новые +
новые топики), старые уже эмбеджены после миграции.

### Что НЕ ломать
- PII: в OpenAI только [#id]+текст, имена локально. Не менять.
- Ядро two-pass synthesis, client.py, схема БД, curator/, agent-template/. Правка
  дедупа — только normalize.py / bot_adapter.py / loaders.py (+ fetch_topic.py в
  другом репо).

### Что дальше (план B — prod-deploy)
Дамп этой БД (pg_dump) → restore на VPS. Бот systemd-сервис, шедулер+embedder
таймеры, прод-smoke, показ заказчику. Дайджест на проде сначала по questions_to_*,
после тестов → все топики (через WNDR_DIGEST_TOPICS, код не меняем).

## Learnings (выполнение)

### Step 1 (done, 2026-06-01)
- Ветка `feature/data-corpus` создана от `feature/realtime-bot-ingest` (решение польз.).
- wndrverse коммит `86c742f`: normalize/loaders/bot_adapter + тесты. `pytest tests/ -q`
  = 35 passed. Ключ `tg_{chat_id}_{msg_id}` обоими путями подтверждён командами.
- telegram-gather коммит `0c03551` (ОТДЕЛЬНЫЙ репо, ветка dev): chat_id в fetch_topic.py
  + фикс импорта в fetch_topics_list.py.
  ⚠️ ВАЖНО: план предполагал NameError (`GetForumTopicsByIDRequest` vs
  `GetForumTopicsRequest`). РЕАЛЬНАЯ причина глубже: оба класса лежат в
  `telethon.tl.functions.MESSAGES`, а импорт был из `.channels` → ImportError по
  модулю. Исправлено на `from telethon.tl.functions.messages import GetForumTopicsRequest`
  (telethon 1.42.0). Импорт проверен — резолвится.
  ⚠️ В telegram-gather (ветка dev) есть ЧУЖИЕ незакоммиченные правки
  (main.py, health_monitor.py, scripts/grab_stickers.py, make_sticker_pack.py) —
  НЕ трогал, закоммитил только свои 2 файла точечным `git add`.

### Step 2 (done, 2026-06-01) — миграция выполнена
- Бэкап `backup_fragments_before_migrate.sql` (131 МБ, 6534 строки в COPY) создан ДО.
- emb_before = 6534 (весь корпус был эмбеджен).
- Транзакция: UPDATE 6530 (NULL-пласт → tg_-1002924475859_, channel_id проставлен)
  + UPDATE 4 (tgbot_-1003905781841_ → tg_). COMMIT.
- Пост-проверка: null_chat=0, tgbot_=0, dup_keys=0, emb_after=6534 (==before), total=6534.
- ⚠️ Бэкап-`.sql` НЕ был в gitignore — добавил `*.sql` + `backup_*.sql` в .gitignore
  (содержит PII). Проверено `git check-ignore`. Файл лежит локально, в git не попадёт.

### Step 3 — маппинг topic_id → ключ (fetch_topics_list, 2026-06-03)
Получен `fetch_topics_list.py "WNDR chat"` → 11 топиков. chat entity.id = 2924475859
(в БД -1002924475859). Колонка Messages в выводе = top_message ID (~17300), НЕ count.

| topic_id | TG Title             | наш ключ           |
|----------|----------------------|--------------------|
| 70       | Анонсы \| Орг.       | announcements      |
| 16139    | Вопросы к Женскому   | questions_to_women |
| 16138    | Вопросы к Мужскому   | questions_to_men   |
| 68       | Запросы              | requests           |
| 1        | Болталка             | boltalka           |
| 2262     | Community offerings  | offerings          |
| 13004    | Daily следы          | daily              |
| 14279    | Харвест              | harvest            |
| 11820    | Цитатник             | quotes (НОВЫЙ)     |
| 12003    | Кто мы?              | intro              |
| 13002    | Коммиты              | commits            |

**V7 cross-check вопросов: Telethon topic_id == thread_id бота.** 16139=questions_to_women,
16138=questions_to_men — СОВПАДАЮТ с topic_map. Бот и backfill не разъедутся.

**Решения по топикам (польз. 2026-06-03):**
- Цитатник (11820) → ключ `quotes` (нет в TOPIC_HINTS; для backfill не блокер,
  для дайджеста можно добавить хинт позже).
- sales (177) + together (48) в БД от старого backfill, но таких топиков в ТЕКУЩЕМ
  чате НЕТ (удалены/переименованы). Оставлены как есть (новый backfill их не трогает).
  Ключи уже мигрированы в tg_ (шаг 2).

**⚠️ Баг fetch_topics_list.py (глубже плана):** telethon 1.42.0 — (1) классы
GetForumTopics* лежат в `.messages`, не `.channels`; (2) аргумент `peer=`, не
`channel=`. Обе правки внесены, скрипт отработал. Коммит обновить в telegram-gather.

### Step 3 (done, 2026-06-03) — backfill выполнен
- Сессия: парсили на ЛОКАЛЬНОЙ dev-сессии `telegram_gather_dev` (config SESSION_NAME).
  Боевая `telegram_gather` (Railway) — отдельный auth key, НЕ тронута. Останавливать
  сервер НЕ потребовалось (две независимые сессии = два устройства).
- HTTP API (api.py) НЕ подошёл: нет эндпоинта списка топиков, period max 2w/неэффективный
  фильтр, чужой JSON-формат + пишет ключ `telegram_{id}` (третий формат). Парсили скриптами.
- GATE пройден: offerings (2262) дал chat_id=-1002924475859. Все 11 экспортов проверены.
- ⚠️ В каталоге telegram-gather лежали СТАРЫЕ legacy-экспорты sales/together (13 апр,
  chat_id=None). НЕ заливал их — скопировал в wndrverse только 11 свежих по списку имён.
- НОВЫЙ СЕЗОН: ~месяц назад стартовал новый сезон, старые сообщения удалены в Telegram.
  Поэтому новый экспорт offerings=508 < старый backfill в БД=1523. Старые (удалённые)
  фрагменты СОХРАНЕНЫ в БД (дедуп — INSERT-or-skip, не upsert: существующие не трогаются,
  эмбеддинги+разметка целы). Корпус только растёт.
- Заливка: 4406 inserted (dup-skip по каждому топику = старый сезон схлопнулся).
- Итог БД: total 6534→10940, dup_keys=0, no_chat=0, questions_to_women=339,
  questions_to_men=348, quotes=84. unembedded=4406 (дельта для шага 4).
- ⚠️ Второй баг fetch_topics_list.py: telethon 1.42.0 хочет `peer=`, не `channel=`.
  Исправлено. telegram-gather коммит обновить (amend/новый).

### Решения этой сессии
- Backfill (шаг 3): ВСЕ 12 топиков сейчас (польз.).
- Темп: стоп перед шагом 2 (SQL-деструктив) и шагом 4 (трата OpenAI).
- telegram-gather трогаем совместно; запуск Telethon (шаг 3) — только с подтверждения.
---
