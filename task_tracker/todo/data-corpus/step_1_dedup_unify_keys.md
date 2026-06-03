# Шаг 1: Единый external_id (дедуп backfill ↔ realtime)

> Зависит от: нет (первый шаг)
> Статус: [ ] pending

## Проблема

Одно сообщение, залитое двумя путями, получает РАЗНЫЕ `external_id` → дубль:

| Источник | сейчас | где |
|----------|--------|-----|
| backfill (file/telethon) | `wndr_{chat_name}_{msg_id}` → `wndr_WNDR chat_2265` | `core/ingest/normalize.py:34` |
| realtime (бот) | `tgbot_{chat_id}_{msg_id}` | `core/ingest/bot_adapter.py` |

Дедуп — построчный SELECT по `external_id` перед INSERT
(`core/store/fragments_db.py:160`), НЕ ON CONFLICT. Ключи должны совпадать ПОБАЙТНО.

## Задача

Привести оба источника к единому ключу **`tg_{chat_id}_{msg_id}`**.

### 1. Telethon-экспорт: добавить chat_id в JSON
Файл `~/projects/telegram-gather/fetch_topic.py` (ДРУГОЙ репозиторий!).
В `data = {...}` (строка ~172) уже есть `entity` (resolve_chat, строка 157) с
реальным id. Добавить:
```python
data = {
    "chat_id": int(f"-100{entity.id}"),   # <-- НОВОЕ: нормализованный -100… вид
    "chat_name": args.chat,
    ...
}
```
**Знак:** Telethon `entity.id` для супергруппы положительный (`2924475859`); в
БД/topic_map/у бота — `-100…` (`-1002924475859`). Писать `-100…`, чтобы ключ
backfill === ключ бота (PTB `message.chat_id` уже `-100…`).

### 2. loaders.py: прокинуть chat_id
`core/ingest/loaders.py:load_export_file` — читать `chat_id` из JSON (рядом с
`chat_name`, строка ~64) и передать в `message_to_fragment` (вызов на строках
**72-74**, сейчас БЕЗ chat_id):
```python
# рядом со строкой 64:
chat_id = data.get('chat_id')   # None для СТАРЫХ экспортов (нет поля) — legacy
...
# строки 72-74 — добавить chat_id=chat_id:
frag = message_to_fragment(
    msg, topic=topic, chat_name=chat_name, chat_id=chat_id,
    thread_root_id=thread_root_id,
)
```

### 3. normalize.py: ключ по chat_id (+ legacy fallback)
`core/ingest/normalize.py:message_to_fragment` — добавить параметр `chat_id`:
```python
def message_to_fragment(msg, *, topic, chat_name, chat_id=None, thread_root_id):
    ...
    if chat_id is not None:
        external_id = f"tg_{chat_id}_{msg['id']}"
    else:
        external_id = f"wndr_{chat_name}_{msg['id']}"   # legacy (старые файлы)
    ...
    'external_id': external_id,
    'channel_id': chat_id,        # <-- НОВОЕ: backfill раньше не ставил channel_id
```

### 4. bot_adapter.py: тот же формат
`core/ingest/bot_adapter.py` — убрать `bot` из ключа:
```python
frag["external_id"] = f"tg_{message.chat_id}_{message.message_id}"
```

## Тесты

⚠️ ТРИ существующих теста ассертят старый формат `external_id` и СЛОМАЮТСЯ — их
надо обновить ОДНОВРЕМЕННО с правкой кода (иначе `pytest` красный):

1. `tests/test_ingest_normalize.py:26` — сейчас
   `assert f['external_id'] == 'wndr_WNDR chat_5595'`. Это вызов БЕЗ chat_id (legacy)
   → ассерт остаётся валиден (fallback). Проверить, что тест зовёт `message_to_fragment`
   без `chat_id` — тогда не трогать. ДОБАВИТЬ новый кейс: с `chat_id=-1002924475859`
   → `external_id == 'tg_-1002924475859_<id>'`, `channel_id == -1002924475859`.
2. `tests/test_bot_adapter.py:33` — сейчас
   `assert f["external_id"] == "tgbot_-1001111111111_100"`. ОБНОВИТЬ на
   `"tg_-1001111111111_100"` (убрали `bot`).
3. `tests/test_ingest_bot.py:54` — сейчас
   `assert frags[0]["external_id"] == "tgbot_-1001111111111_100"`. ОБНОВИТЬ на
   `"tg_-1001111111111_100"`.

`tests/test_dedup_unify.py` (СОЗДАТЬ — новый):
- fragment из `message_to_fragment(chat_id=-100X, id=N)` и из
  `bot_message_to_fragment` (фейковый PTB Message, chat_id=-100X, message_id=N) →
  `external_id` СОВПАДАЕТ. Гарантия дедупа (главная цель шага).

Регресс: `test_channels`, `test_scheduler`, `test_topic_map` — не ломаются (формат
ключа их не касается).

## Правки в telegram-gather (ОТДЕЛЬНЫЙ репо) + коммиты

`fetch_topic.py` и `fetch_topics_list.py` — в `~/projects/telegram-gather`, это
ДРУГОЙ git. Здесь делаются ДВЕ правки, коммит — в ИХ репозиторий, отдельно от
wndrverse (не смешивать).

1. **`fetch_topic.py`** — добавить `chat_id` в экспорт (см. п.1 выше). Закоммитить в
   telegram-gather СРАЗУ после правки (не откладывать на step_5) — иначе step_3
   снимет экспорты без chat_id.
2. **`fetch_topics_list.py` — починить NameError (блокирует step_3).** Строка 21
   импортирует `GetForumTopicsByIDRequest`, а строка 45 вызывает
   `GetForumTopicsRequest` (не импортирован) → падает при запуске. Привести импорт и
   вызов к одному классу. Проверка: `python fetch_topics_list.py "WNDR chat"` не
   падает с NameError. Закоммитить в telegram-gather.

Коммит wndrverse (normalize/loaders/bot_adapter + тесты) — отдельным коммитом в этом
репо. Два репозитория = два независимых коммита.

## Команды для верификации

```bash
python -c "from core.ingest.normalize import message_to_fragment as m; print(m({'id':5,'text':'x','date':'2026-01-01T00:00:00'}, topic='t', chat_name='WNDR chat', chat_id=-1002924475859, thread_root_id=None)['external_id'])"
# ожидаем: tg_-1002924475859_5
python -c "from core.ingest.normalize import message_to_fragment as m; print(m({'id':5,'text':'x','date':'2026-01-01T00:00:00'}, topic='t', chat_name='WNDR chat', thread_root_id=None)['external_id'])"
# ожидаем: wndr_WNDR chat_5
python -m pytest tests/ -q
```

## Критерии готовности

- [ ] backfill и realtime для одного `(chat_id, msg_id)` дают ОДИН `external_id`
      `tg_{chat_id}_{msg_id}` (тест `test_dedup_unify` зелёный).
- [ ] `message_to_fragment` с `chat_id` ставит `channel_id`.
- [ ] Старые экспорты без `chat_id` грузятся по legacy-ключу (fallback не сломан).
- [ ] 3 существующих теста обновлены (`test_ingest_normalize` +кейс,
      `test_bot_adapter:33`, `test_ingest_bot:54` → `tg_…`).
- [ ] `fetch_topic.py` (telegram-gather) пишет `chat_id` в виде `-100…`, закоммичен.
- [ ] `fetch_topics_list.py` NameError починен, не падает на запуске, закоммичен.
- [ ] `pytest tests/ -q` зелёный.
