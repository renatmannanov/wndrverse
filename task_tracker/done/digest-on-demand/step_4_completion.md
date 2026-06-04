# Step 4: Завершение плана digest-on-demand

> Зависит от: шаги 1-3
> Статус: done

## Чеклист

- [x] Все шаги плана выполнены ([x] в PLAN.md)
- [x] Критерии готовности из PLAN.md проверены (каждый — командой/тестом)
- [x] Промпт без коннектов: саммари выходит с 3 блоками
- [x] `get_fragments_for_digest(until=...)` + граничный юнит-тест зелёный
- [x] `/summary` на проде: вайт-лист, ответ в ЛС, PII локальная, негатив-кейсы ок
- [x] Smoke test: реальная команда отработала end-to-end на VPS (len=2213)
- [x] Не сломано: realtime-ingest пишет, dup=0 (total=10956); `pytest tests/ -q` 59 зелёных
- [x] CLAUDE.md обновлён: команда `/summary`, env `WNDR_SUMMARY_ALLOWED`
- [x] context.md проекта обновлён (Текущий фокус + Последние решения)
- [x] Мусор убран (.env.bak, topic_map.json.bak на VPS удалены)
- [x] Статус в PLAN.md → done
- [x] Папка перемещена: todo/digest-on-demand/ → done/digest-on-demand/
- [x] Ветка влита по git-стратегии (feature → master, с подтверждением)

## Доп. правка в ходе плана (вне исходного scope)

Список топиков в `/summary` показал посторонний `raymann_agents` (тестовый чат
`-1003905781841`, не WNDR). Устранено: (1) маппинг убран из `topic_map.json` на
VPS, (2) 4 тестовых фрагмента удалены из БД (подтверждено пользователем),
(3) `get_topics_with_counts(only=…)` ограничивает список до `TOPIC_HINTS`.

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
