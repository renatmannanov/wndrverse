# Hot Topics Digest (прототип, вариант А)

> Статус: done
> Дата: 2026-06-09
> Тип: фича (эксперимент)

## Цель

Второй, экспериментальный режим дайджеста — «горячие темы». Берём сообщения
ОДНОГО топика за период, кластеризуем по смыслу (готовые embeddings + HDBSCAN),
ранжируем темы по горячести и рендерим в формат заказчика: эмодзи + название
темы + `(N сообщений)` + ссылка на Telegram. Текущий people-grouping digest
(`КТО ЧТО`/`ЗАПРОСЫ`) НЕ трогаем — новый режим живёт параллельно.

Главный приоритет — **качество кластеров**: в темах не должно быть флуда,
коротких фраз и неподходящих сообщений.

## Видение результата

```
$ python -m delivery topics --topic boltalka --period 1m

📅 Болталка · 2026-05-09 — 2026-06-09

📈 <название темы> (22 сообщения)
   https://t.me/c/2924475859/9307
🔮 <название темы> (14 сообщений)
   https://t.me/c/2924475859/9308
…
```

Темы отсортированы по горячести (msgs + likes + authors), флуд отфильтрован,
ссылки настоящие и ведут в ПЕРВОЕ сообщение треда. Названия тем — по-русски.

## Out-of-scope

- Варианты Б (кросс-топик) и С (кросс-связи) — только А, на одном топике.
- НЕ трогаем `synthesis.py`, `run_clustering`, `get_all_embedded_fragments`,
  команду `digest`, `humanize_*`.
- НЕ вылизываем формулу ранга — простой нормированный score, веса фиксированы в
  константах модуля.
- НЕ делаем Telegram-доставку/бот-команду/scheduler — только CLI → stdout.
- НЕ доингестим данные — всё уже в БД (channel_id 100%, embeddings 100%,
  reactions 79%).
- Якорь ссылки = ВСЕГДА первое по времени сообщение кластера (не самое
  залайканное). Лайки нужны только для ранжирования.

## Архитектура (рядом с существующим, переиспользуем ядро)

```
core/store/fragments_db.py
  + get_embedded_fragments_for_period(topic, since, until, min_chars)   [шаг 1]

core/brain/clustering.py
  рефактор: вынести чистое ядро cluster_embeddings(); run_clustering → обёртка  [шаг 2]

core/brain/hotness.py        НОВЫЙ — чистые функции (лайки, score)        [шаг 3]
core/brain/topics.py         НОВЫЙ — оркестратор фичи                     [шаг 5]
core/prompts/topic_label.md  НОВЫЙ — промпт «название темы»               [шаг 5]

delivery/topics_render.py    НОВЫЙ — TopicCluster[] → текст + t.me-ссылки  [шаг 4]
delivery/cli.py
  + подкоманда `topics`                                                   [шаг 6]
```

Контракт brain↔delivery — структура `TopicCluster` (dict): тема не знает про
рендер, рендер не знает про кластеризацию.

## Поток данных

```
store.get_embedded_fragments_for_period
  → brain.topics.build_topics  (фильтр флуда → cluster_embeddings →
                                hotness.score → ранг → LLM-название)
  → delivery.topics_render     (→ текст со ссылками)
  → delivery.cli `topics`      (склейка + заголовок, переиспользует parse_period)
```

## Шаги

| # | Файл | Статус |
|---|------|--------|
| 1 | step_1_store_query.md | [x] |
| 2 | step_2_cluster_core.md | [x] |
| 3 | step_3_hotness.md | [x] |
| 4 | step_4_render.md | [x] |
| 5 | step_5_topics_orchestrator.md | [x] |
| 6 | step_6_cli_command.md | [x] |
| 7 | step_7_calibrate.md | [x] |
| 8 | step_8_completion.md | [x] |

Порядок: 1–4 независимы по сути, но 5 (оркестратор) зависит от 1+2+3, 6 от 4+5,
7 (калибровка порогов) после рабочего end-to-end, 8 — завершение.

## Критерии готовности

- [x] `python -m delivery topics --topic boltalka --period 1m` печатает темы в
      целевом формате (эмодзи + название + `(N сообщений)` + ссылка).
- [x] Ссылки кликабельны и ведут в реальное сообщение (`t.me/c/2924475859/<msg>`).
- [x] Темы отсортированы по убыванию горячести.
- [x] В темах нет коротких фраз/флуда — визуальная проверка на boltalka (шаг 7).
- [x] Существующий `python -m delivery digest --topic offerings --period 1w`
      работает как раньше (не сломали).
- [x] Существующий `run_clustering` импортируется и не сломан (шаг 2).
- [x] Юнит-тесты `hotness.py` (парсинг реакций, score) — зелёные.
- [x] PII: в OpenAI уходят только тексты сообщений, без имён/@handle.
