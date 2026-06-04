# Шаг 3: Деплой на VPS + прод-smoke

> Зависит от: шаги 1-2 (код готов, тесты зелёные локально)
> Статус: [x] done

> Прод-smoke 2026-06-04: `/summary questions_to_women 2026-05-01 2026-05-31` →
> саммари в ЛС вызвавшему, 3 блока (без коннектов), PII локальная ([Имя, дата]),
> len=2213. Лог VPS: `summary SENT user=423915315`. Корпус: total=10956, dup=0.
> Попутно убран посторонний маппинг raymann_agents из topic_map.json + удалены
> 4 тестовых фрагмента; список топиков в /summary ограничен TOPIC_HINTS.

## Задача

Выкатить фичу на прод, перезапустить ingest-бот, прогнать реальную команду.

### 1. Влить и запушить (git-стратегия)
```bash
# локально: feature/digest-on-demand → master (после прохождения тестов)
git checkout master && git merge feature/digest-on-demand
git push origin master
```
(Согласовать слияние с пользователем — см. CLAUDE.md рабочий протокол.)

### 2. Обновить код на VPS
```bash
ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95
cd ~/wndrverse
git pull origin master
git log --oneline -3                     # видно новый коммит
```

### 3. Добавить env на VPS
В `~/wndrverse/.env` дописать:
```
WNDR_SUMMARY_ALLOWED=423915315
```
(значения вписывает пользователь/оператор; стартовый список — владелец, позже
админы сообщества). `chmod 600 .env` уже стоит.

### 4. Перезапустить ingest-бот (подхватит CommandHandler + новый env)
```bash
sudo systemctl restart wndr-ingest-bot
sudo systemctl status wndr-ingest-bot --no-pager | head -8     # active (running)
journalctl -u wndr-ingest-bot -n 20 --no-pager                # стартовал чисто
```
⚠️ Бот короткоживуще прервётся на рестарте — пропущенные за ~2 сек сообщения
теоретически возможны, но polling после старта подтянет недавние updates. Делать
в спокойное время. (Realtime-ingest код не менялся — риск минимальный.)

### 5. Прод-smoke реальной командой (СТОП-ТОЧКА: трата OpenAI)
В ЛС бота от вайт-лист аккаунта:
```
/summary questions_to_women 2026-05-01 2026-05-31
```
Проверить:
- саммари пришло в ЛС вызвавшему;
- 3 блока (БЕЗ коннектов);
- PII локальная (`[Имя, дата]`, не `[#id]`);
- длина ≤ 4096;
- содержимое по реальным вопросам периода.
Затем негатив: `/summary` без аргументов → подсказка; с не-вайтлист аккаунта →
отказ.

## Команды для верификации

```bash
sudo systemctl is-active wndr-ingest-bot
journalctl -u wndr-ingest-bot -n 30 --no-pager | grep -iE "summary|denied|ingest"
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT id, topic, length(content) FROM artifacts ORDER BY id DESC LIMIT 3;"
```

## Критерии готовности

- [ ] master запушен; VPS на новом коммите; ingest-бот перезапущен, active.
- [ ] `WNDR_SUMMARY_ALLOWED` в `.env` на VPS.
- [ ] Реальная `/summary` от своего → саммари в ЛС, 3 блока, PII локальная, длина ок.
- [ ] Негатив-кейсы (нет аргументов / чужой / плохая дата) ведут себя как задумано.
- [ ] Realtime-ingest продолжает писать новые сообщения (count растёт, dup=0).
- [ ] OpenClaw/Hermes не затронуты.
