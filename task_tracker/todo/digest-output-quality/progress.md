# Progress Log — digest-output-quality

## Контекст для агента

Фокус плана: КАЧЕСТВО ВЫВОДА дайджеста (`build_digest`). Hot-topics (`/topics`)
пайплайн НЕ трогаем.

### Ключевые файлы
- `core/brain/synthesis.py` — двухпроходный синтез (Pass-1 селекция, Pass-2 проза),
  `_group_by_author` (PII-группировка), `_synthesize_fragments`, `_select_fragments`.
- `core/llm/client.py` — единая точка LLM. `COMPLETION_MODEL = gpt-4o-mini`.
- `core/store/fragments_db.py` — `get_fragments_for_digest` (min_chars=150),
  `get_topics_with_counts` (min_chars=150), `get_embedded_fragments_for_period`
  (min_chars=1, НЕ трогать — hot-topics).
- `delivery/cli.py` — `build_digest` (общий путь для scheduler + /summary + CLI),
  `humanize_author_refs` ([@N]→имя локально).
- `core/prompts/digest_synthesis.md` — промпт синтеза (целит ~2800 симв.).

### Жёсткие ограничения (PII-контракт — нарушать НЕЛЬЗЯ)
- В OpenAI уходит ТОЛЬКО `[@N]`-текст + тексты сообщений. НИКОГДА author_name,
  username, display-имена. Имена подставляются ЛОКАЛЬНО в delivery после синтеза.
- Self-критик (шаг 4) работает на `[@N]`-тексте ДО подстановки имён. Тест на
  отсутствие имён в prompt критика — обязателен.

### Решения, зафиксированные на этапе уточнений (2026-06-18)
- Модель синтеза Pass-2: дефолт `gpt-4o`, НАСТРАИВАЕТСЯ через env
  `WNDR_SYNTHESIS_MODEL` (для A/B без правки кода, напр. gpt-4.1). Pass-1 селекция
  остаётся на `gpt-4o-mini`, через env НЕ настраивается.
- Self-критик: режим ВАЛИДАТОР (находит дефекты, логирует, текст НЕ чинит).
  Модель критика — синтез-модель (та же env-константа). За флагом
  `WNDR_DIGEST_CRITIC`, по умолчанию ВЫКЛ (не платим за вызов в обычном проде;
  включаем при golden-прогонах/отладке). `result['critic_issues']` есть всегда
  (`[]` при ВЫКЛ).
- Golden set: SNAPSHOT-режим, локально на реальной БД. LLM-judge — не сейчас.
  BASELINE снимается ДО шага 1 (`--baseline`), чтобы diff'ом доказать эффект
  правок 1–4 (раннер/кейсы создаются до шага 1, финализация снапшотов — в шаге 5).
- `min_chars`: 150→80 глобально в `get_fragments_for_digest` И `get_topics_with_counts`.

### Развилка эффекта (ВНИМАНИЕ исполнителю)
min_chars 150→80 впустит короткий шум в синтез. На срезах ≤150 фрагментов Pass-1
селекции НЕТ — всё идёт в синтез напрямую. Baseline↔after diff (шаг 5) должен это
проконтролировать: если короткий шум засоряет вывод — поднять порог обратно или
усилить промпт. Не «улучшение любой ценой».

### Известное ограничение (НЕ чиним в этом плане)
Дедуп `is_duplicate` проставляется ТОЛЬКО в `core/enrich/embedder.py`
(`_check_duplicates`, cosine>0.95), который гоняется по таймеру раз в 6ч. Funnel
`ingest()` дедуп по смыслу НЕ делает (только по external_id — точные повторы).
=> Дайджест по свежему периоду может видеть почти-дубли как разные сообщения
(окно отставания до 6ч). Задокументировать как known limitation, не чинить здесь.

### Тесты — как мокаются (чтобы не сломать)
- Тесты синтеза DB/OpenAI-free: `synthesize` или `complete` мокаются через
  monkeypatch. `_synthesize_fragments` реально OpenAI не дёргают.
- `tests/test_group_by_author.py::test_synthesize_and_save_keeps_author_refs`
  мокает `synthesize` целиком — критик там не вызовется (это ок).
- Перед правкой модели: `grep -rn "COMPLETION_MODEL\|'model'" tests/`.

## Learnings
(заполняется в процессе работы)
---
