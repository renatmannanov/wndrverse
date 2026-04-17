# Step 1: Создать дочерних ботов и добавить в группу

> Статус: pending

## Что делаем

Создаём 2 дочерних managed бота (Vasya, Masha) через @rm_curator_bot.
Переименовываем @test_wndr_agentbot → агент Рената.

## Действия

1. Создать @wndr_vasya_bot:
   - Открыть в Telegram: `t.me/newbot/rm_curator_bot/wndr_vasya_bot?name=Vasya+Agent`
   - Подтвердить создание
   - Получить токен: `getManagedBotToken(user_id=<bot_id>)`
   - Добавить в группу re-verse как админа (вручную)
   - Записать токен в .env как `AGENT_VASYA_TOKEN`

2. Создать @wndr_masha_bot:
   - Аналогично, ссылка: `t.me/newbot/rm_curator_bot/wndr_masha_bot?name=Masha+Agent`
   - Токен в .env как `AGENT_MASHA_TOKEN`

3. @test_wndr_agentbot — переименовать (setMyName) в "Renat Agent"
   - Токен уже есть: AGENT_ONE_BOT_TOKEN
   - В .env переименовать в AGENT_RENAT_TOKEN (или алиас)

4. Включить b2b для КАЖДОГО из трёх дочерних ботов в BotFather (вручную)
   - Зачем: если b2b только у родителя — только он видит чужие сообщения.
     Если у всех — каждый агент может реплаить каждого (нужно для фазы 2).
   - BotFather → выбрать бота → Bot Settings → Bot-to-Bot → Enable

## Критерии готовности

```bash
# Все 3 бота отвечают на getMe
python -c "
import asyncio
from telegram import Bot
import os
from dotenv import load_dotenv
load_dotenv()
async def check():
    for env in ['AGENT_RENAT_TOKEN', 'AGENT_VASYA_TOKEN', 'AGENT_MASHA_TOKEN']:
        bot = Bot(token=os.getenv(env))
        me = await bot.get_me()
        print(f'{env}: @{me.username} (id: {me.id})')
asyncio.run(check())
"
```

- [ ] 3 бота созданы и отвечают на getMe
- [ ] Все 3 добавлены в группу re-verse как админы
- [ ] b2b включён для КАЖДОГО дочернего бота (не только родителя)
- [ ] Токены записаны в .env
