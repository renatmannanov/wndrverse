# Шаг 2: Бот-ингестор как systemd-сервис

> Зависит от: шаг 1 (БД + корпус на VPS)
> Статус: [ ] pending

## Задача

Запустить `bot/ingest_bot.py` как постоянный systemd-сервис на VPS. С этого момента
новые сообщения WNDR-топиков пишутся в БД в реальном времени (поверх корпуса из
дампа — дедуп по единому ключу `tg_{chat_id}_{msg_id}` не задвоит).

### 0. privacy mode OFF (подтвердить ДО запуска)
@BotFather → `/setprivacy` → бот `BOT_TOKEN_INGEST` → **Disable**. Без этого бот не
видит обычные сообщения группы. Бот в WNDR chat — ГОТОВО (подтверждено
пользователем).

### 1. systemd-юнит
`/etc/systemd/system/wndr-ingest-bot.service` (sudo):
```ini
[Unit]
Description=WNDR realtime ingest bot
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=rm_agent
WorkingDirectory=/home/rm_agent/wndrverse
Environment=PYTHONUTF8=1
EnvironmentFile=/home/rm_agent/wndrverse/.env
ExecStart=/home/rm_agent/wndrverse/.venv/bin/python -m bot.ingest_bot
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```
WorkingDirectory — `~/wndrverse` (зафиксировано в step_1). `PYTHONUTF8=1` — кириллица в логах.

### 2. Запуск
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now wndr-ingest-bot
sudo systemctl status wndr-ingest-bot     # active (running)
journalctl -u wndr-ingest-bot -f          # видит сообщения, пишет фрагменты
```

### НЕ делать здесь
- Не трогать systemd-юниты OpenClaw/Hermes.
- Не менять bot/ingest_bot.py (готов; дедуп-правка bot_adapter.py — в data-corpus).

## Тесты

Юнит-тестов нет. Проверка — сервис active + реальное сообщение долетает в БД.

## Команды для верификации

```bash
sudo systemctl status wndr-ingest-bot     # active (running)
# отправить тестовое сообщение в WNDR-топик questions_to_*, затем:
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT external_id, topic, left(text,40) FROM fragments \
   WHERE topic LIKE 'questions_to_%' ORDER BY id DESC LIMIT 3;"
# ожидаем: свежее, external_id = tg_-100…_NNN; дублей по ключу нет
```

## Критерии готовности

- [ ] privacy mode OFF (подтверждено в @BotFather).
- [ ] `wndr-ingest-bot.service` active + enabled (автостарт при ребуте).
- [ ] Тестовое сообщение появилось в БД с ключом `tg_{chat_id}_{msg_id}`, без дубля.
- [ ] Сервисы VPS (OpenClaw/Hermes) не затронуты.
