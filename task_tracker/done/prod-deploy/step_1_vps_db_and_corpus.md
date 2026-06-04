# Шаг 1: Docker + БД на VPS + перенос корпуса дампом

> Зависит от: план data-corpus = done (влит в master; корпус 10940, dup=0, unemb=0)
> Статус: [x] DONE (2026-06-03)

## Задача

Развернуть код на VPS, поставить Docker, поднять postgres+pgvector, восстановить
корпус ПОЛНЫМ дампом локальной БД (без предварительного `core.db init`).

### Зафиксированные факты (проверено на сервере 2026-06-03)

- **Docker НЕ установлен** (нет docker/podman/нативного postgres). progress.md ранее
  ошибочно говорил «Docker уже стоит» — НЕВЕРНО. Ставим Docker в п.1.
- **Каталог на VPS = `~/wndrverse`** (`/home/rm_agent/wndrverse`). НЕ внутри
  `~/claude-hub` (это отдельный git-репо-scaffold под Claude-агентов; clone туда даёт
  вложенный git). Этот путь подставлен ВО ВСЕ systemd-юниты step_2/step_3.
- **sudo passwordless** у rm_agent — работает.
- **Порт 5434** на VPS свободен (нет ни одного DB-порта).
- **Ветка = `master`** (data-corpus влит ff, c095854). НО: push на origin локально
  ещё НЕ сделан — перед clone на VPS нужен `git push origin master` (см. п.0).

### 0. Push master на origin (локально, ДО clone на VPS)
data-corpus влит в master локально, но НЕ запушен. VPS клонит с GitHub → нужен push.
```bash
git log origin/master..master --oneline   # покажет неотправленные коммиты
git push origin master
```

### 1. Установить Docker на VPS
```bash
ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker rm_agent          # чтобы docker без sudo
# ПЕРЕЛОГИНИТЬСЯ (новый SSH-сеанс) чтобы группа docker применилась:
exit
ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95
docker --version && docker compose version && docker ps   # ps без ошибки прав
```
⚠️ Не трогать другие сервисы — Docker ставится с нуля, конфликтов нет (проверено:
ни OpenClaw, ни Hermes docker не используют — их контейнеров не было).

### 2. Код на VPS
```bash
cd ~
git clone https://github.com/renatmannanov/wndrverse.git   # → ~/wndrverse
cd ~/wndrverse
git checkout master                        # код дедупа здесь (data-corpus влит)
git log --oneline -3                       # убедиться, что виден c095854 (или новее)
```

### 3. Зависимости (через requirements.txt — V3)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 4. .env + topic_map.json на VPS (секреты вручную, значения НЕ из плана)
`.env` (свериться с `.env.example`):
- DATABASE_URL (дефолт `postgresql://postgres:postgres@localhost:5434/wndrverse` ок)
- OPENAI_API_KEY, BOT_TOKEN_INGEST, WNDR_DIGEST_DM_USER_ID, WNDR_TOPIC_MAP
- WNDR_DIGEST_TOPICS=questions_to_women,questions_to_men (после тестов → расширить)

`topic_map.json`: скопировать из `topic_map.example.json`, вписать реальные
chat_id/thread_id (chat_id=-1002924475859; 16139→questions_to_women;
16138→questions_to_men).
```bash
git check-ignore .env core/ingest/topic_map.json   # оба должны печататься
```

### 5. Поднять БД (ПУСТУЮ, БЕЗ init — restore несёт схему сам)
```bash
ss -tlnp | grep 5434 || echo "5434 free"     # подтвердить свободу порта
docker compose up -d db
docker compose ps                             # db healthy
# НЕ запускать `python -m core.db init` — полный дамп уже содержит DDL+extension.
```

### 6. Создать ПОЛНЫЙ дамп локально (K1+K2 — один способ)
```bash
# ЛОКАЛЬНО (Windows, в каталоге проекта):
docker compose exec -T db pg_dump -U postgres -d wndrverse > wndrverse_corpus.sql
# полный дамп: DDL + CREATE EXTENSION vector + данные + индексы.
# НЕ --data-only. *.sql уже в .gitignore (подтверждено) → в git не попадёт.
```
⚠️ Дамп содержит PII (author_name) — едет на VPS осознанно (решение 2).

### 7. Перенести и восстановить
```bash
# ЛОКАЛЬНО: скопировать на VPS
scp -i ~/.ssh/openclaw_hetzner wndrverse_corpus.sql rm_agent@62.238.31.95:~/wndrverse/
# НА VPS: восстановить в пустую БД (без предварительного init)
cd ~/wndrverse
cat wndrverse_corpus.sql | docker compose exec -T db psql -U postgres -d wndrverse
```
Полный дамп воссоздаёт extension+схему+данные одной командой → нет конфликта
`relation already exists` (тот конфликт был бы при init→restore; init убран).

### 8. Удалить PII-дамп после успешного restore (V7)
```bash
# НА VPS (после проверки count в «Командах для верификации»):
rm ~/wndrverse/wndrverse_corpus.sql
# ЛОКАЛЬНО:
rm wndrverse_corpus.sql
```

## Команды для верификации

```bash
# на VPS, из ~/wndrverse:
docker compose ps                                   # db healthy
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) AS total, count(*)-count(DISTINCT external_id) AS dup, \
   count(*) FILTER (WHERE embedding IS NULL) AS unemb FROM fragments;"
# ожидаем: total=10940; dup=0; unemb=0  (== локальная БД)
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT topic, count(*) FROM fragments GROUP BY topic ORDER BY count(*) DESC;"
# ожидаем среди прочего: questions_to_women≈339, questions_to_men≈348
git check-ignore .env core/ingest/topic_map.json
```

## Критерии готовности

- [x] master запушен на origin (clone на VPS видит f8948a3).
- [x] Docker установлен (29.1.3); `docker ps` без sudo (rm_agent в группе docker).
- [x] Код на VPS в `~/wndrverse`, ветка master; `.venv` + `pip -r requirements.txt`.
- [x] `docker compose ps` — db healthy; init НЕ запускался (restore несёт схему).
- [x] Корпус восстановлен ПОЛНЫМ дампом: total=10940; dup=0; unemb=0 (== локалка).
- [x] `.env` (chmod 600), `topic_map.json` на VPS, gitignored. resolve_topic смоук ОК.
- [x] PII-дамп `.sql` удалён с VPS и локально после restore.

## Факты выполнения (2026-06-03)
- Docker 29.1.3 + Compose 2.40.3 поставлены (apt). Ядро обновилось до 6.8.0-117 —
  reboot рекомендован, но НЕ обязателен сейчас (БД переживёт; отложено).
- Дамп 210MB, md5 совпал VPS↔локалка, restore exit=0, 0 ошибок.
- pg 16.14 обе стороны → `\restrict` директива совместима.
- DATABASE_URL в .env НЕ задан — дефолт core/db.py совпадает с compose (localpass).
