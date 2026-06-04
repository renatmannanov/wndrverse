# Backlog: включить авто-дайджест таймер на проде

> Происхождение: отложенная часть плана `prod-deploy` (step_3). Инфра-деплой
> завершён, но ежедневный авто-дайджест в ЛС пользователь решил пока не включать
> (2026-06-03). Эта задача — включить его, когда понадобится.

## Что нужно сделать

Поднять `wndr-digest.timer` (systemd) на VPS, чтобы раз в день синтезировать
дайджест по `WNDR_DIGEST_TOPICS` и DM-ить его пользователю. Реализация уже
описана и проверена — нужно только enable.

## Контекст (прод уже работает)

- VPS `rm_agent@62.238.31.95`, каталог `~/wndrverse`. SSH:
  `ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95`.
- Уже active: `wndr-ingest-bot.service` (realtime сбор), `wndr-embedder.timer` (6ч).
- БД postgres+pgvector в docker, корпус ~10955, всё эмбеджено.
- Путь синтеза проверен: реальные дайджесты уже синтезировались на проде через
  команду `/summary` (artifacts id 12-15 в БД, 2026-06-04). Код рабочий.

## Юнит-конфиги (готовы — взять из prod-deploy/step_3)

`/etc/systemd/system/wndr-digest.service` (Type=oneshot, путь `/home/rm_agent/wndrverse`,
EnvironmentFile=.env, ExecStart=`.venv/bin/python -m digest.scheduler --now`).

`/etc/systemd/system/wndr-digest.timer`:
```ini
[Timer]
OnCalendar=*-*-* 09:00:00 Asia/Almaty
Persistent=true
[Install]
WantedBy=timers.target
```

## Порядок включения

1. Записать оба юнита (sudo tee), `daemon-reload`.
2. ⚠️ ВАЛИДАЦИЯ ДО enable: `systemd-analyze calendar "*-*-* 09:00:00 Asia/Almaty"`
   — Next elapse должен быть конкретным, НЕ never.
3. ⚠️ СМОУК ДО enable (трата OpenAI): `sudo systemctl start wndr-digest.service`
   один раз, проверить journalctl + что дайджест пришёл в ЛС. ЭТО ТРАТА OpenAI на
   синтез — подтвердить с пользователем.
4. `sudo systemctl enable --now wndr-digest.timer`; `systemctl list-timers | grep wndr`.

## Решения (зафиксированы в prod-deploy)

- Время задаёт OnCalendar (источник правды на проде), НЕ WNDR_DIGEST_AT.
- `Persistent=true` (переживает ребут, не пропускает).
- Топики/период/получатель — через .env (`WNDR_DIGEST_TOPICS`, `WNDR_DIGEST_PERIOD`,
  `WNDR_DIGEST_DM_USER_ID`). Сначала questions_to_*, потом расширить ENV на все.
- Пользователь должен `/start` ingest-бота в ЛС (Telegram не даёт боту писать первым).

## Критерии готовности

- [ ] `wndr-digest.timer` enabled + active, `Persistent=true`, виден в list-timers.
- [ ] Смоук: реальный дайджест доставлен в ЛС, PII локальная, длина ≤ 4096.
- [ ] CLAUDE.md: упомянуть включённый дайджест-таймер.
- [ ] Existing сервисы (ingest-бот, embedder, OpenClaw/Hermes) не затронуты.
