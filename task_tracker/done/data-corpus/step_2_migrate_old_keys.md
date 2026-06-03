# Шаг 2: Миграция старых ключей на формат tg_ (SQL-апдейт, вариант В)

> Зависит от: шаг 1 (новый формат ключа определён)
> Статус: [ ] pending

## Задача

Привести ВСЕ старые ключи к единому формату `tg_{chat_id}_{msg_id}`. Два пласта
старых данных (на 2026-06-01, повторно сверить count перед работой):
- **~6530 фрагментов** с `channel_id IS NULL`, ключ `wndr_WNDR chat_{id}` (старый
  файловый backfill). Им проставляем `channel_id = -1002924475859` (все из WNDR) +
  ключ `tg_-1002924475859_{msg_id}`.
- **4 фрагмента** `tgbot_-1003905781841_{id}` (topic raymann_agents, `channel_id`
  ЗАПОЛНЕН = -1003905781841 — тестовый канал из realtime-bot-ingest, НЕ WNDR). У них
  channel_id уже верный, надо только переименовать ключ `tgbot_…` → `tg_…` (убрать
  `bot`), чтобы совпал с новым форматом бота из шага 1.

⚠️ Числа (6530 / 4 / 6534 total) — это snapshot планирования. ПЕРЕД работой
повторить count на текущей БД (могли добавиться realtime-фрагменты). Источник правды
— фактический `SELECT`, не число из плана.

Зачем: после миграции новый backfill (шаг 3) и realtime бота схлопнутся по
совпадающему ключу вместо дублирования.

### ⚠️ ДЕСТРУКТИВНАЯ ОПЕРАЦИЯ — порядок строгий

**0. Бэкап БД ДО апдейта (обязательно).**
```bash
docker compose exec -T db pg_dump -U postgres -d wndrverse -t fragments \
  > backup_fragments_before_migrate.sql
# проверить что файл непустой и содержит COPY/INSERT
```

**1. Пред-проверки (повторить на текущей БД — порядок: СНАЧАЛА проверки, ПОТОМ
сообщить пользователю, ТОЛЬКО затем апдейт).**
```bash
# (a) snapshot эмбеддингов ДО — для пост-проверки сохранности (V4):
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) FILTER (WHERE embedding IS NOT NULL) AS emb_before, count(*) AS total_before FROM fragments;"
# запомнить emb_before — после апдейта должно совпасть.

# (b) NULL-пласт: все из одного источника:
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT source, count(*) FROM fragments WHERE channel_id IS NULL GROUP BY source;"
# (c) msg_id извлекается чисто (число) у всех NULL-строк:
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) AS total, count(*) FILTER (WHERE split_part(external_id,'_',3) ~ '^[0-9]+\$') AS clean FROM fragments WHERE channel_id IS NULL;"
# (d) нет коллизий msg_id между топиками:
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT split_part(external_id,'_',3) AS msgid, count(*) FROM fragments WHERE channel_id IS NULL GROUP BY msgid HAVING count(*) > 1;"
# (e) tgbot_-пласт: сколько и какие channel_id (ожидаем raymann_agents, -1003905781841):
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT channel_id, topic, count(*) FROM fragments WHERE external_id LIKE 'tgbot_%' GROUP BY channel_id, topic;"
# Ожидаем: (b) только telegram; (c) total==clean; (d) 0 строк; (e) только tgbot из
# не-WNDR каналов (если вдруг есть tgbot с chat_id=-1002924475859 — это уже бот успел
# записать WNDR realtime, он схлопнется с backfill сам, мигрировать его НЕ нужно,
# только переименовать ключ как в (g)).
```
Если (b)/(c)/(d) НЕ сходятся (нечисловой msgid, коллизии, чужой source) — СТОП,
разобраться. Иначе UNIQUE-constraint сломается.

**2. Сообщить пользователю: «обновлю N строк (NULL-пласт) + M строк (tgbot→tg), бэкап
сделан» → дождаться «ок».** N/M — из фактических count (не из плана).

**3. Апдейт обоих пластов (одна транзакция).**
```sql
BEGIN;
-- (f) NULL-пласт (старый файловый backfill, все WNDR):
UPDATE fragments
SET channel_id = -1002924475859,
    external_id = 'tg_-1002924475859_' || split_part(external_id, '_', 3)
WHERE channel_id IS NULL;
-- (g) tgbot_-пласт: переименовать ключ tgbot_ → tg_ (channel_id уже верный):
UPDATE fragments
SET external_id = 'tg_' || substring(external_id from 7)   -- срезаем 'tgbot_'
WHERE external_id LIKE 'tgbot_%';
-- проверить затронутые строки = ожидаемым N+M, проверить отсутствие дублей ключа:
-- SELECT count(*) - count(DISTINCT external_id) FROM fragments;  -- должно быть 0
COMMIT;   -- если что-то не так до COMMIT → ROLLBACK
```
Запуск через `docker compose exec db psql`. Если затронуто НЕ ожидаемое количество
или появились дубли ключа — `ROLLBACK`, разобраться.

### Заметка
Эмбеддинги старых СОХРАНЯЮТСЯ (апдейтим только external_id + channel_id, НЕ трогаем
embedding). В этом весь смысл варианта В — не платить за эмбеддинги повторно.
Пост-проверка (V4): `emb_before == emb_after` (см. критерии).

## Тесты

SQL-миграция — юнит-тестов нет. Проверка — запросы ниже.

## Команды для верификации

```bash
# нет дублей ключа во всей таблице:
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) - count(DISTINCT external_id) AS dup_keys FROM fragments;"
# ожидаем: 0

# старых (channel_id NULL) больше нет:
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) FROM fragments WHERE channel_id IS NULL;"
# ожидаем: 0

# tgbot_ ключей не осталось (все переименованы в tg_):
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) FROM fragments WHERE external_id LIKE 'tgbot_%';"
# ожидаем: 0

# эмбеддинги НЕ пострадали (сверить с emb_before из пред-проверки a):
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) FILTER (WHERE embedding IS NOT NULL) AS emb_after FROM fragments;"
# ожидаем: emb_after == emb_before

# формат ключа новый, эмбеддинги на месте:
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT external_id, channel_id, (embedding IS NOT NULL) AS has_emb FROM fragments WHERE topic='offerings' LIMIT 3;"
# ожидаем: tg_-1002924475859_*, channel_id заполнен, has_emb = t
```

## Критерии готовности

- [ ] Бэкап `backup_fragments_before_migrate.sql` создан ДО апдейта.
- [ ] Пред-проверки сошлись (числовой msgid, нет коллизий, один source); snapshot
      `emb_before` зафиксирован.
- [ ] Пользователь подтвердил деструктив («ок») до апдейта (числа N/M — фактические).
- [ ] После апдейта: `channel_id IS NULL` = 0; `tgbot_%` = 0; `dup_keys` = 0.
- [ ] Эмбеддинги сохранены: `emb_after == emb_before` (V4).
