# Backlog: добор together/sales — найти актуальный thread_id

> Создан 2026-06-05 из плана backfill-missing-messages.

## Проблема

При доборе 11 застывших топиков WNDR (план backfill-missing-messages) топики
**together** и **sales** не выгрузились: `iter_messages(reply_to=<id>)` через
Telethon вернул 0 сообщений ДАЖЕ без лимита — не отдаются даже старые сообщения,
которые лежат в БД с апреля.

Старые topic-id (из экспорта 2026-04-13):
- together: 11002 (last_msg в БД 2026-04-13, 48 сообщений)
- sales: 8718 (last_msg в БД 2026-04-11, 177 сообщений)

Вероятная причина: thread_id топиков изменился, либо топики архивированы/закрыты.
Оба — самые тихие топики, застыли ещё в апреле (НЕ с 3 июня), поэтому отложены.

## Что нужно

1. Получить актуальный список форум-топиков WNDR chat (chat_id -1002924475859) с их
   реальными thread_id. В установленной версии Telethon `GetForumTopicsRequest`
   импортируется иначе, чем `telethon.tl.functions.channels.GetForumTopicsRequest`
   (ImportError) — найти правильный путь импорта / способ листинга топиков.
2. Сопоставить together/sales с актуальными thread_id.
3. Выгрузить их (`fetch_topic.py … --name together/sales -o data/exports/wndr_backfill2`),
   залить `python -m core.ingest.loaders` на VPS (дедуп страхует), проверить dup=0.

## Окружение

- telegram-gather: `C:\Users\renat\projects\telegram-gather\` (Telethon userbot, локально).
- БД: VPS `rm_agent@62.238.31.95`, `~/wndrverse`, postgres :5434 в docker.
- Детали дедупа/external_id — см. CLAUDE.md проекта wndrverse + завершённый план
  done/backfill-missing-messages/.
