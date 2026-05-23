# Шаг 4: Ingest — выгрузка telegram-gather → fragments

> Зависит от: шаг 2 (store). Шаг 3 (llm) НЕ нужен для ingest.
> Статус: [ ] pending

## Задача

Загрузить сообщения из JSON-экспортов telegram-gather в таблицу fragments.
Это единственный вход данных в MVP. Интерфейс должен быть таким, чтобы будущий
realtime-источник (бот) подключался без переделок — один вход `ingest(messages)`.

### Формат входа (подтверждён по реальным данным)

Файл `wndr_topic_<name>.json`:
```json
{
  "chat_name": "WNDR chat", "topic_id": 5593, "topic_name": "intro",
  "total_messages": 305, "total_threads": 56,
  "threads": [
    { "root": {msg}, "replies": [ {msg}, ... ] }
  ]
}
```
Каждый `{msg}`: `id, date(ISO), user_id, sender_name, username, text, char_count, reply_to_msg_id, reactions[{emoji,count}]`.

**КРИТИЧНО — null-root треды:** в КАЖДОМ из 10 файлов есть ровно один тред с
`"root": null` (в boltalka — с сотнями replies внутри). Если делать `thread['root']['id']`
без проверки → `TypeError: 'NoneType' object is not subscriptable` на первом запуске.
Обработка: `if thread.get('root') is None` → пропустить root, обработать `replies`
с `thread_root_id=None`. Сами replies валидны и должны попасть в БД.

### `core/ingest/normalize.py`

`message_to_fragment(msg: dict, *, topic: str, chat_name: str, thread_root_id: int) -> dict`
маппит одно сообщение в Fragment-dict:
- `external_id` = `f"wndr_{chat_name}_{msg['id']}"` (дедуп между прогонами)
- `source` = `"telegram"`
- `text` = `msg['text']`
- `created_at` = `datetime.fromisoformat(msg['date'])`
- `tags` = хэштеги из текста. ВНИМАНИЕ: функции `_extract_tags` в коде ayda НЕТ
  (только в архивных .md). Написать с нуля, тривиально:
  `[w.lstrip('#') for w in text.split() if w.startswith('#')]`
- `sender_id` = `msg['user_id']` (может быть None — не падать)
- `author_name` = `msg['sender_name']`
- `topic` = topic, `message_thread_id` = thread_root_id
- `metadata` = `{username, reactions, char_count, reply_to_msg_id}`
- Пропускать сообщения с пустым/отсутствующим `text` (служебные).

### `core/ingest/loaders.py`

`load_export_file(path: str) -> int` — читает один JSON, разворачивает
threads (root + все replies → плоский список сообщений), маппит каждое через
`message_to_fragment`, вставляет батчами через `insert_fragments_batch`.
Возвращает число вставленных. thread_root_id = id корневого сообщения треда.

`load_export_dir(dir_path: str, topics: list[str] | None = None)` — пройти по
`wndr_topic_*.json` в директории (или только указанным topics), для каждого
вызвать `load_export_file`. topic берётся из поля `topic_name` файла.

CLI: `python -m core.ingest.loaders --dir <path> [--topic intro]`.
Путь к экспортам передаётся аргументом/из env `WNDR_EXPORTS_DIR`, НЕ хардкод.

### Проверка данных (важно для будущего «с кем связаться»)

В loader логировать: сколько сообщений без `user_id` (null) — нужно знать
покрытие ключа sender_id. Просто счётчик в выводе, без действий.

## Тесты

- Юнит-тест `message_to_fragment` (это парсер — тут тест оправдан): подать
  один реальный msg-dict, проверить маппинг полей (external_id, sender_id,
  topic, created_at = datetime-объект для вставки, tags извлечены).
  (Примечание: здесь created_at — datetime, потому что insert_fragments_batch
  принимает datetime. Строкой даты становятся только на ВЫХОДЕ из query-функций,
  см. шаг 2.)
- Пустой text → функция возвращает None / пропускается.
- Тред с `root: null` → replies всё равно вставляются, без TypeError.

## Команды для верификации

```bash
# WNDR_EXPORTS_DIR указывает на telegram-gather/data/exports/wndr
python -m core.ingest.loaders --dir "$WNDR_EXPORTS_DIR" --topic intro
docker compose exec db psql -U postgres -d wndrverse -c "SELECT count(*), topic FROM fragments GROUP BY topic;"
docker compose exec db psql -U postgres -d wndrverse -c "SELECT count(*) FROM fragments WHERE sender_id IS NULL;"
```

## Критерии готовности

- [ ] `load_export_file` на intro вставляет > 0 фрагментов с `topic='intro'`
- [ ] external_id уникален → повторный запуск не дублирует (duplicates_skipped > 0)
- [ ] sender_id/author_name/message_thread_id заполнены из данных
- [ ] tags извлечены из текста (есть фрагменты с непустым tags)
- [ ] Залогировано число сообщений без user_id
- [ ] Юнит-тест `message_to_fragment` зелёный
- [ ] Нет хардкод-пути к экспортам (через --dir / env)
