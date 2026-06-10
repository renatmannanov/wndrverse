# Step 4: Завершение плана

> Статус: done

## Чеклист

- [x] Все шаги плана выполнены ([x] в PLAN.md)
- [x] Критерии готовности из PLAN.md проверены (каждый — командой или тестом)
- [x] Smoke (юнит): `python -m pytest tests/test_topics_command.py -q` зелёный
- [x] Не сломано: `python -m pytest tests/test_summary_command.py -q` и
      `python -m delivery digest --topic offerings --period 1w` и
      `python -m delivery topics --topic boltalka --period 1m` — работают как раньше
- [x] Все тесты зелёные: `python -m pytest tests/ -q`
- [x] PII-проверка: бот пересылает текст из ядра, имён не подмешивает (в OpenAI
      ушли только тексты — ядро не тронуто)
- [x] CLAUDE.md обновлён: в секцию про realtime ingest bot / hot-topics добавить
      строку про команду `/topics` (формат, что в DM, вайтлист — по аналогии с
      описанием `/summary`)
- [x] Env vars в CLAUDE.md: отметить, что `/topics` использует тот же
      `WNDR_SUMMARY_ALLOWED` (отдельная переменная НЕ нужна)
- [x] Мусор убран (временные скрипты отладки, если были)
- [x] Статус в PLAN.md → done
- [x] Папка перемещена: todo/topics-bot-command/ → done/topics-bot-command/

## Прод-деплой (НЕ делать в этом плане — по отдельной команде пользователя)

После мёрджа в master и пуша:
```bash
ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95
cd ~/wndrverse && git pull origin master
sudo systemctl restart wndr-ingest-bot
journalctl -u wndr-ingest-bot -f          # проверить старт без ошибок
```
Деплой выполняется ТОЛЬКО по явной команде пользователя (правило CLAUDE.md про
рискованные операции). Не трогать OpenClaw/Hermes units.

## Решение по дальнейшему (записать в progress.md, НЕ делать сейчас)

После показа заказчику: заходит ли формат через бота → стоит ли делать
scheduler (авто-дайджест тем) и/или постинг прямо в топик группы
(`telegram_group` channel). Отдельный план, не часть этого.
