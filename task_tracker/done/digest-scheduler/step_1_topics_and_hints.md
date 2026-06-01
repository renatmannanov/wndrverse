# Шаг 1: Топики WNDR в маппинг + topic-хинты

> Зависит от: нет
> Статус: [ ] pending

## Задача

Подключить два форум-топика WNDR chat в существующий `topic_map.json` и добавить
семантические хинты для них в `core/brain/synthesis.py:TOPIC_HINTS`, чтобы синтез
понимал контекст «вопросы к миру», а не работал вслепую.

### 0. СНАЧАЛА проверить .gitignore (до любого git add)
`topic_map.json` содержит реальный chat_id WNDR-группы. Перед ЛЮБЫМ `git add` в
этом шаге выполнить:
```bash
git check-ignore core/ingest/topic_map.json   # должен напечатать путь = IGNORED
```
Если путь НЕ печатается — НЕ делать `git add`, сначала починить `.gitignore`.
Файл уже должен быть в `.gitignore` (от прошлого плана), но проверка обязательна
ДО коммита, не после.

### 1. topic_map.json (gitignored — содержит реальные chat_id)
Добавить в `core/ingest/topic_map.json` две записи к существующей `raymann_agents`.
WNDR chat — супергруппа с топиками, поэтому ключ = `(chat_id, thread_id)`:
```json
{
  "mappings": [
    {"channel_id": -1003905781841, "thread_id": null,  "topic": "raymann_agents"},
    {"channel_id": -1002924475859, "thread_id": 16139, "topic": "questions_to_women"},
    {"channel_id": -1002924475859, "thread_id": 16138, "topic": "questions_to_men"}
  ]
}
```
`example`-файл (`topic_map.example.json`, в git) обновить так, чтобы он РЕАЛЬНО
показывал thread-режим. Сейчас в нём `questions_to_men/women` стоят с
`thread_id: null` (т.е. как отдельные чаты — вводит в заблуждение). Заменить эти
две строки на форум-вариант: один `channel_id` + разные ненулевые `thread_id`
(плейсхолдеры). Пример итогового example (значения плейсхолдерные, НЕ реальные):
```json
{
  "mappings": [
    {"channel_id": -1001111111111, "thread_id": null,  "topic": "men"},
    {"channel_id": -1002222222222, "thread_id": null,  "topic": "women"},
    {"channel_id": -1009999999999, "thread_id": 100,   "topic": "questions_to_men"},
    {"channel_id": -1009999999999, "thread_id": 200,   "topic": "questions_to_women"}
  ]
}
```
Так образец показывает оба режима: отдельные чаты (null) И форум-топики одного
чата (ненулевой thread_id). Реальные chat_id/thread_id из WNDR в example НЕ писать.

### 2. TOPIC_HINTS в synthesis.py
Добавить два ключа в словарь `TOPIC_HINTS` (строки 28-39). Формулировка под смысл
«люди задают вопросы противоположной части сообщества»:
```python
'questions_to_women': "Топик «вопросы к женскому миру»: мужчины задают вопросы "
                      "женщинам сообщества. Выдели главные темы вопросов и суть "
                      "ответов/обсуждений.",
'questions_to_men':   "Топик «вопросы к мужскому миру»: женщины задают вопросы "
                      "мужчинам сообщества. Выдели главные темы вопросов и суть "
                      "ответов/обсуждений.",
```
Не трогать остальные ключи. `synthesize()` сам подхватит хинт по `topic_type`
(передаётся из `cli._run_digest` как `topic_arg`, если он есть в TOPIC_HINTS —
см. `cli.py:82`).

### НЕ делать здесь
- Не трогать two-pass логику, нормализацию, схему БД.
- Не собирать сообщения (это делает бот-ингестор, отдельно).

## Тесты

`tests/test_topic_map.py` — дополнить:
- `(−1002924475859, 16139)` → `questions_to_women`;
- `(−1002924475859, 16138)` → `questions_to_men`;
- `(−1002924475859, 99999)` (неизвестный thread в этом чате, дефолта нет) → `None`.

(Тест для synthesis.TOPIC_HINTS не нужен — это данные-словарь; покрытие даёт smoke.)

## Команды для верификации

```bash
# resolve по реальному конфигу (значения thread_id известны)
python -c "from core.ingest.topic_map import resolve_topic as r; print(r(-1002924475859, 16139), r(-1002924475859, 16138), r(-1002924475859, 99999))"
# ожидаем: questions_to_women questions_to_men None

# хинты на месте
python -c "from core.brain.synthesis import TOPIC_HINTS; print('questions_to_women' in TOPIC_HINTS, 'questions_to_men' in TOPIC_HINTS)"
# ожидаем: True True

python -m pytest tests/test_topic_map.py -q
```

## Критерии готовности

- [ ] `git check-ignore core/ingest/topic_map.json` печатает путь — проверено ДО
      любого `git add` (см. п.0).
- [ ] `resolve_topic(-1002924475859, 16139)` → `questions_to_women`;
      `(…, 16138)` → `questions_to_men`; неизвестный thread → `None`.
- [ ] `TOPIC_HINTS` содержит оба новых ключа.
- [ ] `topic_map.example.json` показывает thread-режим (строка с ненулевым
      thread_id); реальный `topic_map.json` НЕ в git.
- [ ] `pytest tests/test_topic_map.py` зелёный.
