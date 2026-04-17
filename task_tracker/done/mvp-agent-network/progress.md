# Progress Log — mvp-agent-network

## Контекст для агента

- Основной источник данных: приватный канал Рената через telegram-gather HTTP API (Railway 24/7)
- Тестовая группа: супергруппа "rayverse" с 2 топиками (Bus + Showcase)
- Реализация агентов: `client.messages.create()` + промпты из `curator/prompts/`
- Архитектура: Вариант В — куратор дефолтный за всех + свои агенты для vibe-coderов
- 2 агента MVP: тема AI/агенты и тема сообщества/дети
- Сценарий 2 (куратор решает) — основной. Сценарий 1 (голосование) — stretch goal.
- Масштабирование после MVP: WNDR группа (112 человек)

## Learnings

### 2026-04-13: Агенты репостят вместо фильтрации
- Первый прогон: 19 из 26 сообщений попало в Bus
- Причина: промпты не ограничивали количество и не задавали критерии отсева
- Решение: жёсткий лимит MAX 2 на агента + критерии "что НЕ брать"

### 2026-04-13: Telethon → telegram-gather
- Убрали прямой Telethon из wndrverse
- telegram-gather уже работает на Railway, просто HTTP запросы через httpx
- Убирает проблемы с OTP, сессиями, авторизацией

### 2026-04-13: get_bus_messages() не работает
- telegram-gather не возвращает message_thread_id
- Фильтрация по reply_to == BUS_TOPIC_ID — неправильная (reply_to = ID сообщения, не топика)
- Для MVP не нужна: main.py передаёт bus_posts в памяти, не перечитывая Telegram
- Для v2: добавить message_thread_id в telegram-gather или читать через Bot API

### 2026-04-13: Managed Agents API
- Изначально планировали client.beta.agents.create() / client.beta.sessions.create()
- Заменили на стандартный client.messages.create() — проще, работает сейчас
- Managed Agents можно вернуть в v2 если понадобится

### 2026-04-16: Telegram Bot API 9.6 — Managed Bots & Bot-to-Bot
- Telegram добавил Managed Bots: бот-родитель создаёт дочерних ботов для пользователей
- Bot-to-Bot Communication: боты видят и реагируют на сообщения друг друга в группах
- **Решение:** отдельный куратор-бот не нужен. @wndrverse_bot = менеджер + куратор + бэкенд
- **Managed Bots** решает онбординг: участник нажимает кнопку → получает персонального бота (zero-setup)
- **Bot-to-Bot** решает pre-matching: агенты реагируют друг на друга в Bus, Сценарий 1 становится реальным
- Архитектура: один бэкенд, много токенов. Каждый токен = отдельная "личность" в Telegram
- Обязательна защита от петель (rate limit, max depth, dedup) — Telegram предупреждает о санкциях
- Добавлены шаги 7 (managed bots) и 8 (bot-to-bot) в план
- ARCHITECTURE.md обновлён с новой диаграммой

### 2026-04-16: Тест Managed Bots + Bot-to-Bot — SUCCESS
- Создан дочерний бот @test_wndr_agentbot через ссылку `t.me/newbot/rm_curator_bot/test_wndr_agent`
- **getManagedBotToken** — параметр называется `user_id`, не `bot_id` (документация неточная)
- **Токен** возвращается напрямую в `result` (строка), не в `result.token`
- Дочерний бот отправил сообщение в Bus (message_id=47)
- @rm_curator_bot видит сообщение через b2b и реплаит (message_id=48)
- **Ограничение:** дочернего бота нужно вручную добавить в группу как админа — API не позволяет ботам добавлять других ботов
- **Ограничение:** b2b mode и Bot Management Mode включаются только через BotFather вручную, нет API
- **Режим managed/custom** добавлен в архитектуру (ARCHITECTURE.md)
