# Step 4: Завершение плана digest-group-by-author

> Зависит от: шаги 1-3
> Статус: [x] done (2026-06-05)

## Чеклист

- [x] Все шаги плана выполнены ([x] в PLAN.md)
- [x] Критерии готовности из PLAN.md проверены (91 тест зелёный; реальный прогон)
- [x] «КТО ЧТО» сгруппирован по автору; имя каждого участника НЕ повторяется
- [x] `[@N]` контракт: вход без имён (PII), подстановка `[@N] → Имя @ник` локально
- [x] temperature синтеза 0.4, отбор 0.0
- [x] Smoke на проде владельцем прошёл (`/summary commits 2026-05-16 2026-05-31`)
- [x] Не сломано: realtime-ingest пишет (dup=0); `pytest tests/ -q` зелёный (91);
      scheduler (build_digest) работает
- [x] CLAUDE.md обновлён (раздел «Digest author grouping + [@N] contract»)
- [x] context.md проекта обновлён (Текущий фокус + Последние решения)
- [x] Мусор убран (временные _dbg.txt / _digest_out.txt удалены)
- [x] Статус в PLAN.md → done
- [x] Папка перемещена: todo/digest-group-by-author/ → done/digest-group-by-author/
- [x] Ветка влита по git-стратегии (feature → master, с подтверждением; ветка удалена)

## Итог

Сверх плана (по запросам владельца в ходе прод-smoke) добавлено: чистка тем от
ссылок + лимит 15 в КТО ЧТО, шапка топик+даты, блок ЗАПРОСЫ И ПРЕДЛОЖЕНИЯ,
кликабельный @username. Коммиты: f8e8f99, a624f5f (merge), 09dc82a, 2f9c5f8, 5419827.

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
