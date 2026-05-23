# Шаг 6: Brain — синтез дайджеста (+ перенос clustering)

> Зависит от: шаг 3 (llm), шаг 4 (данные в БД). Шаг 5 (embeddings) — для clustering
>   и общей целостности пайплайна; для самого синтеза Pass 1 НЕ требует embeddings
>   (Pass 1 = LLM-отбор по тексту, не векторный поиск — см. ниже).
> Статус: [ ] pending

## Задача

Главная фича MVP — умный дайджест. Перенос
`03_ayda_think/services/synthesis_service.py` с переписанным под СООБЩЕСТВО
промптом и вынесением промптов в `.md`.

### Промпты в файлы (улучшение vs ayda, где они были строками в .py)

- `core/prompts/digest_selection.md` — отбор релевантных фрагментов (Pass 1).
- `core/prompts/digest_synthesis.md` — синтез дайджеста (Pass 2).

Промпт синтеза переписать с «скрытые связи в заметках ОДНОГО человека» на
**дайджест по сообществу**. Он должен:
- Понимать тип топика (передаётся в промпт): harvest=итоги цикла, commits=начало
  цикла/обязательства, daily=прогресс, offerings=что люди предлагают,
  requests=что людям нужно, intro=кто пришёл, sales=продажи.
- Выдавать: главные темы периода; кто что предложил/попросил/завершил;
  потенциально полезные связи; что не стоит потерять (важные офферы/запросы).
- Цитировать с ссылками `[#id]` — ТОЛЬКО id, БЕЗ имён (см. PII ниже).
- Писать на русском, по делу, без воды.

**PII — обезличивание входа в LLM (решение из PLAN п.8):**
В промпт (и Pass 1, и Pass 2) фрагменты подаются как `[#id] (дата)\n текст` —
БЕЗ author_name/username. Имя в OpenAI не уходит. Дайджест возвращается со
ссылками `[#id]`. Подстановка имён `[#id] → [Имя, дата]` делается на ВЫВОДЕ
(delivery, шаг 7) локально из БД, не в синтезе.

**Pass 1 = LLM-отбор (НЕ векторный поиск).** В ayda Pass 1 — это LLM-вызов: модели
даётся список `[id] дата — текст[:100]`, она возвращает id релевантных. Embeddings
тут НЕ используются. Перенести этот механизм как есть (с обезличиванием — без имён).

**Лимит против context_length_exceeded.** boltalka/большие топики могут вернуть
тысячи фрагментов. Защита в два уровня:
1. Pass 1 (selection) отбирает ≤ SELECTION_TARGET (20) — это уже есть в ayda.
2. ДО Pass 1, если фрагментов очень много (> 800), сначала ограничить вход:
   взять последние N по дате (свежее важнее для дайджеста) ИЛИ резать текст каждого
   до ~500 символов в списке для отбора. Зафиксировать: hard-cap входа в Pass 1 =
   800 фрагментов (последние по дате). Иначе даже список для отбора превысит контекст.

### `core/brain/synthesis.py`

- Перенести `synthesize(topic, fragments)` two-pass логику.
- Промпты грузить из `core/prompts/*.md` (не хардкод-строки).
- LLM-вызовы через `core.llm.client.complete` (не transcription_service).
- Параметр `topic_type` пробрасывать в промпт синтеза (семантика топика).
- Вход `fragments` — из `get_fragments_for_digest` (шаг 2). created_at — строка.
- Сохранять результат через `save_artifact` (topic, content, fragment_ids).
- Hard-cap входа в Pass 1 = 800 последних по дате (защита от context overflow).

### `core/brain/clustering.py` (перенос, НЕ в MVP smoke)

- Скопировать `clustering_service.py`, поправить импорты на `core.store` / `core.llm`.
- Промпт именования кластеров — тоже в `core/prompts/cluster_name.md`.
- Не запускать на smoke-шаге (это вторая фича). Цель шага — чтобы код был
  перенесён и импортировался, фичу «облако тем» включим отдельно.

## Тесты

- Smoke внутри шага: вызвать `synthesize('offerings', fragments)` на ~30
  реальных фрагментах из offerings, убедиться что возвращается непустой
  осмысленный текст со ссылками. (Глубокая оценка качества — шаг 8.)

## Команды для верификации

```bash
python -c "
from core.store.fragments_db import get_fragments_for_digest
from core.brain.synthesis import synthesize
frags = get_fragments_for_digest(topic='offerings', since=None)[:40]
r = synthesize('offerings', frags)
print(r['content'][:500]); print('used:', len(r['fragment_ids']))
"
python -c "import core.brain.clustering"   # импортируется без ошибок
```

## Критерии готовности

- [ ] `core/prompts/digest_selection.md` и `digest_synthesis.md` существуют, промпт под сообщество (не «один человек»)
- [ ] `synthesize` грузит промпты из файлов, вызывает `core.llm.client.complete`
- [ ] На реальных offerings возвращает непустой текст со ссылками `[#id]`
- [ ] В промпт НЕ передаются имена/username (только [#id] + текст) — проверено чтением промпта/кода
- [ ] Pass 1 — LLM-отбор по тексту (не векторный поиск)
- [ ] Hard-cap входа 800 фрагментов работает: synthesize на boltalka не падает context_length_exceeded
- [ ] `topic_type` влияет на формулировку (harvest≠offerings в выводе)
- [ ] `core.brain.clustering` импортируется (перенесён, импорты на core.*)
