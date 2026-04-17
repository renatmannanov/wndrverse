# Шаг 7: Telegram Managed Bots — создание дочерних ботов

> Зависит от: шаг 1 (инфраструктура)
> Статус: done (протестировано 2026-04-16)

## Задача

Протестировать Telegram Managed Bots API.
Цель: @wndrverse_bot (родитель) создаёт дочернего бота, получает его токен, постит от его имени в Bus.

## Предусловия

- @wndrverse_bot уже создан и работает (шаг 1)
- Бот добавлен в группу как администратор

## Что делаем

### 7.1 Включить Bot Management Mode

1. Открыть BotFather → найти @wndrverse_bot
2. Перейти в BotFather MiniApp (не обычное меню)
3. Включить "Bot Management Mode"
4. Проверить: бот получает поле `can_manage_bots = true`

```bash
# Проверить через getMe
curl "https://api.telegram.org/bot$CURATOR_BOT_TOKEN/getMe" | python -m json.tool
# Ожидаем: "can_manage_bots": true
```

### 7.2 Создать дочернего бота вручную (тест)

Сформировать ссылку и открыть в Telegram:

```
https://t.me/newbot/wndrverse_bot/test_agent_wndr?name=Test+Agent
```

> Заменить `wndrverse_bot` на реальный username родителя.
> `test_agent_wndr` — предлагаемый username дочернего (пользователь может изменить).

После подтверждения: @wndrverse_bot получит `managed_bot` update.

### 7.3 Получить токен дочернего бота

> **ВАЖНО:** параметр называется `user_id`, не `bot_id`!

```bash
# Через Bot API
curl -X POST "https://api.telegram.org/bot$CURATOR_BOT_TOKEN/getManagedBotToken" \
  -d "user_id=<BOT_USER_ID_FROM_UPDATE>"
```

Или в Python:

```python
import httpx

PARENT_TOKEN = os.getenv("CURATOR_BOT_TOKEN")

# Получить updates (найти managed_bot update)
r = httpx.get(f"https://api.telegram.org/bot{PARENT_TOKEN}/getUpdates")
updates = r.json()["result"]
for u in updates:
    if "managed_bot" in u:
        bot_user_id = u["managed_bot"]["bot"]["id"]
        print(f"Managed bot created: {bot_user_id}")

# Получить токен дочернего (параметр: user_id!)
r = httpx.post(
    f"https://api.telegram.org/bot{PARENT_TOKEN}/getManagedBotToken",
    data={"user_id": bot_user_id},
)
child_token = r.json()["result"]  # токен напрямую в result, не result.token
print(f"Child token: {child_token}")
```

### 7.3.1 Добавить дочернего бота в группу

> **Ограничение Telegram:** бот не может добавить другого бота в группу через API.
> Нужно добавить вручную: админ группы добавляет @дочернего_бота как администратора.

### 7.4 Постить от имени дочернего бота

```bash
# Добавить дочернего бота в группу как админа, затем:
curl -X POST "https://api.telegram.org/bot$CHILD_TOKEN/sendMessage" \
  -d "chat_id=$GROUP_CHAT_ID&message_thread_id=$BUS_TOPIC_ID&text=[test_agent|managed] Hello from managed bot!"
```

### 7.5 Интегрировать в бэкенд (если тесты прошли)

Добавить в `members.json`:
```json
{
  "name": "Test Agent",
  "tg_username": "test_agent_wndr",
  "managed": true,
  "agent_token_env": "AGENT_TEST_TOKEN"
}
```

Обновить `curator/bus.py`: поддержка нескольких токенов (каждый агент постит от своего бота).

## Команды для верификации

```bash
# 1. Проверить can_manage_bots
curl "https://api.telegram.org/bot$CURATOR_BOT_TOKEN/getMe" | python -c "
import sys, json
data = json.load(sys.stdin)
print('can_manage_bots:', data['result'].get('can_manage_bots', False))
"

# 2. Проверить что managed bot создан
curl "https://api.telegram.org/bot$CURATOR_BOT_TOKEN/getUpdates" | python -c "
import sys, json
for u in json.load(sys.stdin)['result']:
    if 'managed_bot' in u:
        print('Managed bot:', u['managed_bot'])
"

# 3. Проверить что дочерний бот пишет в Bus
# → визуально в Telegram: сообщение от @test_agent_wndr в Bus топике
```

## Результаты теста (2026-04-16)

- Родитель: `@rm_curator_bot` (id: 8771986558, can_manage_bots: true)
- Дочерний: `@test_wndr_agentbot` (id: 8733226908)
- Токен получен через `getManagedBotToken` с параметром `user_id` (НЕ `bot_id`)
- Дочерний добавлен в группу вручную как админ (API не позволяет автоматически)
- Сообщение от дочернего в Bus: message_id=47
- Реплай родителя на сообщение дочернего: message_id=48

## Критерии готовности

- [x] Bot Management Mode включён для @rm_curator_bot
- [x] `getMe` возвращает `can_manage_bots: true`
- [x] Дочерний бот создан через ссылку `t.me/newbot/rm_curator_bot/test_wndr_agent`
- [x] Токен дочернего получен через `getManagedBotToken(user_id=...)`
- [x] Дочерний бот отправил сообщение в Bus от своего имени
- [x] Формат сообщения: `[test_agent|managed] текст`

## Если не работает

- **BotFather MiniApp не показывает Bot Management Mode:** фича может быть не доступна для всех ботов. Проверить что бот не в sandbox mode. Попробовать через @BotFather команду `/mybots` → выбрать бота → Bot Settings.
- **getManagedBotToken возвращает ошибку:** убедиться что bot_id правильный (из update, не из ссылки).
- **Дочерний бот не может писать в группу:** нужно добавить его как админа с правом отправки сообщений.
