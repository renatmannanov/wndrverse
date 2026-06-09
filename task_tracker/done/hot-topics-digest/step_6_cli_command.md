# Шаг 6: CLI-подкоманда `topics`

> Зависит от: шаг 4 (render), шаг 5 (build_topics)
> Статус: [ ] pending

## Задача

В `delivery/cli.py` добавить подкоманду `topics` рядом с `digest`. Тонкая склейка:
store → brain.topics.build_topics → delivery.topics_render → channels.send.
Переиспользует `parse_period`, `parse_date_range`, заголовок.

CLI:
```
python -m delivery topics --topic boltalka --period 1m [--channel stdout] [--limit N]
```

Реализация:
- Новая функция `_run_topics(topic, period, channel, limit)` по образцу `_run_digest`:
  ```python
  def _run_topics(topic_arg, period, channel, limit):
      if topic_arg == "all":
          raise SystemExit("topics поддерживает только ОДИН топик (вариант А), не 'all'")
      since = parse_period(period)
      until = None
      frags = get_embedded_fragments_for_period(topic_arg, since=since, until=until)
      if not frags:
          # печатаем в stdout, а не только в лог — иначе пользователь видит пустоту
          channels.send(f"{_digest_header(topic_arg, since, until)}\n\nЗа период сообщений не найдено.", channel=channel)
          return 0
      topics = build_topics(frags, limit=limit)
      if not topics:
          channels.send(f"{_digest_header(topic_arg, since, until)}\n\nЗа период тем не найдено (всё отсеяно как флуд/шум).", channel=channel)
          return 0
      header = _digest_header(topic_arg, since, until)   # переиспользуем
      text = render_topics(header, topics)
      channels.send(text, channel=channel)
      return 0
  ```
- В `_main`: добавить парсер `topics` с `--topic` (required), `--period` (default
  'all'), `--channel` (default 'stdout'), `--limit` (type int, default None).
- В `_main` в БЛОКЕ ДИСПЕТЧЕРА (где сейчас `if args.command == "digest"`) добавить
  ветку `elif args.command == "topics": return _run_topics(args.topic, args.period,
  args.channel, args.limit)` — ИНАЧЕ упадёт в `parser.error("unknown command")`.
- Импорты вверху: `get_embedded_fragments_for_period`, `build_topics`,
  `render_topics`.
- НЕ менять `_run_digest`, парсер `digest`, `build_digest`, `humanize_*`.
- `_digest_header` переиспользуется как есть (он уже про «📅 name · from — till»).

Правило #1: `topics` — топик ОБЯЗАТЕЛЕН (в отличие от digest, где есть 'all').
Кросс-топик (вариант Б) out-of-scope, поэтому 'all' для topics НЕ поддерживаем —
если передан `--topic all`, вернуть понятную ошибку «topics поддерживает только
один топик (вариант А)» (см. guard в `_run_topics` выше).

## Тесты

- Smoke через реальный запуск (см. команды). Юнит не обязателен — это склейка.
- Что может сломаться: существующая команда `digest`. Проверить отдельно.

## Команды для верификации

```bash
# Новая команда печатает темы в целевом формате
python -m delivery topics --topic boltalka --period 1m

# --limit работает
python -m delivery topics --topic boltalka --period 1m --limit 5

# 'all' отвергается понятно
python -m delivery topics --topic all --period 1m ; echo "exit=$?"

# Существующая digest НЕ сломана
python -m delivery digest --topic offerings --period 1w
```

## Критерии готовности

- [ ] `python -m delivery topics --topic boltalka --period 1m` печатает заголовок
      + ранжированные темы со ссылками.
- [ ] `--limit N` ограничивает число тем.
- [ ] `--topic all` → понятная ошибка, не трейсбек.
- [ ] `python -m delivery digest --topic offerings --period 1w` работает как раньше.
- [ ] 0 фрагментов / 0 кластеров → в STDOUT печатается понятное сообщение (не
      пустота), без краша и без OpenAI-спенда.
