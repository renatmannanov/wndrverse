# Шаг 1: Инфраструктура

> Зависит от: нет
> Статус: pending

## Задача

Создать Telegram супергруппу с двумя топиками и бота.

## Что делаем

1. Создать Telegram супергруппу (Topics включены) - done
2. Создать Топик 1: "Bus" — только боты пишут, люди читают - done
3. Создать Топик 2: "Showcase" — только куратор пишет - done
4. Создать бота через @BotFather → получить BOT_TOKEN - 
5. Добавить бота в группу как администратора
6. Получить CHAT_ID группы и TOPIC_ID каждого топика
7. Создать `.env` файл с переменными

## .env структура

```
CURATOR_BOT_TOKEN=YOUR_CURATOR_BOT_TOKEN
AGENT_ONE_BOT_TOKEN=YOUR_AGENT_ONE_BOT_TOKEN
GROUP_CHAT_ID=-1003968221945
BUS_TOPIC_ID=3
SHOWCASE_TOPIC_ID=1
PRIVATE_CHANNEL=iwacado
PUBLIC_CHANNEL=projectness
ANTHROPIC_API_KEY=YOUR_ANTHROPIC_API_KEY
AGENT_ID_AI=
AGENT_ID_COMMUNITY=
TG_GATHER_URL=https://YOUR_RAILWAY_APP.railway.app
TG_GATHER_API_KEY=YOUR_TG_GATHER_API_KEY
```

> Токены ботов пока тестовые — перед релизом в open-source сделать revoke и перевыпустить.

## Как получить ID (уже получено)

- `GROUP_CHAT_ID` = `-1003968221945` (группа "rayverse")
- `BUS_TOPIC_ID` = `3` (топик "Bus")
- `SHOWCASE_TOPIC_ID` = `1` (топик "Showcase" / General)

Для новых групп — отправить сообщение в топик и посмотреть `message_thread_id`:
```bash
curl "https://api.telegram.org/bot$CURATOR_BOT_TOKEN/getUpdates"
```

Для `GROUP_CHAT_ID` — в ответе поле `chat.id` (отрицательное число для супергруппы).

## Команды для верификации

```bash
# Проверить что бот может писать в Bus топик
curl -X POST "https://api.telegram.org/bot$CURATOR_BOT_TOKEN/sendMessage" \
  -d "chat_id=$GROUP_CHAT_ID&message_thread_id=$BUS_TOPIC_ID&text=test"

# Ответ должен содержать "ok":true
```

## Критерии готовности

- [ ] Группа создана, Topics включены
- [ ] Два топика созданы (Bus, Showcase)
- [ ] Бот — администратор группы
- [ ] `.env` заполнен всеми переменными
- [ ] curl-тест: бот пишет в Bus → сообщение появляется
