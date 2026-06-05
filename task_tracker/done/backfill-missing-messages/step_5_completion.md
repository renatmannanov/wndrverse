# Step 5: Завершение плана

> Статус: done (2026-06-05)

## Чеклист

- [x] Все шаги плана выполнены ([x] в PLAN.md) — step_4 помечен «не нужен»
- [x] Критерии готовности из PLAN.md проверены командами:
  - [x] `dup=0` в fragments (11100 total, 0 dup)
  - [x] `last_msg` сдвинулся: daily/harvest/announcements/offerings → 5 июня,
        boltalka/quotes → 4 июня (requests/intro/commits — новых не было, 0 inserted)
  - [x] total 11024 → 11100 (+76)
- [x] embedder отработал — `need_embedding=0`
- [x] Бэкап `~/wndrverse/fragments_pre_backfill.sql` удалён (PII)
- [x] Каталог `wndr_backfill` на VPS удалён (PII). Локальный в telegram-gather/data/
      оставлен (gitignored, рабочая машина)
- [x] Backlog-промпт `backfill-missing-messages-PROMPT.md` → удалён (выполнен)
- [x] context.md проекта обновлён
- [x] Статус в PLAN.md → done
- [x] Папка перемещена: todo/ → done/

## Замечание на будущее (НЕ в этой задаче)

Корень проблемы — `topic_map.json` содержит только 2 топика, бот молча пропускает
остальные 11. Пока маппинг не расширен, эти топики снова застынут после 5 июня.
Отдельная задача: добавить 11 топиков в topic_map.json + restart wndr-ingest-bot.
