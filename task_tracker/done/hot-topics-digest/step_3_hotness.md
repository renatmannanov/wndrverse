# Шаг 3: Горячесть — чистые функции

> Зависит от: нет
> Статус: [ ] pending

## Задача

Новый модуль `core/brain/hotness.py` — ТОЛЬКО чистые функции, без БД и LLM.
Парсинг реакций + формула ранга. Тестируется изолированно.

```python
# веса фиксированы (правило #1: один путь, без «настраиваемости» в прототипе)
W_MSGS = 0.5
W_LIKES = 0.3
W_AUTHORS = 0.2


def likes_of(reactions: list[dict] | None) -> int:
    """Сумма count по всем реакциям сообщения. None/[] → 0.

    reactions = [{'count': int, 'emoji': str}, ...]. Кастомные эмодзи иногда
    приходят числовым id вместо символа — count всё равно валиден, суммируем всё.
    Битые элементы (нет 'count' / не int) пропускаем, не падаем.
    """


def cluster_stats(members: list[dict]) -> dict:
    """Агрегаты кластера из его фрагментов.

    members — фрагменты одного кластера (формат get_embedded_fragments_for_period).
    Возвращает {'msgs': int, 'likes': int, 'authors': int} где:
      msgs    = len(members)
      likes   = sum(likes_of(m['reactions']))
      authors = число УНИКАЛЬНЫХ sender_id (None-авторы НЕ считаются — аноним не
                раздувает охват). distinct по sender_id, не по author_name.
    """


def score(stats: dict, maxes: dict) -> float:
    """Нормированный балл горячести в наборе кластеров.

    maxes = {'msgs','likes','authors'} — максимумы по ВСЕМ кластерам набора.
    Каждый сигнал нормируется x/max (max==0 → вклад 0, без деления на ноль).
    score = W_MSGS*msgs_n + W_LIKES*likes_n + W_AUTHORS*authors_n. Диапазон [0,1].
    """
```

Замечания:
- `maxes` считает вызывающий (topics.py) по всем кластерам ДО ранжирования.
- Никакого «настраиваемого α/β» — веса в константах модуля, как договорились
  (ранг вторичен, не вылизываем).

## Тесты

`tests/test_hotness.py`:
- `likes_of(None)==0`, `likes_of([])==0`,
  `likes_of([{'count':4,'emoji':'❤'},{'count':2,'emoji':'💯'}])==6`,
  `likes_of([{'emoji':'x'}])==0` (нет count — не падает).
- `cluster_stats`: 3 сообщения, авторы [1,1,None] → msgs=3, authors=1
  (None не в счёт, дубль id=1 схлопнут).
- `score`: при maxes все равны значениям → score==1.0; при нулевых maxes → 0.0
  без ZeroDivisionError.

## Команды для верификации

```bash
python -m pytest tests/test_hotness.py -q
python -c "from core.brain.hotness import likes_of, cluster_stats, score; print('ok')"
```

## Критерии готовности

- [ ] `python -m pytest tests/test_hotness.py -q` зелёный (все кейсы выше).
- [ ] `likes_of` не падает на битых/None реакциях.
- [ ] `cluster_stats` считает уникальных авторов по sender_id, игнорит None.
- [ ] `score` нормирован, без деления на ноль.
