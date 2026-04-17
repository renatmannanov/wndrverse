# Step 5: Написать test_stand.py — интерактивный оркестратор

> Статус: pending

## Что делаем

Скрипт из 3 фаз: фильтрация → b2b реплаи → куратор.
Человек генерирует ответы, скрипт постит от нужного бота.
Сразу постит в Telegram (без dry-run).

## Требования

### Общее

- Порядок агентов рандомизируется (`random.shuffle`) в КАЖДОЙ фазе
- Это имитирует независимые действия в разное время
- Каждый пост показывает имя бота-автора (@username)

### Фаза 1: Фильтрация источника

1. Загрузить members.json
2. Вызвать telegram-gather API для source_channel (одним запросом)
3. `random.shuffle(members)`
4. Для каждого участника:
   - Показать промпт (полностью) + сообщения из канала
   - Принять ввод от человека (или SKIP)
   - Постить от бота участника через `post_to_bus(text, bot_token)`
   - Сохранить `{member, bot, text, msg_id}` для фазы 2

### Фаза 2: b2b реплаи

1. Показать все Bus-посты с номерами и именем бота:
   ```
   BUS содержит:
     1. [@test_wndr_agentbot] [renat|tg] дочка написала промпт...
     2. [@wndr_masha_bot] [masha|tg] AI-курс для детей...
   ```
2. `random.shuffle(members)` — другой случайный порядок
3. Для каждого участника:
   - Показать ТОЛЬКО ЧУЖИЕ посты (скрыть свои)
   - Показать промпт агента
   - "Агент X (@bot) видит Bus. Реагирует? (номер поста или SKIP)"
   - Если да — выбрать номер, ввести текст реплая
   - Постить через `reply_in_bus(text, reply_to_message_id, bot_token)`

### Фаза 3: Куратор → Showcase

1. Показать Bus + реплаи (с авторами ботов)
2. Показать промпт куратора (полностью)
3. Принять ввод → постить через `post_to_showcase(text)`

### Логирование

Каждый прогон → файл `data/runs/{timestamp}.json`:

```json
{
  "timestamp": "2026-04-16T14:30:00",
  "source_channel": "iwacado",
  "source_messages_count": 15,
  "agent_order_phase1": ["Masha", "Renat", "Vasya"],
  "agent_order_phase2": ["Vasya", "Masha", "Renat"],
  "phase_1": [
    {"agent": "Renat", "bot": "@test_wndr_agentbot", "action": "post", "text": "...", "message_id": 123},
    {"agent": "Vasya", "bot": "@wndr_vasya_bot", "action": "skip"}
  ],
  "phase_2": [
    {"agent": "Masha", "bot": "@wndr_masha_bot", "reply_to": 123, "reply_to_agent": "Renat", "text": "..."}
  ],
  "phase_3": {
    "showcase_text": "..."
  }
}
```

## Зависимости

- Шаг 1 (боты), Шаг 2 (members.json), Шаг 3 (промпты), Шаг 4 (bus.py)

## Критерии готовности

- [ ] Скрипт читает members.json
- [ ] telegram-gather API вызывается (1 запрос)
- [ ] Порядок агентов рандомизируется в каждой фазе
- [ ] Каждый агент постит от своего бота
- [ ] В фазе 2 — агент видит только ЧУЖИЕ посты с именем бота-автора
- [ ] Реплаи работают (reply_to корректный)
- [ ] Showcase-пост публикуется
- [ ] Лог прогона сохраняется в data/runs/
