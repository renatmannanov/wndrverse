# Шаг 1: Каркас core/ + Docker (postgres+pgvector)

> Зависит от: нет
> Статус: [ ] pending

## Задача

Создать скелет проекта и поднять БД. Это фундамент — без него остальные шаги
негде запускать.

1. Создать структуру пустых пакетов:
   ```
   core/__init__.py
   core/ingest/__init__.py
   core/store/__init__.py
   core/enrich/__init__.py
   core/brain/__init__.py
   core/llm/__init__.py
   core/prompts/            (папка под .md, без __init__)
   delivery/__init__.py
   data/.gitkeep
   ```

2. `core/db.py` — перенести из `03_ayda_think/storage/db.py`, но:
   - Выкинуть классы `User`, `ChannelMapping`, `ChannelMessageMapping` и их функции
     (`get_user_spreadsheet`, `save_user` и т.д.) — это специфика ayda, нам не нужно.
   - Оставить: `Base`, `engine`, `SessionLocal`, `pgvector_available`, `init_db()`.
   - `DATABASE_URL` default → `postgresql://postgres:localpass@localhost:5434/wndrverse`
     (порт 5434, чтобы не конфликтовать с ayda 5433; имя БД `wndrverse`).
   - В `init_db()` убрать ALTER про clusters.name и старые миграции NULL booleans —
     у нас чистая БД, таблицы создаются сразу правильными в шаге 2. Оставить только:
     `CREATE EXTENSION vector`, `Base.metadata.create_all`, создание HNSW-индекса.
   - Импорт моделей в `init_db()` поменять на `import core.store.fragments_db`.
     ВНИМАНИЕ: этот импорт в ayda НЕ на уровне модуля, а ВНУТРИ функции `init_db()`
     (db.py:76 `import storage.fragments_db`). Легко пропустить при поиске-замене —
     проверить отдельно, иначе `python -m core.db init` упадёт ModuleNotFoundError при вызове.

3. `docker-compose.yml` в корне:
   - Сервис `db`: образ `pgvector/pgvector:pg16`, порт `5434:5432`,
     env `POSTGRES_DB=wndrverse POSTGRES_PASSWORD=localpass`, том `pgdata:/var/lib/postgresql/data`.
   - (app-сервис пока не обязателен — MVP запускаем локально питоном; добавить
     закомментированный шаблон app для будущего, чтобы было видно куда расти.)

4. `.env.example` в корне (дополнить существующий, не затирая чужие переменные):
   ```
   DATABASE_URL=postgresql://postgres:localpass@localhost:5434/wndrverse
   OPENAI_API_KEY=
   WNDR_EXPORTS_DIR=
   ```

5. `.gitignore` в корне (дополнить, не затирая существующее) — ОБЯЗАТЕЛЬНО до шага 4,
   иначе реальные сообщения людей попадут в git:
   ```
   data/
   .env
   ```
   Папку `data/.gitkeep` оставить (чтобы пустая структура была в git), но всё остальное
   в `data/` игнорируется. Проверить: `git check-ignore data/test.json` → печатает путь.

6. `requirements.txt` — основные зависимости MVP (не удаляя существующие):
   `sqlalchemy`, `psycopg2-binary`, `pgvector>=0.2.0`, `openai>=1.0.0`.
   `numpy>=1.24.0` — тоже в основные (нужен enrich).
   **hdbscan/umap-learn — в ОТДЕЛЬНЫЙ файл** `requirements-clustering.txt`:
   `hdbscan>=0.8.0`, `umap-learn>=0.5.0`. Причина: на Windows это тяжёлые C-зависимости
   (нужен компилятor MSVC), нужны ТОЛЬКО для clustering (вторая фича, не MVP smoke).
   Не блокировать установку основного пайплайна их сборкой.

7. `core/db.py` сделать запускаемым: `python -m core.db init` → вызывает `init_db()`.

## Тесты

Юнит-тесты не нужны (инфраструктурный шаг). Проверка — командами ниже.

## Команды для верификации

```bash
docker compose up -d db
docker compose ps                          # db в статусе running/healthy
python -m core.db init                     # без ошибок, в логе "pgvector extension enabled"
docker compose exec db psql -U postgres -d wndrverse -c "\dt"   # видны таблицы fragments/clusters/...
docker compose exec db psql -U postgres -d wndrverse -c "\dx"   # vector в списке extensions
git check-ignore data/test.json            # печатает "data/test.json" → data/ игнорируется
```

## Критерии готовности

- [ ] `docker compose up -d db` поднимает контейнер без ошибок
- [ ] `python -m core.db init` отрабатывает, в логе "pgvector extension enabled"
- [ ] `\dx` показывает extension `vector`
- [ ] Структура папок core/ + delivery/ создана, все `__init__.py` на месте
- [ ] В `core/db.py` нет User/ChannelMapping (только Base/engine/SessionLocal/init_db)
- [ ] `git check-ignore data/test.json` подтверждает что `data/` в .gitignore
- [ ] hdbscan/umap вынесены в `requirements-clustering.txt` (основной requirements ставится без них)
