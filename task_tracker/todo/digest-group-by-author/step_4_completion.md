# Step 4: Завершение плана digest-group-by-author

> Зависит от: шаги 1-3
> Статус: [ ] pending

## Чеклист

- [ ] Все шаги плана выполнены ([x] в PLAN.md)
- [ ] Критерии готовности из PLAN.md проверены (каждый — командой/тестом)
- [ ] «КТО ЧТО» сгруппирован по автору; имя каждого участника НЕ повторяется
- [ ] `[@N]` контракт: вход без имён (PII), подстановка `[@N] → [Имя]` локально
- [ ] temperature синтеза 0.4, отбор 0.0
- [ ] Smoke на проде владельцем прошёл (`/summary commits 2026-05-16 2026-05-31`)
- [ ] Не сломано: realtime-ingest пишет (dup=0); `pytest tests/ -q` зелёный;
      scheduler (build_digest) работает
- [ ] CLAUDE.md обновлён (если описание синтеза затронуто)
- [ ] context.md проекта обновлён (Текущий фокус + Последние решения)
- [ ] Мусор убран (временные файлы, scratch)
- [ ] Статус в PLAN.md → done
- [ ] Папка перемещена: todo/digest-group-by-author/ → done/digest-group-by-author/
- [ ] Ветка влита по git-стратегии (feature → master, с подтверждением)

## Команды финальной проверки

```bash
pytest tests/ -q
# на VPS:
ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95
cd ~/wndrverse
sudo systemctl is-active wndr-ingest-bot
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*), count(*)-count(DISTINCT external_id) dup FROM fragments;"
```

**Этот шаг обязателен.** Пока он не выполнен — план не считается завершённым.
