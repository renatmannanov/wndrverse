# Шаг 5: Завершение плана prod-deploy

> Зависит от: шаги 1-4
> Статус: [x] DONE (2026-06-04)

## Чеклист

- [x] Все шаги плана выполнены ([x] в PLAN.md); дайджест-таймер → backlog.
- [x] Критерии готовности из PLAN.md проверены командами на VPS (2026-06-04).
- [x] Корпус на проде = дамп локального: total совпал (10940 на restore); dup=0;
      unembedded=0. Сейчас 10956 (бот пишет live), dup=0, unemb=0.
- [x] Прод-smoke зелёный: реальный синтез дайджеста доставлен в ЛС через `/summary`
      (artifacts id 12-15). Дайджест-таймер отдельно — backlog.
- [x] systemd: `wndr-ingest-bot.service` active; `wndr-embedder.timer` active+enabled
      (реально срабатывает, виден в list-timers). `wndr-digest.timer` → backlog.
- [x] Существующие сервисы VPS (OpenClaw/Hermes) не затронуты (наши юниты `wndr-*`).
- [x] CLAUDE.md обновлён: deploy-карта (каталог `~/wndrverse`) + секция
      «### Production (systemd на VPS)» (юниты, ops-команды, способ дампа).
- [x] Мусор убран: дамп-файлы (`*.sql`) не в git (проверено `git ls-files`); .sql
      удалён с VPS и локально ещё в step_1.
- [x] `.gitignore`: `.env`, `topic_map.json`, `*.sql` игнорируются (`git check-ignore` ОК).
- [x] Статус в PLAN.md → done.
- [x] Папка перемещена: `todo/prod-deploy/` → `done/prod-deploy/`.
- [x] Ветка: работали на master (data-corpus влит ff). Отдельной feature-ветки не
      было (инфра-деплой). Изменения = правки планов + CLAUDE.md, коммитятся в master.

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
