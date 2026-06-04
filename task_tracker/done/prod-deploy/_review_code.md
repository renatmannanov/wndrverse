# Review: Code

> Reviewer: code/config agent
> Date: 2026-06-01
> Scope: план prod-deploy против реального кода и конфигов

---

## Критичное (блокирует выполнение)

### 1. `OnCalendar` с timezone-суффиксом — неверный синтаксис systemd

**Файл:** `task_tracker/todo/prod-deploy/step_3_scheduler_timers.md`, строки 34 и 66

```ini
OnCalendar=*-*-* 09:00:00 Asia/Almaty
OnCalendar=*-*-* 00,06,12,18:00:00 Asia/Almaty
```

Systemd **не поддерживает** timezone-суффикс в `OnCalendar` — он воспринимает `Asia/Almaty`
как часть паттерна и выдаёт ошибку `Failed to parse calendar specification`. Таймер не
загрузится (`systemctl daemon-reload` упадёт с ошибкой юнита).

Правильный подход: поставить `[Timer] AccuracySec=1min` и задать таймзону через
`[Service] Environment=TZ=Asia/Almaty` или через директиву `[Timer] OnCalendar` с UTC
(06:00 UTC = 12:00 Almaty, UTC+6 зимой; или UTC+5 летом — Almaty не переходит DST, всегда UTC+5).

Самый безопасный вариант для VPS — просто писать UTC-эквивалент и добавить комментарий,
либо использовать `OnCalendar=*-*-* 04:00:00` (= 09:00 Asia/Almaty) + убедиться что VPS
в UTC.

Вариант с `--now` (шедулер) работает правильно — проблема только в timer-файлах.

---

### 2. `core.db init` ПЕРЕД restore — двойное создание таблиц несовместимо если дамп полный

**Файлы:** `step_1_vps_db_and_corpus.md` (шаг 4 и 5), `core/db.py`

Шаг 4 плана:
```bash
python -m core.db init   # создаёт схему (нужна ДО restore, если дамп без DDL)
```
Шаг 5: `pg_dump -U postgres -d wndrverse > wndrverse_corpus.sql` без флага `--schema-only` или `--data-only`.

По умолчанию `pg_dump` создаёт **полный дамп** (DDL + данные): `CREATE TABLE`, `CREATE INDEX`, `CREATE EXTENSION vector`. При restore в базу, где схема уже создана через `core.db init`, `psql` выдаст:

```
ERROR: relation "fragments" already exists
ERROR: extension "vector" already exists
```

psql при этом **продолжает** (ошибки не фатальные для `cat | psql`), но в логе будут
ошибки, и HNSW-индекс может дублироваться.

**Конкретная проблема:** `core/db.py:83` — `Base.metadata.create_all(bind=engine)` использует
`CREATE TABLE` (SQLAlchemy без `IF NOT EXISTS` до SA 2.0). А полный pg_dump содержит свой
`CREATE TABLE fragments` — конфликт.

**Решение:** либо делать `core.db init` без restore (и дамп с `--data-only`), либо делать
restore полного дампа без `core.db init` первым (расширение `vector` едет в дампе через
`CREATE EXTENSION IF NOT EXISTS vector`). Рекомендую второй вариант: restore полного дампа сам
создаст схему и расширение. `core.db init` не нужен перед restore.

---

## Важное (стоит исправить до начала)

### 3. pip install в step_1 содержит лишний пакет (`python-dotenv`) и не совпадает с requirements.txt

**Файлы:** `step_1_vps_db_and_corpus.md` (строка 30), `requirements.txt`

Команда в плане:
```bash
pip install python-telegram-bot httpx anthropic sqlalchemy openai pgvector psycopg2-binary python-dotenv
```

В `requirements.txt` присутствует пакет `claude-agent-sdk>=0.1`, которого нет в команде плана.
Хотя `claude-agent-sdk` нужен только для агентов (`agents/_claude/main.py`), а не для бота/дайджеста — это расхождение. Правильнее ставить `pip install -r requirements.txt` вместо ручного списка.

Также в ручном списке нет `numpy>=1.24.0` (есть в requirements.txt). Numpy нужен только для
кластеризации (`core/brain/clustering.py`) — не для MVP. Но расхождение в документации сбивает.

**Рекомендация:** заменить ручной pip install на `pip install -r requirements.txt`.

---

### 4. `python-dotenv` не гарантирован — `load_dotenv` обёрнут в `try/except ImportError`

**Файлы:** `bot/ingest_bot.py:56-58`, `digest/scheduler.py:71-73`, `core/enrich/embedder.py:128-130`

Все три точки входа имеют:
```python
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
```

Если `python-dotenv` не установлен, `.env` молча не загружается. Systemd юнит использует
`EnvironmentFile=.../.env` — это надёжный путь (systemd сам читает файл). Проблемы нет при
правильном деплое. Но если кто-то запустит вручную без `EnvironmentFile`, `.env` не подтянется.

В контексте деплоя — не критично (systemd читает .env). Но в pip install пакет должен быть
установлен: он уже есть в `requirements.txt`.

---

### 5. DATABASE_URL дефолт в коде ссылается на `localhost:5434` — на VPS это правильно, но только если Docker слушает на 127.0.0.1

**Файлы:** `core/db.py:18-21`, `.env.example:2`

Дефолт: `postgresql://postgres:localpass@localhost:5434/wndrverse`

На VPS docker-compose пробрасывает `"5434:5432"`, т.е. Docker слушает `0.0.0.0:5434` (или
`127.0.0.1:5434` в зависимости от daemon config). Если в `.env` на VPS `DATABASE_URL` не задана
явно — процессы используют дефолт с `localpass`. Это совпадает с паролем в docker-compose
(`POSTGRES_PASSWORD: localpass`) — ок для dev/prod на одной машине.

Замечание: план говорит "DATABASE_URL (дефолт localhost:5434 ок)" — верно. Нужно убедиться
что в `.env` на VPS явно прописан DATABASE_URL (либо явно не прописан и дефолт устраивает).
Без явной записи в `.env` пароль `localpass` должен совпадать с тем что в docker-compose на VPS
(они одинаковы — ок).

---

## Мелочи (можно по ходу)

### 6. `WNDR_DIGEST_AT` в .env — на проде не влияет, но вводит в заблуждение

**Файл:** `step_3_scheduler_timers.md`, комментарий в тексте; `.env.example:20`

План правильно отмечает что `WNDR_DIGEST_AT` на проде не влияет (sleep-loop не запускается,
время задаёт `OnCalendar`). Но `.env.example` включает эту переменную без пометки. Стоит добавить
комментарий в `.env.example`: `# на проде с systemd-timer это значение игнорируется; время
задаёт OnCalendar в wndr-digest.timer`.

---

### 7. `wndr-embedder.service` не имеет `PYTHONUTF8=1`

**Файл:** `step_3_scheduler_timers.md`, строка 54-59 (embedder service)

В `wndr-ingest-bot.service` есть `Environment=PYTHONUTF8=1`, а в `wndr-embedder.service` —
нет. Embedder логирует тексты фрагментов при ошибках. На VPS с Ubuntu UTF-8 по умолчанию это не
критично, но для консистентности стоит добавить.

---

### 8. `pg_dump` в плане без явного флага — нужно добавить `--no-owner --no-privileges`

**Файл:** `step_1_vps_db_and_corpus.md`, строка 51

```bash
pg_dump -U postgres -d wndrverse > wndrverse_corpus.sql
```

При restore на VPS пользователь postgres может быть идентичен (Docker), но `--no-owner
--no-privileges` делает дамп portable и избегает `ALTER TABLE ... OWNER TO` при restore в
другой среде. Не блокирует, но стоит добавить.

---

## Не найдено проблем

- **`python -m bot.ingest_bot`**: `__main__` есть (`bot/ingest_bot.py:68`), `main()` вызывается,
  `BOT_TOKEN_INGEST` читается правильно.
- **`python -m digest.scheduler --now`**: `--now` поддержан (`scheduler.py:78`), `__main__` есть
  (`scheduler.py:102`), `load_dotenv` вызывается.
- **`python -m core.enrich.embedder`**: `__main__` есть (`embedder.py:148`), `load_dotenv` есть,
  `--estimate` поддержан.
- **`python -m core.db init`**: `__main__` есть и корректно делегирует в `core.db.init_db()`
  через canonical-import (workaround для двойного Base).
- **pgvector в docker-образе**: образ `pgvector/pgvector:pg16` уже содержит расширение. `init_db()`
  вызывает `CREATE EXTENSION IF NOT EXISTS vector` — безопасно. При restore полного дампа
  расширение едет в дампе как `CREATE EXTENSION IF NOT EXISTS vector` тоже.
- **Имена env-переменных**: совпадают между `.env.example`, кодом (`scheduler.py`, `ingest_bot.py`)
  и CLAUDE.md. Нет расхождений в именах `WNDR_DIGEST_TZ`, `WNDR_DIGEST_AT`, `WNDR_DIGEST_PERIOD`,
  `WNDR_DIGEST_TOPICS`, `WNDR_DIGEST_DM_USER_ID`, `BOT_TOKEN_INGEST`, `WNDR_TOPIC_MAP`.
- **psycopg2-binary, pgvector, sqlalchemy, openai**: все есть в `requirements.txt`.
- **`python-telegram-bot`**: есть в `requirements.txt`, версия `>=22.0` соответствует API
  использованному в коде (`Application.builder()`).
