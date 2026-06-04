# Step 4: Завершение плана digest-on-demand

> Зависит от: шаги 1-3
> Статус: pending

## Чеклист

- [ ] Все шаги плана выполнены ([x] в PLAN.md)
- [ ] Критерии готовности из PLAN.md проверены (каждый — командой/тестом)
- [ ] Промпт без коннектов: саммари выходит с 3 блоками
- [ ] `get_fragments_for_digest(until=...)` + граничный юнит-тест зелёный
- [ ] `/summary` на проде: вайт-лист, ответ в ЛС, PII локальная, негатив-кейсы ок
- [ ] Smoke test: реальная команда отработала end-to-end на VPS
- [ ] Не сломано: realtime-ingest пишет, dup=0; `pytest tests/ -q` зелёный
- [ ] CLAUDE.md обновлён: команда `/summary`, env `WNDR_SUMMARY_ALLOWED`
- [ ] context.md проекта обновлён (если ведётся)
- [ ] Мусор убран (временные файлы)
- [ ] Статус в PLAN.md → done
- [ ] Папка перемещена: todo/digest-on-demand/ → done/digest-on-demand/
- [ ] Ветка влита по git-стратегии (с подтверждением пользователя)

## Команды финальной проверки

```bash
pytest tests/ -q
# на VPS:
ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95
cd ~/wndrverse
sudo systemctl is-active wndr-ingest-bot
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) total, count(*)-count(DISTINCT external_id) dup FROM fragments;"
# ожидаем: dup=0, total растёт (ingest жив)
```

**Этот шаг обязателен.** Пока он не выполнен — план не считается завершённым.
