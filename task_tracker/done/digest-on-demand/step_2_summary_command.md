# Шаг 2: Команда /summary в боте

> Зависит от: шаг 1 (until в выборке + ядро синтеза по диапазону)
> Статус: [x] done

## Задача

Добавить в `bot/ingest_bot.py` команду `/summary <topic> <date_from> <date_till>`.
Доступ по вайт-листу. Ответ — в ЛС вызвавшему. Переиспользует синтез из шага 1.

### 1. Вайт-лист (env)
В `.env`: `WNDR_SUMMARY_ALLOWED=423915315` (CSV user_id). Парсить в set[int] при
старте бота. Пустой/не задан → НИКОМУ нельзя (fail-closed, безопасно).
Добавить `WNDR_SUMMARY_ALLOWED` в `.env.example` с комментарием.

### 2. CommandHandler
В `bot/ingest_bot.py`, в `main()`, рядом с MessageHandler:
```python
from telegram.ext import CommandHandler
app.add_handler(CommandHandler("summary", on_summary))
```
⚠️ Важно: текущий MessageHandler ловит `filters.ALL & ~filters.StatusUpdate.ALL`.
Команды (`/summary`) тоже сообщения — но `on_message` их игнорировать не обязан
(они не из мапнутого топика обычно). На всякий случай: в `on_message` команды
ingest-ить не нужно (это не контент топика); если `/summary` шлётся в ЛС бота,
chat не в topic_map → `resolve_topic`=None → уже скипается. ОК, конфликта нет.
Но проверь порядок хендлеров и что команда не дублируется в ingest.

### 3. on_summary — логика
```python
async def on_summary(update, context):
    user_id = update.effective_user.id
    # 3.1 whitelist
    if user_id not in ALLOWED:
        await update.message.reply_text("Команда доступна только администраторам.")
        logger.info("summary DENIED user=%s", user_id)
        return
    # 3.2 parse args: <topic> <from> <till>
    args = context.args  # ['questions_to_women', '2026-05-01', '2026-05-31']
    if len(args) != 3:
        await update.message.reply_text(
            "Формат: /summary <topic> <YYYY-MM-DD> <YYYY-MM-DD>")
        return
    topic, from_s, till_s = args
    # 3.3 validate dates (YYYY-MM-DD), from <= till
    #     since = datetime(from), until = datetime(till) + 1 day  (см. step_1)
    #     на ошибке парсинга — reply с примером, return
    # 3.4 validate topic (известный? — можно проверить по distinct topic в БД
    #     или по списку; неизвестный → reply, return)
    # 3.5 синтез по диапазону (ядро из step_1), off the event loop:
    #     text = await asyncio.to_thread(run_digest_range, topic, since, until)
    #     0 фрагментов → reply "За период нет сообщений" БЕЗ траты OpenAI, return
    # 3.6 ответ в ЛС вызвавшему:
    #     await context.bot.send_message(chat_id=user_id, text=text[:4096])
    #     (НЕ через delivery.channels — тот шлёт на фикс. DM_USER_ID)
```

### 4. Ответ в ЛС вызвавшему (не в группу)
Если `/summary` позвали В ГРУППЕ — короткий ack в группу не нужен, шлём результат
сразу в ЛС вызвавшему (`chat_id=user_id`). Если у бота нет открытой ЛС с юзером
(не нажимал /start) — `send_message` упадёт Forbidden: отловить, и в этом случае
reply в исходный чат «Напиши мне в личку /start, чтобы получать саммари».
Дайджест в группу НЕ шлём (решение 4 PLAN).

### 5. Стоп-точка трат
Синтез = трата OpenAI (Pass1+Pass2). Поэтому: вайт-лист (свои), пред-чек «0
фрагментов → не синтезируем», валидация ДО вызова OpenAI. Это всё в on_summary.

## Тесты

- `tests/` — юнит на парсинг аргументов и валидацию (хороший ввод; плохая дата;
  from>till; не 3 аргумента; неизвестный топик). Логику синтеза мокать.
- Вайт-лист: чужой user_id → отказ, синтез не зван (мок не вызван).
- Эти тесты не должны требовать реального Telegram/OpenAI (мокать).

## Команды для верификации

```bash
pytest tests/ -q
# локальный ручной прогон бота с тестовым .env, затем в ЛС бота:
#   /summary questions_to_women 2026-05-01 2026-05-31   → саммари приходит
#   /summary (без аргументов)                            → подсказка формата
#   /summary x 2026-13-99 2026-05-31                     → ошибка даты
# с НЕ-вайтлист аккаунта: /summary ...                   → отказ
```

## Критерии готовности

- [ ] `/summary <topic> <from> <till>` работает для вайт-лист юзера, ответ в ЛС.
- [ ] Чужой юзер — вежливый отказ, OpenAI НЕ зван.
- [ ] Невалидный ввод (даты/кол-во арг/топик/from>till) — понятное сообщение.
- [ ] 0 фрагментов за период → сообщение без траты OpenAI.
- [ ] Forbidden (нет ЛС) → подсказка про /start, бот не падает.
- [ ] Юнит-тесты (парсинг/вайт-лист) зелёные; ingest не сломан.
