# prod-deploy

> Статус: pending (ЗАБЛОКИРОВАН до завершения data-corpus)
> Дата: 2026-06-01
> Тип: инфраструктура (деплой на VPS)
> Ветка: feature/prod-deploy (от ветки data-corpus, после её влития)

## Цель

Вывести community-brain в продакшн на VPS Hetzner: развернуть БД, перенести готовый
корпус дампом из локальной БД (результат плана `data-corpus`), запустить бота-
ингестора и дайджест-шедулер как systemd-сервисы/таймеры, прогнать реальный WNDR-
дайджест и показать заказчику. Код дедупа уже исправлен в `data-corpus` — здесь
только инфраструктура.

## Зависимость

⚠️ **Этот план ЗАВИСИТ от `data-corpus`.** Делать ТОЛЬКО после того, как data-corpus
= done (код дедупа влит, локальный корпус чистый и единообразный, дамп готов).
Не начинать раньше.

## Зафиксированные решения (НЕ обсуждаются в ходе работы)

1. **Инфра — всё на одном VPS Hetzner** (`rm_agent@62.238.31.95`, см. CLAUDE.md).
   Бот, шедулер, postgres+pgvector — там же. Изолировано от OpenClaw/Hermes.
   НЕ трогать `~/.openclaw/ ~/.hermes/ ~/.codex/ ~/.claude/`.
2. **Корпус на прод = ДАМП локальной БД** (pg_dump → restore). Решение пользователя.
   Без повторного Telethon-парсинга и без повторных трат на эмбеддинги — корпус
   идентичен локальному. PII (имена) едет на VPS в БД — осознанно (свой сервер,
   имена нужны для humanize на выходе).
3. **Шедулер на проде — systemd-timer** (НЕ sleep-loop). Timer дёргает
   `python -m digest.scheduler --now` раз в день, `Persistent=true` (переживает
   ребут, не пропускает).
4. **Эмбеддинг на проде — systemd-timer** на `core.enrich.embedder`, раз в N часов,
   батч по `embedding IS NULL`. Бот пишет быстро без трат, embedder догоняет дёшево.
5. **Дайджест-топики на проде:** сначала `questions_to_women,questions_to_men`
   (`WNDR_DIGEST_TOPICS`), после прод-тестов → расширить на все топики (правка ENV,
   код НЕ меняем). Решение пользователя.
6. **Где живёт core на VPS — РЕШИТЬ в step_1.** Deploy-карта (CLAUDE.md) деплоит
   `wndrverse_agent_claude`; bot/digest/core — в репо `wndrverse`. Каталог на VPS в
   карте НЕ зафиксирован. Предложение: `~/claude-hub/projects/wndrverse`.
7. **Секреты на VPS — вручную, значения в план/git НЕ писать.** `.env`,
   `topic_map.json` gitignored, заводятся на VPS отдельно.
8. **PII не ломаем.** В OpenAI только `[#id]`+текст; имена локально. Не менять.

## Шаги

| # | Файл | Статус |
|---|------|--------|
| 1 | step_1_vps_db_and_corpus.md  | [ ] |
| 2 | step_2_bot_service.md        | [ ] |
| 3 | step_3_scheduler_timers.md   | [ ] |
| 4 | step_4_prod_smoke_handoff.md | [ ] |
| 5 | step_5_completion.md         | [ ] |

## Критерии готовности

- [ ] postgres+pgvector на VPS; корпус восстановлен из дампа (count совпадает с
      локальной БД; `dup_keys`=0, `unembedded`=0).
- [ ] Бот-ингестор = systemd-сервис (`systemctl status` active), ловит новые WNDR
      сообщения (count растёт).
- [ ] Дайджест-шедулер = systemd-timer (`Persistent=true`); embedder-timer тоже.
      `systemctl list-timers` показывает оба.
- [ ] Прод-smoke: реальный WNDR-дайджест по `questions_to_*` доставлен в ЛС;
      PII локальная; длина в норме.
- [ ] CLAUDE.md: каталог core на VPS, systemd-юниты, deploy-команды.
- [ ] Существующие сервисы VPS (OpenClaw/Hermes) не затронуты.

## Что НЕ в этой задаче (защита от scope creep)

- ❌ Правка дедупа, backfill, миграция, первичные эмбеддинги — план `data-corpus`.
- ❌ Регулярный Telethon на проде (корпус дампом; новое ловит бот).
- ❌ Триггер дайджеста по накоплению (бэклог `digest-trigger-by-context.md`).
- ❌ Доставка в топик группы (только ЛС). CI/CD, мониторинг, алерты.

## Открытые вопросы (решить ДО соответствующего шага)

- **step_1:** каталог core-пайплайна на VPS (решение 6) — выбрать, записать.
- **step_2:** privacy mode OFF у бота — подтвердить в @BotFather. Бот в WNDR chat —
  ГОТОВО (подтверждено пользователем 2026-06-01).
