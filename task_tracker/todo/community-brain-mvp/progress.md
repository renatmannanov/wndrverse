# Progress Log — community-brain-mvp

## Контекст для агента

**Что строим:** ядро `core/` для wndrverse — превращает сообщения сообщества в
знание (хранит, размечает embeddings, генерит дайджест). Первая фича — дайджест.

**Откуда переносим код (читать как источник, копировать + адаптировать):**
- `C:\Users\renat\projects\03_ayda_think\storage\fragments_db.py` → `core/store/fragments_db.py`
  (модель Fragment УЖЕ имеет sender_id/channel_id/message_thread_id — строки 53-55)
- `...\03_ayda_think\storage\db.py` → `core/db.py` (выкинуть User/ChannelMapping)
- `...\03_ayda_think\services\normalizer_service.py` → `core/enrich/embedder.py`
- `...\03_ayda_think\services\synthesis_service.py` → `core/brain/synthesis.py`
  (промпт переписать под СООБЩЕСТВО, не «один человек»; вынести в core/prompts/*.md)
- `...\03_ayda_think\services\clustering_service.py` → `core/brain/clustering.py`

**Источник данных (НЕ хардкодить путь, через env WNDR_EXPORTS_DIR):**
- `C:\Users\renat\projects\telegram-gather\data\exports\wndr\wndr_topic_*.json`
- 10 топиков, ~8.5MB. Формат: `{chat_name, topic_name, threads:[{root:{msg}, replies:[{msg}]}]}`
- `{msg}` = `id, date(ISO), user_id, sender_name, username, text, char_count, reply_to_msg_id, reactions[]`
- Парсер периода (1w/3d/12h) — взять из `telegram-gather\fetch_chat.py:parse_period`

**Ключевые ограничения:**
- БД отдельная `wndrverse`, порт 5434 (ayda на 5433 — НЕ конфликтовать)
- LLM: всё OpenAI (text-embedding-3-small + gpt-4o-mini). Слой core/llm тонкий —
  синтез позже на Claude. НЕ тащить transcription_service (Whisper не нужен).
- Фрагмент = 1 сообщение, привязка thread_id. Мусор <150 символов в синтез не идёт.
- Ключ человека = user_id (Telegram ID).
- НЕ трогать: curator/, agent-template/, test_stand.py.
- НЕ коммитить данные сообщества в git (data/ в .gitignore).

**Не делать в MVP (future):** realtime-бот, расписания, поиск по людям,
доставка в telegram, кейсы «ДО и ПОСЛЕ», переезд curator (он в backlog).

**Семантика топиков (для промпта синтеза):** harvest=итоги цикла,
commits=начало цикла, daily=прогресс/дневник, offerings=офферы, requests=запросы,
intro=знакомство, sales=продажи, boltalka=болталка, announcements=анонсы, together=ретро.

**PII (важно!):** в OpenAI уходит ТОЛЬКО текст (embed) и `[#id]+текст` (синтез).
Имена/username НЕ передаются в LLM. Имена хранятся в БД, подставляются на ВЫВОДЕ
(delivery): `[#id]` → `[Имя, дата]`. None-автор → `[аноним, дата]`.

**Грабли из ревью плана (НЕ наступить):**
- null-root треды есть в КАЖДОМ JSON-файле (`{"root": null, "replies":[...]}`) — обработать, не падать.
- 3 переносимых сервиса тянут get_openai_client из transcription_service (→ config ayda).
  Заменить ВСЕ импорты на core.llm.client. Иначе ModuleNotFoundError.
- `import storage.fragments_db` в ayda — ВНУТРИ функции init_db(), не на уровне модуля. Поправить.
- `_extract_tags` в коде ayda НЕТ — написать с нуля (тривиально).
- parse_period из telegram-gather НЕ знает `m` (месяц) — писать свой в delivery/cli.py.
- get_fragments_for_digest возвращает created_at СТРОКОЙ (.isoformat) — synthesis делает [:10].
- Деньги на API: реальный enrich — только после --estimate и «ок» пользователя.
- `down -v` (шаг 8) стирает том — спросить пользователя, не сбрасывать если enrich сделан.
- hdbscan/umap — в requirements-clustering.txt (отдельно), не блокировать MVP их сборкой.

## Learnings

### Шаг 1+2 (done, 2026-05-23)
- **Окружение:** Python 3.14.0, Docker Desktop, БД поднята (`pgvector/pgvector:pg16`,
  порт 5434, extension vector 0.8.2, healthcheck). Деп-ы основного пайплайна стоят.
- **`.gitignore`/`requirements.txt` УЖЕ существовали** (от curator/agent-template) — не
  затёр, `data/` уже был в .gitignore. requirements дописал блоком. `.gitkeep` в data/
  попадёт в git только через `git add -f` (вся папка игнорится).
- **`data/` git'ом НЕ отслеживается** (там были чужие локальные bus_posts.json/runs/ — вне git).
- **ГРАБЛЯ (новая, не из ревью): double-import при `python -m core.db`.** Файл грузится
  как `__main__` И как `core.db`. fragments_db делает `from core.db import Base` → грузит
  core.db ВТОРОЙ раз с другим Base. `__main__.init_db()` звал create_all на пустом Base →
  0 таблиц, потом "relation fragments does not exist". Фикс: в `if __name__=='__main__'`
  делегировать в `import core.db as canonical; canonical.init_db()`. Тот же паттерн учесть
  для всех `python -m core.X` точек входа (ingest/enrich/delivery) — НЕ звать init/main из
  __main__-копии напрямую если она трогает Base/модели.
- **Зависимость шагов 1↔2:** `init_db()` импортит fragments_db, который есть только после
  шага 2. Поэтому проверка `init` шага 1 реально прошла ПОСЛЕ написания шага 2. Порядок плана
  не нарушен, просто финальная команда шага 1 завершилась вместе со 2.
- Поправил deprecation: `declarative_base` беру из `sqlalchemy.orm` (не `.ext.declarative`).
- Из fragments_db выкинул неиспользуемое в MVP (search_by_keywords/hybrid, get_fragments_clusters,
  artifacts_by_cluster/topic, channel-mappings). Оставил всё для enrich/synthesis/clustering.
  Добавил `count_unembedded_fragments`/`sum_unembedded_chars` для шага 5 `--estimate`.
- **Запуск скриптов с кириллицей:** `python -c` под PowerShell коверкает UTF-8 (NameError на
  кириллице). Решение: писать .py-файл с `PYTHONUTF8=1` и `PYTHONPATH=<root>` (если файл не в корне).
- Step-2 тест прошёл: insert пишет topic/author_name/sender_id; get_fragments_for_digest
  фильтрует по topic+since+min_chars(150); created_at возвращается СТРОКОЙ ([:10] работает).

### Шаг 3 (done, 2026-05-23)
- `core/llm/client.py`: get_openai_client (lazy singleton) + embed + complete.
  Константы EMBED_MODEL=text-embedding-3-small (1536), COMPLETION_MODEL=gpt-4o-mini.
  Грузит .env через python-dotenv (для CLI-прогонов). НЕ тащит transcription_service/Whisper.
- **OPENAI_API_KEY взят из ayda** `03_ayda_think/.env` (len 164), записан в наш `.env`
  программно (значение не печаталось). `.env` в .gitignore — ключ не закоммитится.
- Параметры OpenAI сверены с ayda: embeddings.create(model, input=texts) — порядок векторов
  сохраняется (мэтчинг по позиции); chat.completions.create(model, messages, temperature, max_tokens).
- Проверено реальными вызовами (юзер разрешил копеечные тесты): embed('тест')→dim1536,
  embed(['привет','hello'])→2×1536, complete('Скажи ОК')→непустой ответ.

### Шаг 4 (done, 2026-05-23)
- `normalize.py` (message_to_fragment + _extract_tags) + `loaders.py` (ingest/load_export_file/
  load_export_dir, CLI `--dir/--topic`). Единый funnel `ingest(messages)` для будущего realtime.
- **Формат данных подтверждён по реальному intro:** top keys + msg keys ровно как в плане,
  date = naive ISO ('2026-01-22T17:24:57') → fromisoformat ок. announcements = ВСЕГО 1 тред
  (он же null-root!) → если бы скипали null-root целиком, announcements дал бы 0. План прав.
- **null-root: ровно 1 на КАЖДЫЙ из 10 файлов, у всех есть replies** — обработаны с
  thread_root_id=None через `_iter_thread_messages`. empty_text=0 во всех файлах (но guard оставлен).
- **ВАЖНО про дубликаты:** один msg.id появляется в НЕСКОЛЬКИХ тредах (reply-цепочки
  пересекаются). intro: 360 occurrences → 305 уникальных (= total_messages файла). 55 dup-skipped
  на ПЕРВОМ прогоне — это норма, не баг. Повторный прогон: 0 inserted / 360 dup-skipped (идемпотентно).
- **Грабля: env из .env не виден в `python -m core.X` сам по себе.** Добавил load_dotenv()
  в _main loaders (как в llm.client). Учесть для enrich/delivery CLI тоже.
- Юнит-тест `tests/test_ingest_normalize.py` зелёный (mapping, empty-text→None, null user_id, tags).
- intro в БД: 305 фрагментов, sender_id null=0, 2 фрагмента с tags, author_name/thread_id заполнены.
---
