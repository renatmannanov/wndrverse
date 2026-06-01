# Step 6: Завершение плана

> Зависит от: шаги 1-5
> Статус: [ ] pending

## Чеклист

- [ ] Все шаги плана выполнены ([x] в PLAN.md)
- [ ] Критерии готовности из PLAN.md проверены (каждый — командой или тестом)
- [ ] Smoke: `python -m digest.scheduler --now` доставил дайджест в ЛС, длина в
      норме, PII локальная (шаг 5 зелёный)
- [ ] Не сломано: `delivery digest --topic raymann_agents --period all` всё ещё
      работает (ядро синтеза не сломано); `core/llm/client.py` не изменён
      (`git diff` пуст); two-pass логика synthesis по сути та же
- [ ] `curator/`, `agent-template/`, схема БД, bot/ingest_bot.py — не тронуты
- [ ] CLAUDE.md дополнен (V7 — конкретные места, не на усмотрение):
      - команда `python -m digest.scheduler` — НОВОЙ секцией «### Digest scheduler
        (digest/)» сразу ПОСЛЕ секции «### Realtime ingest bot (bot/)»;
      - `digest/` — строкой в списке «Key files» (рядом с `bot/`, `delivery/`);
      - ENV `WNDR_DIGEST_TZ/AT/PERIOD/TOPICS/DM_USER_ID` — в блок «## Env vars»
        (тот же ```-блок, где BOT_TOKEN_INGEST).
- [ ] Бэклог: создан `task_tracker/backlog/digest-trigger-by-context.md` —
      описание будущего триггера по накоплению (fragment_ids в artifacts уже
      сохраняются как фундамент); --angle упомянут там же как future
- [ ] Мусор убран (отладочные принты). `digest/__init__.py` — намеренная
      инфраструктура, НЕ удалять.
- [ ] `.gitignore`: `topic_map.json` по-прежнему игнорируется (в нём добавились
      WNDR chat_id — проверить что не утёк в git)
- [ ] Все тесты зелёные: `python -m pytest tests/ -q`
- [ ] Статус в PLAN.md → done
- [ ] Папка перемещена: `todo/digest-scheduler/` → `done/digest-scheduler/`
- [ ] Перед мержем (V4): убедиться что родительская ветка
      `feature/realtime-bot-ingest` влита в dev/staging — эта ветка отходит от неё,
      не от dev. Мержить либо после влития родителя, либо цепочкой
      (realtime-bot-ingest → dev, затем digest-scheduler → dev). Зафиксировать с
      пользователем порядок до мержа.
- [ ] Ветка влита по git-стратегии (feature → dev/staging), если пользователь
      подтвердил

## Команды финальной проверки

```bash
python -m pytest tests/ -q
git diff --stat core/llm/client.py   # ожидаем пусто
git check-ignore core/ingest/topic_map.json   # печатает путь = IGNORED
python -c "import digest.scheduler; import delivery.channels"   # импорт ок
# регресс ядра: старый топик всё ещё синтезируется (тратит OpenAI — только если нужно)
# python -m delivery digest --topic raymann_agents --period all
```

**Этот шаг обязателен.** Пока он не выполнен — план не считается завершённым.
