# Шаг 5: Smoke-тест на одной реальной группе

> Зависит от: шаги 1-4
> Статус: [ ] pending

## Задача

Проверить весь путь end-to-end на ОДНОЙ реальной тестовой группе: добавить бота,
послать сообщения, убедиться что они в БД с правильными полями и без дублей.

### Предусловия (делает пользователь, не агент)
- Бот создан у @BotFather, `BOT_TOKEN_INGEST` в `.env`.
- Бот добавлен в ОДНУ тестовую группу (какую — открытый вопрос в PLAN.md).
- **chat_id группы узнаётся СТОРОННИМ ботом** (@getmyid_bot / @userinfobot,
  добавить в группу на минуту, прочитать chat_id, удалить). НЕ через наш бот —
  он скипает чаты, которых ещё нет в конфиге, поэтому chat_id своего бота не
  залогирует (петля). Один способ, зафиксировано.
- Полученный chat_id внесён в `core/ingest/topic_map.json` с нужным topic
  (`thread_id: null` для обычной группы).

### Прогон
1. `docker compose up -d db` — БД поднята.
2. Запустить бота: `python -m bot.ingest_bot` (единственная форма запуска).
3. В группе вручную написать ~5 содержательных сообщений (>150 символов хотя бы
   часть, чтобы потом прошли в digest), включая 1 reply и 1 медиа-с-подписью.
4. Проверить БД (см. команды).
5. Послать то же сообщение ещё раз / перезапустить бота и проверить, что
   повторного приёма того же `message_id` нет (дедуп).

> Примечание: topic_map грузится в память при старте бота. Если правишь
> `topic_map.json` — **перезапусти бота** (`python -m bot.ingest_bot`), иначе
> новые пары не подхватятся и сообщения будут скипаться.

## Команды для верификации

```bash
# psql-юзер = postgres (docker-compose.yml НЕ задаёт POSTGRES_USER → дефолт
# postgres; БД wndrverse, пароль localpass). НЕ wndruser — такого юзера нет.

# сколько фрагментов от бота (external_id начинается с tgbot_)
docker compose exec db psql -U postgres -d wndrverse -c \
  "SELECT count(*) FROM fragments WHERE external_id LIKE 'tgbot_%';"

# проверить поля происхождения у последних 5
docker compose exec db psql -U postgres -d wndrverse -c \
  "SELECT external_id, topic, channel_id, message_thread_id, sender_id, left(text,40) \
   FROM fragments WHERE external_id LIKE 'tgbot_%' ORDER BY id DESC LIMIT 5;"

# дедуп: повторный приём не увеличивает count (запустить до и после повтора)
# ожидаем одинаковое число
```

## Критерии готовности

- [ ] ~5 сообщений из группы появились в `fragments` с `external_id LIKE 'tgbot_%'`.
- [ ] `topic` совпадает с маппингом, `channel_id` = chat_id группы,
      `sender_id` заполнен, `message_thread_id` корректен (None для обычной группы).
- [ ] reply → `metadata->>'reply_to_msg_id'` заполнен.
- [ ] медиа-с-подписью попало (caption как text); медиа-без-подписи НЕ попало.
- [ ] повторный приём того же `message_id` → count не вырос (дедуп работает).
