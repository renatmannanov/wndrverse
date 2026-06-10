# Бот-команда /topics + доставка hot-topics дайджеста в Telegram DM

> Статус: done
> Дата: 2026-06-09
> Тип: фича

## Цель

Добавить on-demand бот-команду `/topics <топик> <YYYY-MM-DD> <YYYY-MM-DD> [limit]`
в `bot/ingest_bot.py` по образцу существующей `/summary`. Команда собирает
hot-topics дайджест (готовое ядро `build_topics` → `render_topics`, фича уже в
master, commit 166b32a) и присылает результат В ЛИЧКУ вызывающему. Формат
аргументов — точные даты, как у `/summary` (единообразие команд бота).

## Видение результата

Админ из вайтлиста пишет боту `/topics boltalka 2026-05-01 2026-05-31` →
получает мгновенный ack («Топик boltalka | Период 2026-05-01..2026-05-31 |
Найдено N сообщений, собираю горячие темы…») → через несколько секунд приходит
сам дайджест ОТДЕЛЬНЫМ чистым сообщением (эмодзи + название + (N сообщений) +
кликабельная t.me-ссылка), пригодным для форварда в топик.
- `/topics` без аргументов → подсказка формата + список топиков с числами.
- Опциональный 4-й аргумент `limit` (int, дефолт 10) ограничивает число тем.
- Плохие даты / from>till / неизвестный топик / `all` / 0 сообщений → дружелюбный
  ответ БЕЗ траты OpenAI.
- Доступ — тот же вайтлист `WNDR_SUMMARY_ALLOWED` (fail-closed).

## Out-of-scope

- Scheduler (авто-дайджест тем по расписанию) — отдельный план, если попросят.
- Постинг прямо в топик группы (`telegram_group` channel) — пока только DM.
- Period-форма (1w/1m/all) в боте — решили НЕ делать, только точные даты.
- Кросс-топик (вариант Б), правка ядра `build_topics`/`render_topics`/CLI.
- Прод-деплой (git pull на VPS + restart `wndr-ingest-bot`) — отдельно, по
  команде пользователя. Шаг завершения это УПОМИНАЕТ, но НЕ выполняет.
- Фикс усечения 4096 ДО HTML-escape — унаследовано от `/summary`
  (ingest_bot.py:198). НЕ чиним здесь: ядро целит ~2800 символов, fallback на
  plain-text есть; чинить значит трогать и `/summary` (scope crawl). Решение
  зафиксировано в ревью (_review_summary.md #5).

## Архитектура (рядом с /summary, переиспользуем ядро)

```
core/store/fragments_db.py
  + count_embedded_fragments_for_period(topic, since, until)   [шаг 1]
    — дешёвый COUNT для ACK ДО OpenAI (тот же фильтр, что get_embedded_…)

delivery/cli.py
  + build_topics_digest(topic, since, until, limit) -> dict|None  [шаг 2]
    — core-функция (по образцу build_digest): store → build_topics →
      render_topics → {'text','found'}. Переиспользуется ботом И CLI.
  рефактор _run_topics: тонкая обёртка над build_topics_digest        [шаг 2]

bot/ingest_bot.py
  + validate_topics_args(args) -> (topic, since, until, limit)        [шаг 3]
  + on_topics(update, context) — хендлер по образцу on_summary        [шаг 3]
  + CommandHandler("topics", on_topics) ДО catch-all MessageHandler   [шаг 3]
```

Контракт: `build_topics_digest` возвращает `{'text': str, 'found': int}` или
`None` (0 фрагментов — без OpenAI-спенда), как `build_digest`.

## Поток данных (как /summary)

```
on_topics: whitelist → no args=help → validate_topics_args → ACK (cheap COUNT,
  no OpenAI) → 0 фрагментов=stop → build_topics_digest (asyncio.to_thread,
  тратит OpenAI на названия) → send_formatted_dm в DM → Forbidden=hint /start
```

## Шаги

| # | Файл | Статус |
|---|------|--------|
| 1 | step_1_count_query.md | [x] |
| 2 | step_2_build_topics_digest.md | [x] |
| 3 | step_3_bot_command.md | [x] |
| 4 | step_4_completion.md | [x] |

Порядок: 1 (count) и 2 (core-функция) независимы; 3 (бот) зависит от 1+2;
4 — завершение.

## Критерии готовности

- [x] `/topics boltalka 2026-05-01 2026-05-31` в DM боту → ack + дайджест в
      целевом формате (эмодзи + название + (N сообщений) + ссылка).
- [x] `/topics` без аргументов → подсказка формата + список топиков.
- [x] 4-й аргумент `limit` ограничивает число тем; без него — дефолт 10.
- [x] Неизвестный топик / `all` / плохие даты / from>till → дружелюбный ответ,
      НЕ трейсбек, БЕЗ OpenAI-спенда.
- [x] 0 фрагментов за период → ack «нет сообщений», build_topics НЕ вызван
      (нет спенда), ничего не отправлено в DM.
- [x] found>0, но все темы отсеяны флудом (build_topics → []) → в DM приходит
      пояснительный текст «За период тем не найдено…», а НЕ «нет сообщений»
      (build_topics_digest вернул result, не None).
- [x] Не-вайтлистнутый юзер → отказ, ни count, ни build_topics не вызваны.
- [x] Forbidden (бот не может писать в DM) → подсказка «/start».
- [x] Существующая `/summary` и CLI `python -m delivery topics …` работают как
      раньше (не сломали).
- [x] PII: в OpenAI уходят только тексты (ядро не тронуто, но проверить, что
      бот не подмешивает имена в текст дайджеста).
- [x] Юнит-тесты `tests/test_topics_command.py` зелёные (по образцу
      test_summary_command.py: validate, denial, no-args, valid-call, empty,
      forbidden).
- [x] Все существующие тесты зелёные: `python -m pytest tests/ -q`.
