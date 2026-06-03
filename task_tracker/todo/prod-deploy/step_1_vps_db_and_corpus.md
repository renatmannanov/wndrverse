# Шаг 1: БД на VPS + перенос корпуса дампом

> Зависит от: план data-corpus = done (дамп готов)
> Статус: [ ] pending

## Задача

Развернуть код на VPS, поднять postgres+pgvector, восстановить корпус из дампа
локальной БД (план data-corpus). ДО — решить каталог core на VPS (решение 6).

### 0. Каталог на VPS
Deploy-карта (CLAUDE.md) деплоит `wndrverse_agent_claude`. core/bot/digest — в репо
`wndrverse`. Каталога под пайплайн в карте нет. **Зафиксировано:
`~/claude-hub/projects/wndrverse`** (туда мигрирует агент по карте; если занято —
`~/claude-hub/projects/wndrverse-core`). Записать выбор в CLAUDE.md (step_5).

### 1. Код на VPS
```bash
ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95
cd ~/claude-hub/projects
git clone https://github.com/renatmannanov/wndrverse.git || (cd wndrverse && git pull)
cd wndrverse
git checkout <ветка с влитым data-corpus>   # код дедупа должен быть здесь
```

### 2. Зависимости
```bash
docker --version && docker compose version   # Docker уже на VPS
python3 -m venv .venv && source .venv/bin/activate
pip install python-telegram-bot httpx anthropic sqlalchemy openai pgvector psycopg2-binary python-dotenv
```

### 3. .env + topic_map.json на VPS (секреты вручную, значения НЕ из плана)
`.env`: DATABASE_URL (дефолт localhost:5434 ок), OPENAI_API_KEY, BOT_TOKEN_INGEST,
WNDR_DIGEST_DM_USER_ID, WNDR_TOPIC_MAP. Свериться с `.env.example`.
`topic_map.json`: скопировать из example, вписать реальные chat_id/thread_id.
`git check-ignore` обоих.

### 4. Поднять БД (пустую) + схема
```bash
docker compose up -d db
docker compose ps            # healthy
python -m core.db init       # создаёт схему (нужна ДО restore, если дамп без DDL)
```
Порт 5434 на VPS — проверить, что свободен (не занят ayda/другим). Если занят —
поменять маппинг в docker-compose.yml ТОЛЬКО на VPS.

### 5. Перенести дамп и восстановить корпус
```bash
# локально: сделать дамп (если не сделан в data-corpus)
docker compose exec -T db pg_dump -U postgres -d wndrverse > wndrverse_corpus.sql
# скопировать на VPS:
scp -i ~/.ssh/openclaw_hetzner wndrverse_corpus.sql rm_agent@62.238.31.95:~/claude-hub/projects/wndrverse/
# на VPS — восстановить:
cat wndrverse_corpus.sql | docker compose exec -T db psql -U postgres -d wndrverse
```
⚠️ Дамп содержит PII (имена в author_name) — едет на VPS (решение 2, осознанно).
Дамп-файл НЕ коммитить (gitignore `*.sql`).

## Тесты

Инфраструктурный шаг. Проверка — count совпадает с локальной БД.

## Команды для верификации

```bash
# на VPS:
docker compose ps                                   # db healthy
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) AS total, count(*)-count(DISTINCT external_id) AS dup, \
   count(*) FILTER (WHERE embedding IS NULL) AS unemb FROM fragments;"
# ожидаем: total == локальный count; dup=0; unemb=0
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT topic, count(*) FROM fragments GROUP BY topic ORDER BY count(*) DESC;"
git check-ignore .env core/ingest/topic_map.json
```

## Критерии готовности

- [ ] Каталог core на VPS выбран, зафиксирован (→ CLAUDE.md в step_5).
- [ ] `docker compose ps` — db healthy на VPS; схема есть.
- [ ] Корпус восстановлен из дампа: total совпадает с локальным; dup=0; unemb=0.
- [ ] `.env`, `topic_map.json` на VPS, gitignored. Дамп-файл не в git.
- [ ] Порт 5434 не конфликтует.
