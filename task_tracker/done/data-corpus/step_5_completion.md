# Шаг 5: Завершение плана data-corpus

> Зависит от: шаги 1-4
> Статус: [ ] pending

## Чеклист

- [x] Все шаги плана выполнены ([x] в PLAN.md)
- [x] Критерии готовности из PLAN.md проверены (каждый — командой/запросом)
- [x] Дедуп: `test_dedup_unify` зелёный (35 passed); `dup_keys = 0` во всей таблице
- [x] Старые мигрированы: `channel_id IS NULL` = 0; эмбеддинги старых сохранены (emb_after==before)
- [x] Все топики WNDR в БД, questions_to_women=339 / questions_to_men=348; backfill не задвоил (dup_keys=0)
- [x] `embedding IS NULL` = 0 (весь корпус 10940 эмбеджен; дельта 4326 + 80 near-dup, $0.0066)
- [x] Не сломано: `pytest tests/ -q` = 35 passed; `core/llm/client.py` не тронут (git diff пуст)
- [x] Бэкап перед миграцией (`backup_fragments_before_migrate.sql`, 131МБ/6534 строки) существует
- [x] `.gitignore`: `data/`, `topic_map.json`, `.env`, `*.sql`-бэкап игнорятся (git check-ignore OK)
- [x] telegram-gather: `fetch_topic.py` (chat_id) + `fetch_topics_list.py` (import + peer= fix)
      закоммичены в ЕГО репо (0c03551, cb03261); чужие правки не тронуты
- [x] CLAUDE.md: формат external_id отмечен (новый ключ tg_{chat_id}_{msg_id}, legacy fallback)
- [x] Статус в PLAN.md → done
- [x] Папка перемещена: `todo/data-corpus/` → `done/data-corpus/`
- [x] **Цепочка влития (V3) согласована (польз. 2026-06-03): merge data-corpus →
      master, fast-forward.** Ветки `dev` в проекте НЕТ — главная = master. История
      линейна (14 коммитов опережения, 0 отставания), ff без конфликтов. master =
      c095854. Push на origin НЕ сделан (ждёт отдельного «ок»). prod-deploy step_1
      (строка 23) берёт `master`.
- [x] **Готов вход для `prod-deploy`:** корпус чистый/единообразный (10940, dup=0,
      unemb=0, no_chat=0), дамп этой БД поедет на VPS (prod-deploy step_1).

## Команды финальной проверки

```bash
python -m pytest tests/ -q
git diff --stat core/llm/client.py            # ожидаем пусто
git check-ignore data core/ingest/topic_map.json .env
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) AS total, count(*) - count(DISTINCT external_id) AS dup_keys, \
   count(*) FILTER (WHERE embedding IS NULL) AS unembedded, \
   count(*) FILTER (WHERE channel_id IS NULL) AS no_chat FROM fragments;"
# ожидаем: dup_keys=0, unembedded=0, no_chat=0
```

**Этот шаг обязателен.** Пока он не выполнен — план не считается завершённым.
