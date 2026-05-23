# Шаг 2: Store — Fragment + CRUD + поля сообщества

> Зависит от: шаг 1
> Статус: [ ] pending

## Задача

Перенести хранилище из ayda и расширить под сообщество.

1. Скопировать `03_ayda_think/storage/fragments_db.py` → `core/store/fragments_db.py`.
   Поправить импорты: `import storage.db as _db` → `import core.db as _db`,
   `from storage.db import Base, SessionLocal` → `from core.db import Base, SessionLocal`.

2. Модель `Fragment` уже содержит `sender_id`, `channel_id`, `message_thread_id`
   (см. ayda fragments_db.py:53-55). Добавить ДВА поля под сообщество:
   - `topic = Column(String(50), nullable=True, index=True)` — имя топика
     (intro/offerings/harvest/...), для фильтра дайджеста по топику.
   - `author_name = Column(String(255), nullable=True)` — sender_name на момент
     сообщения (для человекочитаемого вывода; ключ всё равно sender_id).

3. Расширить `insert_fragments_batch` и `insert_fragment`, чтобы принимали и писали
   новые поля: `topic`, `author_name`, `sender_id`, `channel_id`, `message_thread_id`.
   (Сейчас batch берёт только source/text/created_at/tags/content_type/metadata —
   добавить проброс остальных из dict.)

4. Добавить выборку для дайджеста:
   ```python
   def get_fragments_for_digest(topic: str | None, since: datetime | None,
                                 min_chars: int = 150) -> list[dict]:
       """Фрагменты для синтеза: фильтр по topic, дате, длине; не дубликаты.
       Возвращает [{id, text, created_at, author_name, sender_id, tags}, ...]
       отсортированные по created_at."""
   ```
   Фильтры: `topic == topic` (если задан), `created_at >= since` (если задан),
   `char_length(text) >= min_chars`, `is_duplicate IS NOT TRUE`. Сортировка по дате.

   **ВАЖНО — тип `created_at`:** возвращать СТРОКОЙ через `.isoformat()`, как все
   остальные query-функции в этом файле. synthesis делает `f['created_at'][:10]`
   (срез строки) — если вернуть datetime-объект из ORM, будет `TypeError: 'datetime'
   object is not subscriptable`. Все возвращаемые dict-поля дат — строки.

5. Таблицы Cluster/FragmentCluster/Artifact оставить как есть (понадобятся
   для clustering и сохранения дайджестов).

## Тесты

- Лёгкий проверочный скрипт (не pytest-фреймворк): вставить 2 тестовых фрагмента
  через `insert_fragments_batch`, прочитать через `get_fragments_for_digest`,
  убедиться что поля topic/author_name сохранились и вернулись.

## Команды для верификации

```bash
python -m core.db init    # пересоздаст таблицы с новыми колонками
docker compose exec db psql -U postgres -d wndrverse -c "\d fragments"   # видны колонки topic, author_name, sender_id, message_thread_id
python -c "from core.store.fragments_db import get_fragments_count; print(get_fragments_count())"   # 0, без ошибок импорта
```

## Критерии готовности

- [ ] `core/store/fragments_db.py` импортируется без ошибок (импорты на core.db)
- [ ] `\d fragments` показывает колонки `topic`, `author_name`, `sender_id`, `message_thread_id`, `embedding`
- [ ] `get_fragments_for_digest` фильтрует по topic + дате + длине и сортирует по дате
- [ ] `insert_fragments_batch` пишет topic/author_name/sender_id (проверено вставкой 2 записей)
