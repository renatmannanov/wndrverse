# Шаг 1: Маппинг (chat_id, thread_id) → topic

> Зависит от: нет
> Статус: [ ] pending

## Задача

Создать конфиг маппинга телеграм-источника на топик, заложенный под всю
телеграм-структуру. Ключ — кортеж `(channel_id, message_thread_id)`:
- 4 отдельные группы → `(chat_id, None)`
- 1 супергруппа с топиками → `(chat_id, thread_id)`

### Порядок действий (важен — пункт 0 ДО создания json)

0. **СНАЧАЛА `.gitignore`** (до создания реального конфига — иначе риск закоммитить
   реальные chat_id групп). Добавить ОТДЕЛЬНОЙ строкой конкретный путь, НЕ маску
   `*.json` (она сломает `members.json` и пр.):
   ```
   core/ingest/topic_map.json
   ```
   Проверить: `git check-ignore core/ingest/topic_map.json` печатает путь.
1. **conftest.py в корне репо** (если ещё нет) — чтобы `pytest` и новые тесты
   видели пакеты `core.*` / `bot.*` без ручного `sys.path.insert` в каждом тесте.
   В репо НЕТ `conftest.py`/`pytest.ini`; существующий тест чинит путь руками —
   так делать не будем. Содержимое `conftest.py`:
   ```python
   import sys, os
   sys.path.insert(0, os.path.dirname(__file__))   # корень репо в path
   ```
   Это разовая инфраструктура для всех тестов плана (шаги 1-4, 7).
2. Дальше — сам маппинг (файлы ниже).

Файлы:
- `core/ingest/topic_map.py` — загрузчик + функция `resolve_topic(channel_id,
  thread_id) -> str | None`.
- `core/ingest/topic_map.json` — данные маппинга (в `.gitignore`, см. п.0 —
  содержит реальные chat_id групп). Положить `topic_map.example.json` в git
  как образец.

### Поведение
- `resolve_topic(channel_id, thread_id)`:
  - если есть точная пара `(channel_id, thread_id)` → вернуть topic;
  - если для `channel_id` задан дефолтный topic (запись с `thread_id = null`),
    а точной пары нет → вернуть дефолт;
  - иначе → вернуть `None` (вызывающий код решает: skip + лог).
- Формат JSON (пример):
```json
{
  "mappings": [
    {"channel_id": -1001111111111, "thread_id": null, "topic": "men"},
    {"channel_id": -1002222222222, "thread_id": null, "topic": "women"},
    {"channel_id": -1003333333333, "thread_id": null, "topic": "questions_to_men"},
    {"channel_id": -1004444444444, "thread_id": null, "topic": "questions_to_women"}
  ]
}
```
- Путь к файлу — из ENV `WNDR_TOPIC_MAP` (дефолт `core/ingest/topic_map.json`),
  по аналогии с тем как loaders читает `WNDR_EXPORTS_DIR`.
- Загрузка один раз при импорте/первом вызове, кэш в модуле (не читать файл на
  каждое сообщение).

## Тесты

`tests/test_topic_map.py` (создать, если каталога tests нет — `mkdir`):
- точная пара `(chat, thread)` → правильный topic;
- `(chat, None)` дефолт работает;
- `(chat, thread)` при наличии только дефолта `(chat, None)` → дефолт;
- неизвестный `channel_id` → `None`;
- битый/отсутствующий JSON → понятная ошибка или пустой маппинг (выбрать: пустой
  маппинг + warning в лог, чтобы бот не падал на старте).

## Команды для верификации

```bash
# .gitignore содержит реальный конфиг (ПЕРВЫМ делом, до создания файла)
git check-ignore core/ingest/topic_map.json   # печатает путь = IGNORED

# тест (conftest.py в корне обеспечивает импорт core.*)
python -m pytest tests/test_topic_map.py -q

# ручная проверка resolve (через example-конфиг)
python -c "import os; os.environ['WNDR_TOPIC_MAP']='core/ingest/topic_map.example.json'; from core.ingest.topic_map import resolve_topic; print(resolve_topic(-1001111111111, None))"
# ожидаем: men
```

## Критерии готовности

- [ ] `core/ingest/topic_map.json` в `.gitignore` (конкретный путь, не `*.json`);
      `git check-ignore` печатает путь.
- [ ] `conftest.py` в корне есть; `pytest` находит `core.*`/`bot.*` без ручного
      `sys.path` в тестах.
- [ ] `resolve_topic` возвращает topic по точной паре и по дефолту `(chat, None)`.
- [ ] Неизвестный источник → `None` (не исключение).
- [ ] `topic_map.example.json` в git, реальный `topic_map.json` НЕ в git.
- [ ] `pytest tests/test_topic_map.py` зелёный.
