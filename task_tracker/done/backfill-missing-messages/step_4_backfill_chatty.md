# Step 4: Добивка болтливых топиков без лимита (УСЛОВНЫЙ)

> Статус: pending
> Выполняется ТОЛЬКО если step_3 выявил недокоп (700 не докопали до 3 июня).

## Когда нужен

Болтливый топик, где с 3 июня появилось > 700 сообщений → `--limit 700` не достал
до стыка, осталась дырка между 3 июня и минимумом новой пачки.

## Команды

Для каждого недокопанного топика (локально, telegram-gather):

```powershell
cd C:\Users\renat\projects\telegram-gather
python fetch_topic.py "WNDR chat" --topic-id <ID> --name <key> -o data/exports/wndr_backfill2
# без --limit = вся история; дедуп отсечёт всё уже залитое
```

Затем как в step_2/step_3, но в каталог `wndr_backfill2`:

```powershell
scp -i ~/.ssh/openclaw_hetzner -r `
  C:\Users\renat\projects\telegram-gather\data\exports\wndr_backfill2 `
  rm_agent@62.238.31.95:~/wndrverse/data/exports/
```
```bash
cd ~/wndrverse
source .venv/bin/activate   # venv ОБЯЗАТЕЛЕН (как в step_3)
python -m core.ingest.loaders --dir data/exports/wndr_backfill2
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) total, count(*)-count(DISTINCT external_id) dup FROM fragments;"
```

## Критерий готовности

- min(created_at) среди новых строк недокопанного топика дотянулся до ~3 июня
  (стык с baseline закрыт, дырки нет).
- `dup=0` сохранён.
