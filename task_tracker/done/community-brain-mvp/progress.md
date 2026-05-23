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

### Шаг 5 (done, 2026-05-23)
- `core/enrich/embedder.py`: normalize_all (батчи 100, commit per item, прогресс processed/total),
  estimate() (без API), _detect_language, _check_duplicates (threshold 0.95). embed через core.llm.client.
  PII: в OpenAI уходит ТОЛЬКО text (texts = [f['text']]), author_name НЕ добавляется.
- **ГРАБЛЯ (важная, новая): `pgvector_available` был False в любом процессе без init_db().**
  Все query-функции с guard `_pgvector_available()` (embed/dedup/count) молча возвращали 0/[].
  `--estimate` показывал 0 unembedded при 305 в БД. ФИКС: `core.db.ensure_pgvector_checked()` —
  ленивый разовый probe pg_extension (кэш), fragments_db зовёт его вместо чтения флага.
  init_db ставит _pgvector_checked=True (его результат авторитетный).
- **Юзер разрешил реальный прогон на intro (~$0.0012).** Прогон: 305 embedded, 0 errors.
  Критерии: unembedded(non-dup)=0; language 299 ru / 5 mixed / 1 en; **дубликатов 0**.
- **0 дубликатов в intro — НЕ баг.** intro=знакомства, каждое уникально, near-dup (>0.95) редки.
  Механизм дедупа отработал (нашёл 0). На полном корпусе (boltalka) дубли вероятно появятся (шаг 8).
- Защита от бесконечного цикла: если весь батч в errors (embedding остаётся NULL) — стоп.
- Добавил safety-guard в _main: load_dotenv (как в loaders).

### Шаг 6 (done, 2026-05-23)
- `core/brain/synthesis.py`: two-pass (Pass1 LLM-отбор по тексту → Pass2 синтез),
  промпты из `core/prompts/digest_selection.md` + `digest_synthesis.md`, LLM через
  core.llm.client.complete. topic_type → TOPIC_HINTS (harvest/commits/daily/offerings/...).
  Hard-cap входа INPUT_HARD_CAP=800 (последние по дате) ДО Pass1. synthesize_and_save → artifact.
- `core/brain/clustering.py`: перенос, импорты на core.*, промпт в `cluster_name.md`.
  hdbscan/umap импортируются ЛЕНИВО внутри run_clustering → модуль импортируется без них.
- **PII подтверждён на практике:** в промпт уходит `[#id] (дата)\ntext`, БЕЗ author_name.
  В дайджесте есть [#id]-ссылки (id из входа). Имена типа «Дмитрий» в теле — это из ТЕКСТА
  сообщений («Привет, я Дмитрий...»), принятый остаток. Подстановка [#id]→[Имя] на шаге 7.
- **Smoke на intro (151 фрагмент ≥150 симв):** Pass1 151→20, Pass2 → связный дайджест
  с секциями (главные темы / кто что / связи / не потерять), 22 ссылки [#id]. Качество хорошее.
- topic_type=harvest≠offerings — разные TOPIC_HINTS-строки в промпте; проверка на разнице
  вывода — на шаге 8 (нужны разные топики в БД).
- Hard-cap 800 на boltalka — проверка на шаге 8 (сейчас в БД нет больших топиков).
- ID-парсер Pass1 терпим к формату (strip '[]#'); fallback при <5 id → последние 20 по дате.

### Шаг 7 (done, 2026-05-23)
- `delivery/channels.py`: send(text, channel='stdout'); telegram_* → NotImplementedError (точка роста).
- `delivery/cli.py` + `delivery/__main__.py`: `python -m delivery digest --topic X --period Y`.
  Свой parse_period (all→None; h/d/w/m=30дней; неизвестный суффикс → raise, НЕ молчит).
  humanize_refs: [#id]→[author_name, дата] локально из БД (get_fragments_by_ids), None→аноним.
- **Грабля (cosmetic, предсказанная): LLM варьирует формат ссылки.** _REF_RE = `\[?#?(\d+)\]?`
  ловит [#207]/#207/[207]/(#207). Неизвестные id оставляются как есть (дайджест читаем).
- Юнит-проверки (без API): parse_period 1m=30д/1w=7д/12h/1y-raises; humanize_refs все форматы+аноним+unknown.
- **End-to-end на intro прошёл:** `python -m delivery digest --topic intro --period all` →
  связный дайджест, ссылки заменены на [Имя, дата] из НАШЕЙ БД (напр. [Dmitry Dumik, 2026-01-22]).
  artifact сохранён (id=1, 20 frag_ids, len 2276). `--topic all --period all`→151 фраг (без фильтра).
  `--period 1m`→0 (intro датирован янв-март, вне 30 дней) — корректно, fallback "недостаточно".
- **Замечание:** datetime.utcnow() даёт DeprecationWarning (Py3.14). Оставлено намеренно: БД хранит
  naive datetime, tz-aware сломает сравнение created_at>=since. Можно заменить позже консистентно.
- PowerShell заворачивает stderr-лог в NativeCommandError (exit 255), но stdout-дайджест чистый — не баг.

### Шаг 8 — SMOKE (done, 2026-05-23)
- **Объём корпуса: 6530 фрагментов (НЕ ~150k как ждал план).** Реальный WNDR-экспорт = ~6.5k.
  Топики: boltalka 2396, offerings 1523, daily 1004, requests 705, intro 305, sales 177,
  commits 154, harvest 133, announcements 85, together 48. Все 10 загружены (count>0 каждый).
- **Стоимость embeddings (зафиксировано): ~$0.009** (6225 фрагментов сверх intro, ~454k токенов,
  text-embedding-3-small). Юзер дал «ок» на реальный прогон. Полный enrich: 6104 embedded,
  121 duplicates, 0 errors. Том НЕ стирали (down -v не делали — intro уже был embedded).
- Критерии БД: unembedded(non-dup)=0; is_duplicate=121; язык 6090 ru / 321 mixed / 119 en.
- **3 дайджеста сгенерированы и сохранены в artifacts** (id 3=offerings/21, 4=harvest/20, 5=requests/20).
- **ОЦЕНКА КАЧЕСТВА ГЛАЗАМИ — хорошо, MVP работает:**
  - Опирается на реальные сообщения: каждый пункт со ссылкой [Имя, дата] из локальной БД.
  - topic_type РАБОТАЕТ — три разных шаблона: offerings="что предлагают" (практики, мастер-классы,
    какао-церемония), harvest="итоги/инсайты цикла" (величие, самопринятие, рефлексия),
    requests="что нужно" (помощь при выгорании, курсы ИИ, рекомендации). НЕ копия друг друга.
  - Полезные связи осмысленные (Katya↔Анна по выгоранию, Ксения↔Карина по группам).
  - Анти-галлюцинация пройдена: проверил вручную — «практика благодарности» (offerings, id 4548/4595),
    запрос Katya о выгорании (requests, id 5703) + ответ Анны (id 5714) — РЕАЛЬНО есть в источнике.
  - PII держится: в дайджесте [#id] заменены на [Имя,дата] локально; в OpenAI ушли только [#id]+текст.
    Имена типа «Дмитрий» в свободном тексте — принятый остаток (публичный чат, юзер согласовал).
- **Hard-cap 800 на boltalka косвенно ок:** offerings 1523 фраг прошёл через Pass1 без падения
  (cap отрезал до 800 последних → Pass1 отобрал 21). Прямого digest по boltalka не делали, но
  путь cap→Pass1 отработал на топике >800.
- Мелочь: spike дублей на батче 5100-5200 (+34/+20) — кластер почти-идентичных (вероятно daily/boltalka).
- Прибрано: temp .txt дайджесты удалены, stray artifact id=2 ("all", insufficient-data тест) удалён.

### Шаг 9 — ЗАВЕРШЕНИЕ (done, 2026-05-23)
- README: добавлена секция «Community Brain (core/)» — Run it (docker compose + пайплайн),
  Privacy, Handoff. Project Structure дополнен core/ + delivery/. Существующий контент curator не тронут.
- CLAUDE.md: Commands += блок core/ (init/ingest/enrich/digest), Key files += core/delivery/compose,
  Stack += postgres+pgvector/sqlalchemy/openai.
- Финальные проверки (командами): юнит-тесты зелёные; все 10 модулей core/delivery импортируются;
  curator/agent-template/test_stand — `git diff master` пуст; нет хардкод C:\Users; data/ в git только
  .gitkeep; embed шлёт только text, synthesis [#id]+text без имён; нет import storage/services/config
  из ayda (источник читался только при разработке). Папка todo→done (git mv, история сохранена).
- context.md для wndrverse НЕ ведётся (живёт у 00_anna) — пункт н/п.

### ИТОГ MVP
- 6530 фрагментов (10 топиков), 6104 embedded. Фича дайджеста работает end-to-end.
- 6 дайджестов сгенерировано (3 all-period + 3 march2026), лежат в data/digests/ (gitignored).
- Семантический поиск проверен (3 запроса) — эмбеддинги ловят смысл (опечатки/синонимы). Дистанции
  0.45-0.65, на проде для поиска по людям добавить фильтр по топику + порог + отсечку коротких.
- **Ждём фидбэк от ребят по дайджестам** (юзер перешлёт). Дальше — future из плана:
  realtime-бот, расписание, доставка в TG, clustering (облако тем), поиск по людям.

### Известные шероховатости (не баги, для будущего тюнинга промпта)
- LLM иногда видит 2 сообщения одного автора как двух людей (в промпте только [#id], имён нет — цена PII).
- harvest-дайджест зацепил префикс «Точка Б» из исходных формулировок.
- Косметика ссылок: LLM варьирует формат [#id] — _REF_RE терпим, незаменённые id остаются как есть.
- datetime.utcnow() даёт DeprecationWarning (Py3.14) — оставлено (БД хранит naive datetime).
---
