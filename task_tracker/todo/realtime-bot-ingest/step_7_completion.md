# Step 7: Завершение плана

> Зависит от: шаги 1-6
> Статус: [ ] pending

## Чеклист

- [ ] Все шаги плана выполнены ([x] в PLAN.md)
- [ ] Критерии готовности из PLAN.md проверены (каждый — командой или тестом)
- [ ] Smoke test: бот end-to-end пишет сообщения группы в БД с правильными
      topic/channel_id/thread_id, дедуп работает (шаг 5 зелёный)
- [ ] enrich/digest на боевых данных прошёл, --estimate был показан до трат (шаг 6)
- [ ] Не сломано: файловый ingest всё ещё работает
      (`python -m core.ingest.loaders --dir <exports>` на старом корпусе — 0 ошибок,
       или хотя бы импорт/dry-проверка), normalize.py не изменён (`git diff` пуст)
- [ ] `curator/`, `agent-template/`, схема БД — не тронуты
- [ ] tools_index.md обновлён (если есть в репо и если бот туда логично вписать)
- [ ] CLAUDE.md дополнен: команда запуска бота (`python -m bot.ingest_bot`) и
      новые ENV (`BOT_TOKEN_INGEST`, `WNDR_TOPIC_MAP`)
- [ ] context.md проекта обновлён (если ведётся для wndrverse)
- [ ] Мусор убран (отладочные принты). NB: `conftest.py` и `bot/__init__.py` —
      намеренная инфраструктура, НЕ удалять.
- [ ] `.gitignore`: реальный `topic_map.json` игнорируется, в git — только
      `.example.json`
- [ ] Все тесты зелёные: `python -m pytest tests/ -q`
- [ ] Статус в PLAN.md → done
- [ ] Папка перемещена: `todo/realtime-bot-ingest/` → `done/realtime-bot-ingest/`
- [ ] Ветка влита по git-стратегии (feature → dev/staging), если пользователь
      подтвердил

## Команды финальной проверки

```bash
python -m pytest tests/ -q
git diff --stat core/ingest/normalize.py core/store/fragments_db.py   # ожидаем пусто
python -c "import bot.ingest_bot"   # бот импортируется
```

**Этот шаг обязателен.** Пока он не выполнен — план не считается завершённым.
