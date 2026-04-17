# WNDRverse MVP — Agent Network

> Статус: done
> Дата: 2026-04-11 → 2026-04-16
> Тип: фича (MVP)

## Цель

Запустить сеть агентов на базе Telegram: инфраструктура, промпты, Managed Bots, Bot-to-Bot.

## Результат

Инфраструктура готова. Telegram Managed Bots и Bot-to-Bot протестированы и работают.
Автоматизация через Claude API — перенесена в следующий план (test-stand).

## Что сделано

- [x] Супергруппа "re-verse" с 2 топиками (Bus + Showcase)
- [x] telegram-gather API работает (curator/reader.py)
- [x] Промпты агентов написаны (curator/prompts/agent_one.md, agent_two.md, curator.md)
- [x] bus.py и showcase.py написаны
- [x] Managed Bots: @rm_curator_bot (родитель) создаёт @test_wndr_agentbot (дочерний)
- [x] getManagedBotToken работает (параметр `user_id`, не `bot_id`)
- [x] Дочерний бот постит в Bus от своего имени
- [x] Bot-to-Bot: родитель видит сообщения дочернего, реплаит
- [x] ARCHITECTURE.md обновлён: Managed Bots, Bot-to-Bot, mode managed/custom
- [x] sources.json — каналы Рената по категориям

## Что НЕ сделано — перенесено в следующий план

- [ ] agents.py — Claude API фильтрация (перенесено → test-stand, фаза 2)
- [ ] main.py — полный автоцикл (перенесено → test-stand, фаза 2)
- [ ] members.json — участники с mode managed/custom (перенесено → test-stand)
- [ ] Loop guard — защита от b2b петель (перенесено → test-stand)
- [ ] End-to-end автотест (перенесено → test-stand, фаза 2)

## Ключевые learnings

- `getManagedBotToken` принимает `user_id`, не `bot_id`
- Токен возвращается напрямую в `result` (строка), не `result.token`
- Дочернего бота нужно вручную добавить в группу как админа — API не позволяет
- b2b mode / Bot Management Mode включаются только через BotFather, нет API
- Для b2b достаточно включить mode у одного бота из пары (родителя)
- Ссылка `t.me/newbot/...` — deep link, работает только из Telegram-клиента

## Шаги (финальный статус)

| # | Файл | Статус |
|---|------|--------|
| 1 | step_1_infra.md | [x] done |
| 2 | step_2_reader.md | [x] done |
| 3 | step_3_agents.md | перенесён → test-stand |
| 4 | step_4_curator.md | перенесён → test-stand |
| 5 | step_5_test.md | перенесён → test-stand |
| 7 | step_7_managed_bots.md | [x] done |
| 8 | step_8_bot_to_bot.md | [x] done (loop guard → test-stand) |
| 6 | step_6_completion.md | [x] done |
