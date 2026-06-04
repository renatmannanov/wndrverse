# Шаг 3: Шедулер + embedder как systemd-таймеры

> Зависит от: шаг 2 (бот пишет данные)
> Статус: [x] DONE для прод-деплоя (2026-06-04): embedder-таймер запущен. Дайджест-
>          таймер ВЫНЕСЕН В БЭКЛОГ (`backlog/enable-daily-digest-timer.md`) по решению
>          пользователя — авто-дайджест включим отдельно, когда понадобится.

## Задача

Два systemd-таймера: (а) дайджест раз в день, (б) embedder раз в N часов. Таймеры,
НЕ sleep-loop (решения 3, 4): `Persistent=true` → переживают ребут, не пропускают.
На проде используем `--now` через timer (timer считает «когда»), sleep-loop НЕ
запускаем.

### 1. Дайджест-таймер
`/etc/systemd/system/wndr-digest.service`:
```ini
[Unit]
Description=WNDR daily digest (one-shot)
After=network-online.target docker.service

[Service]
Type=oneshot
User=rm_agent
WorkingDirectory=/home/rm_agent/wndrverse
Environment=PYTHONUTF8=1
EnvironmentFile=/home/rm_agent/wndrverse/.env
ExecStart=/home/rm_agent/wndrverse/.venv/bin/python -m digest.scheduler --now
```
`/etc/systemd/system/wndr-digest.timer`:
```ini
[Unit]
Description=Run WNDR digest daily at 09:00 Asia/Almaty

[Timer]
OnCalendar=*-*-* 09:00:00 Asia/Almaty
Persistent=true

[Install]
WantedBy=timers.target
```
ВРЕМЯ задаёт OnCalendar (источник правды на проде). `WNDR_DIGEST_TOPICS`/`PERIOD` в
`.env` читаются процессом (топики/период выборки). `WNDR_DIGEST_AT` на проде не
влияет (sleep-loop не запускаем) — зафиксировать в progress.md.
Топики: дефолт `questions_to_women,questions_to_men`; после прод-тестов → расширить
ENV на все (решение 5), код не меняем.

### 2. Embedder-таймер
`/etc/systemd/system/wndr-embedder.service`:
```ini
[Unit]
Description=WNDR embedder batch (one-shot)
After=network-online.target docker.service

[Service]
Type=oneshot
User=rm_agent
WorkingDirectory=/home/rm_agent/wndrverse
Environment=PYTHONUTF8=1
EnvironmentFile=/home/rm_agent/wndrverse/.env
ExecStart=/home/rm_agent/wndrverse/.venv/bin/python -m core.enrich.embedder
```
`/etc/systemd/system/wndr-embedder.timer`:
```ini
[Unit]
Description=Embed new fragments every 6h

[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00 Asia/Almaty
Persistent=true

[Install]
WantedBy=timers.target
```
Embedder тратит OpenAI, но: дёшево (text-embedding-3-small) + батч только по
`embedding IS NULL` (дельта с прошлого прогона). Корпус из дампа уже эмбеджен →
таймер обрабатывает лишь новое от бота. Осознанная периодическая трата (решение 4).

### 3. Проверить OnCalendar ДО enable (V1)
Суффикс таймзоны в OnCalendar валиден на systemd v255 (Ubuntu 24.04), но проверяем
явно, чтобы next-run не оказался «never»:
```bash
systemd-analyze calendar "*-*-* 09:00:00 Asia/Almaty"
systemd-analyze calendar "*-*-* 00,06,12,18:00:00 Asia/Almaty"
# у обоих: "Next elapse" должен быть конкретной датой/временем, НЕ "never".
```

### 4. Запуск
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now wndr-digest.timer wndr-embedder.timer
systemctl list-timers | grep wndr     # оба, next-run виден
```

### Заметка
Разовый тест дайджест-сервиса (`systemctl start wndr-digest.service`) — это РЕАЛЬНАЯ
трата OpenAI на синтез. Делается в шаге 4 (прод-smoke), не здесь.

## Тесты

Юнит-тестов нет. Проверка — таймеры активны, list-timers показывает next-run.

## Команды для верификации

```bash
systemctl list-timers | grep wndr
sudo systemctl is-enabled wndr-digest.timer wndr-embedder.timer   # enabled
```

## Критерии готовности

- [x] `wndr-embedder.timer` enabled + active (waiting), `Persistent=true`, виден в
      `systemctl list-timers` (next 19:00 UTC = 00:00 Almaty).
- [→] `wndr-digest.timer` — ВЫНЕСЕН В БЭКЛОГ `backlog/enable-daily-digest-timer.md`
      (решение пользователя). Юнит-конфиг готов в этом файле, enable — отдельной задачей.
- [→] Дайджест-сервис / OnCalendar / источник времени — см. backlog-задачу (там же).
- [x] Embedder-таймер настроен (дельта по embedding IS NULL), каждые 6ч.

## Факты выполнения (2026-06-03)
- Разовый embedder руками: 15 unembedded → 14 embedded + 1 near-dup, unembedded=0,
  total=10955. Стоимость ~$0.00001 (text-embedding-3-small, 628 токенов).
- `systemd-analyze calendar` для embedder OnCalendar = валиден (Next elapse конкретный,
  не never). Таймзона Asia/Almaty распознана на systemd v255.
- ДАЙДЖЕСТ-таймер пока НЕ включён (по запросу). Включение = отдельный заход:
  записать wndr-digest.service+timer, validate OnCalendar, enable.
