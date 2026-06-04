# digest-on-demand

> Статус: pending
> Дата: 2026-06-04
> Тип: фича (команда саммари в боте + выборка по диапазону дат)
> Ветка: feature/digest-on-demand (от master)

## Контекст (для агента из другого окна — читать первым)

Прод уже работает (план `prod-deploy` = шаги 1-2 done, embedder-таймер done):
- VPS Hetzner `rm_agent@62.238.31.95`, каталог `~/wndrverse`. SSH:
  `ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95`.
- БД postgres+pgvector в docker (`docker compose` в `~/wndrverse`, порт 5434).
  Корпус ~10955 фрагментов, dup=0, всё эмбеджено.
- `wndr-ingest-bot.service` (systemd, active) = realtime listener: новые сообщения
  WNDR-топиков → БД. Сейчас это ЧИСТЫЙ слушатель (только `on_message`, без команд).
- `wndr-embedder.timer` (каждые 6ч) догоняет эмбеддинги.
- Дайджест-таймер (`wndr-digest.timer`) ПОКА НЕ включён (отложен пользователем).

**Эта задача добавляет ручной вызов саммари командой в боте + точный диапазон дат.**
НЕ трогает realtime-ingest, дедуп, embedder, корпус.

## Цель

1. Убрать из промпта саммари блок «🔗 ПОЛЕЗНЫЕ СВЯЗИ» (коннекты).
2. Дать выборку фрагментов по ТОЧНОМУ диапазону дат `from..till` (сейчас только
   `since` = «N назад от сейчас»).
3. Добавить в бота команду `/summary <topic> <date_from> <date_till>` → синтез по
   диапазону → ответ в ЛС вызвавшему. Доступ — по вайт-листу user_id.

## Зафиксированные решения (НЕ переобсуждать)

1. **Коннекты — убрать ПОЛНОСТЬЮ.** Удалить блок `🔗 ПОЛЕЗНЫЕ СВЯЗИ` из
   `core/prompts/digest_synthesis.md`. Остаются 3 блока: ГЛАВНЫЕ ТЕМЫ, КТО ЧТО,
   НЕ ПОТЕРЯТЬ. (Решение пользователя 2026-06-04.)
2. **Формат дат = `YYYY-MM-DD`.** Пример:
   `/summary questions_to_women 2026-05-01 2026-05-31`. Диапазон ВКЛЮЧИТЕЛЬНЫЙ по
   обоим концам (till = конец дня date_till, т.е. `< date_till + 1 день`).
3. **Доступ = вайт-лист.** Env `WNDR_SUMMARY_ALLOWED` = CSV user_id, кому можно звать
   `/summary`. Чужие — вежливый отказ + лог. Старт: владелец (423915315); позже
   добавим админов сообщества (правка ENV, код не меняем).
4. **Ответ = в ЛС вызвавшему** (`update.effective_user.id`), НЕ в группу. Бот сейчас
   ничего в группу не пишет — сохраняем это. (Позже добавим отдельный топик для
   саммари — НЕ в этой задаче, бэклог.)
5. **PII не ломаем.** Синтез видит только `[#id]`+текст; имена подставляются локально
   (`humanize_refs` в `delivery/cli.py`). Команда `/summary` использует тот же путь.
6. **Переиспользуем существующий синтез.** Команда зовёт уже готовый `_run_digest`
   (или его части) — НЕ дублируем synth/humanize. Меняем только: (а) добавляем
   `until` в выборку, (б) канал ответа = ЛС вызвавшему вместо фикс. DM_USER_ID.

## Что уже есть в коде (агенту — не искать заново)

- `core/prompts/digest_synthesis.md` — промпт синтеза. Блок коннектов = строки 9-10
  (`🔗 ПОЛЕЗНЫЕ СВЯЗИ ...`).
- `core/store/fragments_db.py:210` — `get_fragments_for_digest(topic, since, min_chars)`.
  Фильтрует `created_at >= since`. НЕТ верхней границы — добавить параметр `until`.
- `delivery/cli.py` — `_run_digest(topic, period, channel)`, `parse_period`,
  `humanize_refs`. Синтез+humanize+send. Канал `telegram_dm` шлёт жёстко на
  `WNDR_DIGEST_DM_USER_ID` (`delivery/channels.py:_send_telegram_dm`).
- `delivery/channels.py` — `send(text, channel)`. `telegram_dm` = бот→фикс. user_id.
  Для ответа вызвавшему нужен ДРУГОЙ путь (см. step_3) — внутри async-хендлера бота.
- `bot/ingest_bot.py` — listener. `main()` строит `Application`, вешает
  `MessageHandler`. Сюда добавить `CommandHandler("summary", ...)`.
- `core/brain/synthesis.py` — `synthesize_and_save(topic_arg, fragments, topic_type)`.

## Шаги

| # | Файл | Статус |
|---|------|--------|
| 1 | step_1_prompt_and_date_range.md | [x] |
| 2 | step_2_summary_command.md       | [x] |
| 3 | step_3_deploy_and_smoke.md      | [ ] |
| 4 | step_4_completion.md            | [ ] |

## Критерии готовности

- [ ] Промпт без блока коннектов; саммари выходит с 3 блоками.
- [ ] `get_fragments_for_digest` принимает `until`; выборка по `from..till` верна
      (юнит-тест на границы: фрагмент ровно в date_from и ровно в date_till попадает).
- [ ] `/summary <topic> <YYYY-MM-DD> <YYYY-MM-DD>` в боте: вайт-лист пускает своих,
      чужих отказывает; синтез по диапазону; ответ в ЛС вызвавшему; PII локальная.
- [ ] Невалидный ввод (плохая дата, неизвестный топик, from>till, 0 фрагментов) —
      понятное сообщение, НЕ трата OpenAI на пустоте, бот не падает.
- [ ] Тесты зелёные (`pytest tests/ -q`); существующий ingest/digest не сломан.
- [ ] Задеплоено на VPS, бот перезапущен, прод-smoke реальной командой прошёл.
- [ ] CLAUDE.md обновлён (команда /summary, env WNDR_SUMMARY_ALLOWED).

## Что НЕ в этой задаче (scope creep)

- ❌ Доставка саммари в отдельный ТОПИК группы (бэклог — пока только ЛС).
- ❌ Включение авто-дайджест-таймера (`wndr-digest.timer`) — отдельно (prod-deploy).
- ❌ Относительные периоды (7d/1w) в /summary — только точные даты YYYY-MM-DD.
- ❌ Правка realtime-ingest, дедупа, embedder, корпуса.

## Открытые вопросы

- Стартовый вайт-лист = `423915315` (владелец). Список админов сообщества добавит
  пользователь позже правкой ENV. До деплоя уточнить, нужны ли ещё id сразу.
