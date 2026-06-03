# Шаг 5: Завершение плана prod-deploy

> Зависит от: шаги 1-4
> Статус: [ ] pending

## Чеклист

- [ ] Все шаги плана выполнены ([x] в PLAN.md)
- [ ] Критерии готовности из PLAN.md проверены (каждый — командой/проверкой на VPS)
- [ ] Корпус на проде = дамп локального: total совпадает; dup_keys=0; unembedded=0
- [ ] Прод-smoke зелёный: реальный WNDR-дайджест доставлен в ЛС (шаг 4)
- [ ] systemd: `wndr-ingest-bot.service` active; `wndr-digest.timer` +
      `wndr-embedder.timer` enabled (`systemctl list-timers`)
- [ ] Существующие сервисы VPS (OpenClaw/Hermes) не затронуты
- [ ] CLAUDE.md обновлён:
      - deploy-карта: каталог core-пайплайна на VPS (из step_1), что деплоится;
      - новая секция «### Production (systemd на VPS)»: юниты + команды
        (`systemctl status/list-timers`, journalctl, перенос дампа).
- [ ] Мусор убран: дамп-файлы (`*.sql`) не в git, временные не разрослись
- [ ] `.gitignore`: `.env`, `topic_map.json`, `*.sql` игнорируются (`git check-ignore`)
- [ ] Статус в PLAN.md → done
- [ ] Папка перемещена: `todo/prod-deploy/` → `done/prod-deploy/`
- [ ] Ветка влита по git-стратегии (после data-corpus), если пользователь подтвердил

## Команды финальной проверки

```bash
# на VPS:
sudo systemctl is-active wndr-ingest-bot
systemctl list-timers | grep wndr
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) AS total, count(*)-count(DISTINCT external_id) AS dup, \
   count(*) FILTER (WHERE embedding IS NULL) AS unemb FROM fragments;"
# ожидаем: dup=0, unemb=0, total = локальный
# локально:
git check-ignore .env core/ingest/topic_map.json
```

**Этот шаг обязателен.** Пока он не выполнен — план не считается завершённым.
