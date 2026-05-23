# Community Brain MVP — умный дайджест по сообществу

> Статус: pending
> Дата: 2026-05-23
> Тип: фича

## Цель

Сделать самодостаточное ядро (`core/`), которое превращает сообщения сообщества
в знание: хранит все сообщения и людей, размечает их (embeddings + pgvector),
и генерирует умный дайджест по топику/периоду. Первая фича — **дайджест**.
Ядро переиспользуемо и упаковано в Docker, чтобы потом легко передать сообществу.

## Что входит в MVP

- `core/` (4 слоя: ingest → store → enrich → brain) + `core/llm/` + `core/prompts/`
- `delivery/cli.py` — запуск дайджеста из командной строки, вывод в stdout
- `docker-compose.yml` — postgres+pgvector + app, всё через `.env`
- Источник данных MVP: разовая выгрузка `telegram-gather/data/exports/wndr/*.json`
- LLM-стек: всё на OpenAI (embeddings + синтез), как в ayda_think

## Что НЕ входит в MVP (future, не делать)

- Realtime-ingest через бота / Telethon (заложить интерфейс, не реализовывать)
- Расписания (enrich раз в час, дайджест еженедельно) — добавим с realtime
- Облако тем (clustering) — переносим код, но фича идёт второй, не в MVP smoke
- Поиск/мэтч по людям — третья фича
- Доставка в Telegram (группа/личка) — delivery-слой заложен, канал = stdout
- Кейсы «ДО и ПОСЛЕ»
- Переезд `curator/` в `agents/` — в backlog (`move_curator_to_agents.md`)

## Шаги

| # | Файл | Статус |
|---|------|--------|
| 1 | step_1_scaffold_docker.md       | [x] |
| 2 | step_2_store.md                 | [x] |
| 3 | step_3_llm_layer.md             | [ ] |
| 4 | step_4_ingest.md                | [ ] |
| 5 | step_5_enrich.md                | [ ] |
| 6 | step_6_brain_synthesis.md       | [ ] |
| 7 | step_7_delivery_cli.md          | [ ] |
| 8 | step_8_smoke.md                 | [ ] |
| 9 | step_9_completion.md            | [ ] |

## Архитектура (целевая раскладка)

```
wndrverse/
├── core/
│   ├── db.py                  подключение к БД + init_db (pgvector, индексы)
│   ├── ingest/
│   │   ├── loaders.py         JSON-loader формата telegram-gather (future: bot/telethon)
│   │   └── normalize.py       тред root+replies → Fragment-dict, фильтр мусора
│   ├── store/
│   │   └── fragments_db.py    Fragment + CRUD + поиск (перенос из ayda + поля сообщества)
│   ├── enrich/
│   │   └── embedder.py        embeddings батчами + дедуп + язык (перенос normalizer)
│   ├── brain/
│   │   ├── synthesis.py       two-pass дайджест (перенос + переписанный промпт)
│   │   └── clustering.py      UMAP+HDBSCAN (перенос, не в MVP smoke)
│   ├── llm/
│   │   └── client.py          тонкий провайдер: embeddings + completion
│   └── prompts/
│       ├── digest_selection.md
│       └── digest_synthesis.md
├── delivery/
│   ├── cli.py                 python -m delivery digest --topic offerings --period 1w
│   └── channels.py           stdout (future: telegram)
├── docker-compose.yml
├── .env.example
└── data/                     gitignored; экспорты/дампы
```

## Критерии готовности (весь план)

- [ ] `docker compose up -d` поднимает postgres+pgvector, `core/db.py init` создаёт схему без ошибок
- [ ] `python -m core.ingest.loaders --topic intro` загружает intro в БД, кол-во фрагментов > 0
- [ ] `python -m core.enrich.embedder` проставляет embeddings всем загруженным фрагментам (unembedded count → 0)
- [ ] `python -m delivery digest --topic offerings --period all` выдаёт связный дайджест в stdout
- [ ] Дайджест опирается на реальные сообщения (видны ссылки [#id, дата]), оценён глазами на smoke-шаге
- [ ] Нет хардкод-путей к `C:\Users\renat\...` в коде — только через `.env` / аргументы
- [ ] Существующий код (`curator/`, `agent-template/`, `test_stand.py`) не затронут
- [ ] В OpenAI уходит только текст/`[#id]` — имена/username НЕ передаются (PII, см. решение 8)
- [ ] `data/` в `.gitignore` до первого ingest — реальные сообщения не попадают в git

## Ключевые решения (зафиксированы, не пересматривать в ходе работы)

1. **Хранилище** — PostgreSQL + pgvector, отдельная БД `wndrverse`, локально в Docker.
2. **LLM** — OpenAI: `text-embedding-3-small` (embeddings) + `gpt-4o-mini` (синтез).
   Слой `core/llm/` тонкий, чтобы синтез позже переключить на Claude флагом.
3. **Фрагмент = одно сообщение**, с привязкой `thread_id` (видеть тред целиком).
   Фильтр мусора: сообщения короче 150 символов в синтез не идут (порог из gather).
4. **Ключ человека** — `user_id` (Telegram ID). `username`/`sender_name` — вторичны.
5. **Семантика топиков** (в промпт синтеза): harvest=итоги цикла, commits=начало цикла,
   daily=прогресс/дневник, offerings=офферы, requests=запросы, intro=знакомство,
   sales=продажи, boltalka=болталка, announcements=анонсы, together=ретро.
6. **Передача** — Docker; код в git, данные отдельным дампом (НЕ коммитить сообщения).
7. **realtime** (future) — бот для нового, Telethon разово для истории.
8. **PII / приватность** — в OpenAI уходит ТОЛЬКО текст (embeddings) и `[#id] + текст`
   (синтез). Имена/username/sender_name в промпт НЕ передаются. Имена хранятся локально
   в БД и подставляются на выводе (delivery): `[#207]` → `[Дмитрий, дата]`. Так внешнему
   провайдеру не передаётся структурированная привязка id→личность. Остаточный риск —
   имена в свободном тексте сообщений (обезличить нельзя не сломав смысл) — принят осознанно.
