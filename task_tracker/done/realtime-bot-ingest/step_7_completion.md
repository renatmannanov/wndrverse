# Step 7: Завершение плана

> Зависит от: шаги 1-6
> Статус: [x] done

## Чеклист

- [x] Все шаги плана выполнены ([x] в PLAN.md)
- [x] Критерии готовности из PLAN.md проверены (каждый — командой или тестом)
- [x] Smoke test: бот end-to-end пишет сообщения группы в БД с правильными
      topic/channel_id/thread_id, дедуп работает (шаг 5 зелёный)
- [x] enrich/digest на боевых данных прошёл, --estimate был показан до трат (шаг 6)
- [x] Не сломано: файловый ingest импортируется (`from core.ingest.loaders import
      load_export_dir` OK), normalize.py / fragments_db.py не изменены (`git diff` пуст)
- [x] `curator/`, `agent-template/`, схема БД — не тронуты
- [x] tools_index.md — в репо нет, пропущено
- [x] CLAUDE.md дополнен: команда запуска бота (`python -m bot.ingest_bot`), секция
      про bot/, новые ENV (`BOT_TOKEN_INGEST`, `WNDR_TOPIC_MAP`)
- [ ] context.md проекта — не ведётся для wndrverse (internal/projects пусто), пропущено
- [x] Мусор убран (отладочных принтов в новом коде нет). `conftest.py` и
      `bot/__init__.py` — намеренная инфраструктура, оставлены.
- [x] `.gitignore`: реальный `topic_map.json` игнорируется, в git — только
      `.example.json`
- [x] Все тесты зелёные: `python -m pytest tests/ -q` (23 passed)
- [x] Статус в PLAN.md → done
- [x] Папка перемещена: `todo/realtime-bot-ingest/` → `done/realtime-bot-ingest/`
- [ ] Ветка влита по git-стратегии (feature → dev/staging) — ждёт подтверждения юзера

## Известная не-блокирующая проблема (вне скоупа плана)
`delivery/channels.py:12 print(text)` падает на кириллице в Windows-консоли
(cp1252). Лечится `PYTHONUTF8=1` или записью через utf-8 stdout. Это existing-код
delivery, не realtime-ingest — оставлено как есть.

## Команды финальной проверки

```bash
python -m pytest tests/ -q
git diff --stat core/ingest/normalize.py core/store/fragments_db.py   # ожидаем пусто
python -c "import bot.ingest_bot"   # бот импортируется
```

**Этот шаг обязателен.** Пока он не выполнен — план не считается завершённым.
