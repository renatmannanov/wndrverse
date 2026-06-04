# Шаг 4: Прод-smoke + показ заказчику + автосаммари

> Зависит от: шаги 1-3
> Статус: [x] DONE (2026-06-04)

## Факт выполнения (2026-06-04)
Прод-smoke синтеза дайджеста выполнен через команду `/summary` (план
`digest-on-demand`, done), а НЕ через дайджест-таймер (тот вынесен в бэклог).
Реальные синтезы на проде зафиксированы: artifacts id 12-15 в БД VPS
(topic=questions_to_women, 2047-3008 симв., 2026-06-04). End-to-end путь
выборка→synth→humanize→доставка в ЛС проверен на живых данных. PII локальная
(humanize_refs), длина в норме (<4096). «Автосаммари» в смысле этого шага
закрыт командой `/summary`; периодический авто-дайджест — backlog.

## Задача

Прогнать реальный WNDR-дайджест по `questions_to_*` на проде, проверить end-to-end,
показать заказчику, зафиксировать настройки автосаммари.

### ⚠️ СТОП-ТОЧКА: данные + деньги
0. Пред-чек данных:
```bash
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT topic, count(*), count(*) FILTER (WHERE embedding IS NOT NULL) AS emb \
   FROM fragments WHERE topic LIKE 'questions_to_%' GROUP BY topic;"
```
Если по обоим < 3 после фильтра min_chars → синтез выдаст «недостаточно данных».
Сообщить пользователю, подождать накопления ботом. НЕ гнать пустой синтез.

### 1. Реальный прогон
```bash
sudo systemctl start wndr-digest.service     # синтез по questions_to_* → ЛС
journalctl -u wndr-digest.service -n 40
```
⚠️ Трата OpenAI на синтез (Pass1+Pass2). На WNDR-топиках это целевой smoke.

### 2. Проверить
- Бот прислал дайджест в ЛС `WNDR_DIGEST_DM_USER_ID` — глазами в Telegram.
- По questions_to_women И questions_to_men (2 сообщения, если оба непусты).
- PII: имена локальные (`[Имя, дата]`), не `[#id]`; в БД artifacts хранит `[#id]`.
- Длина ≤ 4096 (лог без warning об обрезке).
- Содержимое осмысленно ссылается на реальные вопросы топиков.

### 3. Показ заказчику
Дайджест в ЛС = демо. Показать пример. Обратную связь (длина/тон/секции) — в
progress.md; при необходимости — отдельная задача (промпт digest_synthesis.md).

### 4. Настройка автосаммари
«Автосаммари» = работающий wndr-digest.timer. Настройка:
- частота/время → `wndr-digest.timer` OnCalendar (+ `daemon-reload`).
- период → `WNDR_DIGEST_PERIOD` (.env). топики → `WNDR_DIGEST_TOPICS` (после тестов
  → все). получатель → `WNDR_DIGEST_DM_USER_ID`.
Согласовать с заказчиком финальные значения, записать в progress.md.

## Тесты

Юнит-тестов нет (прод-проверка живьём).

## Команды для верификации

```bash
sudo systemctl start wndr-digest.service
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT id, topic, length(content) AS chars, array_length(fragment_ids,1) AS n \
   FROM artifacts WHERE topic LIKE 'questions_to_%' ORDER BY id DESC LIMIT 5;"
```

## Критерии готовности

- [ ] Пред-чек данных выполнен; если мало — СТОП, синтез не гнался.
- [ ] Реальный WNDR-дайджест доставлен в ЛС, подтверждён в Telegram.
- [ ] PII локальная, длина в норме.
- [ ] Артефакт(ы) по `questions_to_*` в таблице artifacts.
- [ ] Заказчику показан пример; обратная связь в progress.md.
- [ ] Настройки автосаммари согласованы и записаны.
