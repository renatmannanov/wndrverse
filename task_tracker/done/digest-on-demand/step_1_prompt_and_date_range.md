# Шаг 1: Убрать коннекты из промпта + выборка по диапазону дат

> Зависит от: —
> Статус: [x] done

## Задача

Два независимых изменения ядра (без бота): (а) промпт без блока коннектов,
(б) `get_fragments_for_digest` умеет верхнюю границу `until`.

### 1. Убрать блок «🔗 ПОЛЕЗНЫЕ СВЯЗИ» из промпта
Файл `core/prompts/digest_synthesis.md`. Удалить строки (сейчас 9-10):
```
- 🔗 ПОЛЕЗНЫЕ СВЯЗИ — кому с кем стоит познакомиться или что с чем перекликается
  (например: один что-то предлагает, другому ровно это нужно).
```
Остаётся 3 блока: 📌 ГЛАВНЫЕ ТЕМЫ, 👤 КТО ЧТО, ⭐ НЕ ПОТЕРЯТЬ. Больше в промпте
ничего не трогать (правила/лимит символов оставить).

### 2. Добавить `until` в выборку
Файл `core/store/fragments_db.py`, функция `get_fragments_for_digest` (стр. ~210).
```python
def get_fragments_for_digest(
    topic: str | None,
    since: datetime | None,
    until: datetime | None = None,      # NEW
    min_chars: int = 150,
) -> list[dict]:
    ...
    if since is not None:
        query = query.filter(Fragment.created_at >= since)
    if until is not None:                # NEW
        query = query.filter(Fragment.created_at < until)
    ...
```
⚠️ `until` — ВЕРХНЯЯ граница ЭКСКЛЮЗИВНО (`< until`). Вызывающий для диапазона
`from..till` (включительный по дню) передаёт `until = date_till + 1 день` (полночь
следующего дня). Так фрагмент с временем 23:59 в date_till попадёт в выборку.
Часовой пояс: `created_at` в БД — UTC. Даты команды трактуем как UTC-полночь
(MVP; уточнение TZ — бэклог, не здесь).

### 3. Прокинуть until через delivery (для будущего вызова из бота)
`delivery/cli.py` — `_run_digest`: пробросить опциональные `since`/`until` так,
чтобы бот мог звать синтез по точному диапазону. Минимально: добавить хелпер
(напр. `run_digest_range(topic, since, until, send_fn)`) ИЛИ параметризовать
`_run_digest`. Не ломать текущую сигнатуру, используемую scheduler'ом
(`_run_digest(topic, period, channel)`) — scheduler вызывает её как есть.
Рекомендация: вынести «ядро» (выборка→synth→humanize→вернуть текст) в функцию,
которую зовут И scheduler (фикс. период+канал), И бот (диапазон+канал-вызвавшему).

## Тесты

`tests/` — добавить юнит на границы диапазона:
- фрагмент с `created_at` ровно в начале date_from → ВКЛЮЧЁН.
- фрагмент ровно 23:59:59 в date_till → ВКЛЮЧЁН (т.к. until = till+1день).
- фрагмент 00:00 следующего за date_till дня → ИСКЛЮЧЁН.
- `since=None, until=None` → поведение как раньше (весь корпус по топику).

## Команды для верификации

```bash
pytest tests/ -q                          # все зелёные, включая новый граничный тест
# ручная проверка выборки (локально, БД поднята):
python -c "from datetime import datetime; from core.store.fragments_db import get_fragments_for_digest as g; \
  print(len(g('questions_to_women', datetime(2026,5,1), datetime(2026,6,1))))"
```

## Критерии готовности

- [ ] Промпт без блока коннектов (3 блока остались).
- [ ] `get_fragments_for_digest` принимает `until`, фильтр `< until` работает.
- [ ] Граничный юнит-тест зелёный; старые тесты не сломаны.
- [ ] delivery умеет синтез по `since/until` без слома сигнатуры scheduler'а.
