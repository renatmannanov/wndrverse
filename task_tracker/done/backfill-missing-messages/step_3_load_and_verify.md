# Step 3: Заливка loader на VPS + проверка

> Статус: pending
> ⚠️ Заливка в ПРОД-БД (добавит сотни строк). Апрув пользователя получен 2026-06-05
>   (зафиксирован в PLAN.md «Решения этой сессии»). НЕ запускать без этого апрува.

## Команды (на VPS, cwd = ~/wndrverse)

```bash
cd ~/wndrverse
source .venv/bin/activate   # venv ОБЯЗАТЕЛЕН (sqlalchemy/openai не в системном python)
python -m core.ingest.loaders --dir data/exports/wndr_backfill
```

Проверка — дедуп цел и даты сдвинулись:

```bash
# 1) per-topic last_msg должен сдвинуться к 2026-06-05 по 11 застывшим топикам
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT topic, max(created_at) AS last_msg, count(*) AS n FROM fragments GROUP BY topic ORDER BY max(created_at) DESC;"

# 2) dup ДОЛЖЕН быть 0; total > 11024
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) total, count(*)-count(DISTINCT external_id) dup FROM fragments;"
```

## Сравнение с baseline (PLAN.md)

- requests/boltalka/announcements/offerings/daily/harvest/quotes — ждём сдвиг к 06-05
  (или к последней реальной дате топика, если в нём с 3 июня просто не писали).
- intro/commits/together/sales — могли вообще не обновиться (тихие); это нормально,
  если в них действительно не было новых сообщений.

## Проверка на «недокоп» (чёткий триггер step_4)

Логика: лимит 700 берёт 700 САМЫХ СВЕЖИХ сообщений топика. Если в JSON-выгрузке
`total_messages == 700` (упёрлось в лимит) И минимальная дата выгрузки > baseline-даты
топика из PLAN.md — значит 700 НЕ докопали до стыка, между baseline и минимумом
выгрузки дырка → топик в step_4.

Тест по выгруженным JSON (локально или на VPS, до/после заливки — данные те же):

```powershell
# total_messages == 700 у какого-либо топика = упёрлись в лимит = кандидат на недокоп
Get-ChildItem data/exports/wndr_backfill/*.json | ForEach-Object {
  $j = Get-Content $_ -Raw | ConvertFrom-Json
  $minDate = ($j.threads.root + $j.threads.replies | Where-Object {$_} | ForEach-Object {$_.date} | Sort-Object)[0]
  "{0,-16} total={1,4}  min_date={2}" -f $j.topic_name, $j.total_messages, $minDate
}
```

Правило (однозначное, без «на усмотрение»):
- `total_messages < 700` → весь топик влез, докопали до начала → step_4 НЕ нужен.
- `total_messages == 700` И `min_date` НЕ дотягивает до baseline-даты топика
  (из таблицы в PLAN.md) → недокоп → топик идёт в step_4.

Подтверждение в БД (новые строки за период):

```bash
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT topic, min(created_at), max(created_at), count(*) FROM fragments
   WHERE topic IN ('boltalka','offerings','daily','requests')
     AND created_at > '2026-06-03' GROUP BY topic;"
```

## Критерий готовности

- `dup=0` после заливки.
- `last_msg` по застывшим топикам сдвинулся (где были новые сообщения).
- total вырос относительно 11024.
- Решено, нужен ли step_4 (список недокопанных топиков или «не нужен»).
- Бэкап удалён ПОСЛЕ успешной проверки (`dup=0` подтверждён):
  `rm ~/wndrverse/fragments_pre_backfill.sql` (PII, не держим лишнего).
