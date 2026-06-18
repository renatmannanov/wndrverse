# Шаг 3: min_chars 150→80 (recall коротких офферов/запросов)

> Зависит от: нет (но делать после шага 2 — атомарные коммиты)
> Статус: [x] done

## Задача

Снизить порог длины текста для дайджеста с 150 до 80 символов — короткие, но
содержательные офферы/запросы («Ищу таргетолога, пишите») сейчас выпадают до синтеза.

В `core/store/fragments_db.py` поменять дефолт `min_chars: int = 150` → `80` в
ДВУХ функциях:

1. `get_fragments_for_digest` (строка ~248) — основной источник дайджеста.
2. `get_topics_with_counts` (строка ~213) — help-список топиков для `/summary`
   и `/topics`. Меняем тоже, чтобы счётчики в help отражали реально дайджестимый
   объём (иначе рассинхрон: help показывает одно, дайджест берёт другое).

НЕ трогать `get_embedded_fragments_for_period` — там `min_chars=1` by design
(флуд-фильтр живёт в `core/brain/topics.py`, это hot-topics пайплайн, out-of-scope).

Проверить вызовы `get_topics_with_counts` в `bot/ingest_bot.py` (`_summary_help`,
`_topics_help`): оба зовут БЕЗ явного `min_chars`, значит унаследуют новый дефолт
80 — это правильно (help-счётчики совпадут с дайджестом). Ничего в этих вызовах
менять не нужно.

НО: в docstring `_topics_help` (`bot/ingest_bot.py:258`) есть строка
«follow get_topics_with_counts' filter (min_chars=150)». После правки она станет
ЛОЖНОЙ. ОБНОВИТЬ её: `min_chars=150` → `min_chars=80` в этом docstring. Это
единственная правка в ingest_bot.py для шага 3 (логику не трогаем, только текст
комментария, чтобы не вводить в заблуждение).

## Тесты

Эти функции бьют по реальной БД — юнит-тестов на них нет (и не добавляем,
DB-интеграция). Проверка — ручная против локальной БД (см. команды).

Что может сломаться: тесты, ассертящие конкретное число фрагментов с порогом 150.
Проверить: `grep -rn "min_chars\|150" tests/`. Если есть — обновить ожидания.

## Команды для верификации

```bash
cd c:/Users/renat/projects/wndrverse
# дефолты поменялись:
python -c "import inspect, core.store.fragments_db as m; \
print(inspect.signature(m.get_fragments_for_digest)); \
print(inspect.signature(m.get_topics_with_counts))"
# оба должны показывать min_chars=80

# против локальной БД: больше фрагментов проходит порог (docker db должен быть up)
python -c "from core.store.fragments_db import get_fragments_for_digest as g; \
print('80:', len(g('questions_to_women', None))); \
print('150:', len(g('questions_to_women', None, min_chars=150)))"
# ожидаем: count(80) >= count(150)

pytest tests/ -q
```

## Критерии готовности

- [ ] `get_fragments_for_digest` дефолт `min_chars=80`.
- [ ] `get_topics_with_counts` дефолт `min_chars=80`.
- [ ] `get_embedded_fragments_for_period` НЕ тронут (остаётся min_chars=1).
- [ ] docstring `_topics_help` (bot/ingest_bot.py:258): `min_chars=150` → `80`.
- [ ] Против локальной БД count(80) >= count(150) (больше или равно проходит).
- [ ] `pytest tests/ -q` зелёный.
