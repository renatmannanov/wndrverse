# Step 2: бэкап таблицы fragments + scp каталога на VPS

> Статус: pending

ПОРЯДОК ВАЖЕН: сначала бэкап (защита данных), потом scp.

## 2a. Бэкап ТОЛЬКО таблицы fragments (откат)

Кладём в `~/wndrverse/` (НЕ /tmp — tmpfs не переживёт ребут VPS). `.sql` держит
PII → удаляется в step_3 сразу после `dup=0`:

```bash
ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95
cd ~/wndrverse
docker compose exec -T db pg_dump -U postgres -d wndrverse -t fragments \
  > ~/wndrverse/fragments_pre_backfill.sql
ls -lh ~/wndrverse/fragments_pre_backfill.sql   # sanity: размер > 0
```

(`fragments_pre_backfill.sql` под data/-паттерном gitignore? — лежит в корне
~/wndrverse, НЕ в data/. Но это VPS, репо там не коммитим вручную; на всякий —
не `git add`.)

## 2b. scp выгруженного каталога на VPS

```powershell
scp -i ~/.ssh/openclaw_hetzner -r `
  C:\Users\renat\projects\telegram-gather\data\exports\wndr_backfill `
  rm_agent@62.238.31.95:~/wndrverse/data/exports/
```

## Критерий готовности

- Бэкап `~/wndrverse/fragments_pre_backfill.sql` существует, размер > 0 (СНАЧАЛА).
- На VPS: `ls ~/wndrverse/data/exports/wndr_backfill/*.json | wc -l` == 11 (ПОТОМ).
