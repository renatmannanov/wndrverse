# Шаг 1: Дешёвый COUNT для ACK (без OpenAI)

> Зависит от: нет
> Статус: [x] done

## Задача

В `core/store/fragments_db.py` добавить НОВУЮ функцию
`count_embedded_fragments_for_period(topic, since, until)` — дешёвый `COUNT(*)`
с ТЕМ ЖЕ фильтром, что `get_embedded_fragments_for_period` (шаг 1 прошлого плана,
уже в коде), но без выгрузки строк/embeddings. Нужна боту для мгновенного ACK
ДО любого OpenAI-спенда.

ВАЖНО (правило #1 — один путь): фильтр должен ТОЧНО совпадать с
`get_embedded_fragments_for_period`, иначе ack соврёт. Совпадающие условия:
`topic == topic`, `embedding IS NOT NULL`, `is_duplicate IS NOT TRUE`,
`created_at >= since` (если задан), `created_at < until` (если задан, EXCLUSIVE).
`min_chars` НЕ применяем (в get_embedded_… дефолт 1 — фактически без фильтра;
флуд-фильтр живёт позже в build_topics). Так count == len(get_embedded_…) при
дефолтном min_chars.

```python
def count_embedded_fragments_for_period(
    topic: str,
    since: datetime | None = None,
    until: datetime | None = None,
) -> int:
    """Cheap COUNT of embedded, non-duplicate fragments of ONE topic in a period.

    Same filter as get_embedded_fragments_for_period (default min_chars), but
    COUNT only — no row/embedding load. Lets the bot ACK 'found N' BEFORE any
    OpenAI spend (topic names are the only spend, inside build_topics later).
    until is the UPPER bound EXCLUSIVE. Requires pgvector (same guard).
    """
```

Детали:
- Тот же guard `if not _pgvector_available(): return 0` (как у count_unembedded).
- `session.query(func.count(Fragment.id))` + те же `.filter(...)`.
- Вернуть `int(... or 0)`.

## Тесты

- Ручная проверка через python -c (см. ниже). Юнит не обязателен — тонкий COUNT,
  проверяется командой и тем, что == len(get_embedded_…).
- Что может сломаться: НИЧЕГО существующего (новая функция).

## Команды для верификации

```bash
# count == len(get_embedded_fragments_for_period) при дефолтном min_chars
PYTHONUTF8=1 python -c "
from dotenv import load_dotenv; load_dotenv()
from core.store.fragments_db import (
    count_embedded_fragments_for_period, get_embedded_fragments_for_period)
from datetime import datetime
since, until = datetime(2026,5,1), datetime(2026,6,1)
c = count_embedded_fragments_for_period('boltalka', since, until)
n = len(get_embedded_fragments_for_period('boltalka', since, until))
print('count:', c, 'len:', n, 'match:', c == n)
"
# until=None работает
PYTHONUTF8=1 python -c "
from dotenv import load_dotenv; load_dotenv()
from core.store.fragments_db import count_embedded_fragments_for_period
from datetime import datetime
print('until=None:', count_embedded_fragments_for_period('boltalka', datetime(2026,5,1), None))
"
# пустой период -> 0 без краха
PYTHONUTF8=1 python -c "
from dotenv import load_dotenv; load_dotenv()
from core.store.fragments_db import count_embedded_fragments_for_period
from datetime import datetime
print('empty:', count_embedded_fragments_for_period('boltalka', datetime(2030,1,1), datetime(2030,1,2)))
"
```

## Критерии готовности

- [x] `count_embedded_fragments_for_period` возвращает int == len(
      get_embedded_fragments_for_period) для того же (topic, since, until).
- [x] `until=None` не падает.
- [x] Пустой период → 0 без краха и без OpenAI.
- [x] Старые функции импортируются (новая функция, ничего не тронуто).
