# Шаг 5: Smoke — разовая доставка дайджеста в ЛС

> Зависит от: шаги 1-4
> Статус: [ ] pending

## Задача

Проверить весь путь end-to-end: разовый прогон (`--now`) синтезирует дайджест по
топику WNDR и реально доставляет его в личку пользователю.

### Предусловия (делает пользователь, не агент)
- Бот-ингестор добавлен в WNDR chat и собрал сообщения из топиков 16139/16138
  (есть фрагменты в БД с `topic IN ('questions_to_women','questions_to_men')`).
- Пользователь написал боту `/start` в ЛС (Telegram не даёт боту писать первым).
- `.env`: `BOT_TOKEN_INGEST` задан, `WNDR_DIGEST_DM_USER_ID=423915315`.

### ⚠️ СТОП-ТОЧКА: деньги на OpenAI
Синтез тратит OpenAI (Pass 2, при многих фрагментах ещё Pass 1). Порядок:

0. **Пред-чек наличия данных (V2) — БЕЗ него не идти дальше.**
   ```bash
   docker compose exec db psql -U postgres -d wndrverse -c \
     "SELECT topic, count(*), count(*) FILTER (WHERE embedding IS NOT NULL) AS embedded \
      FROM fragments WHERE topic IN ('questions_to_women','questions_to_men') GROUP BY topic;"
   ```
   - Если по обоим топикам **0 строк** → **СТОП**. Бот ещё не собрал сообщения из
     WNDR-топиков. Сообщить пользователю «нет данных, синтез не запускаю» и НЕ
     тратить OpenAI. Дальше идти НЕЛЬЗЯ (guard в коде это тоже отловит, но деньги
     на estimate/синтез не тратим зря и не гоняем впустую).
   - Если данные есть — продолжать.

1. Если есть неэмбедженные (`embedded` < `count`) — оценка перед тратой:
   ```bash
   python -m core.enrich.embedder --estimate
   ```
   **ВАЖНО (V3):** `--estimate` считает ВЕСЬ unembedded-корпус, не только WNDR.
   Сначала показать пользователю, сколько ИМЕННО WNDR-фрагментов без эмбеддинга:
   ```bash
   docker compose exec db psql -U postgres -d wndrverse -c \
     "SELECT count(*) FROM fragments \
      WHERE topic LIKE 'questions_to_%' AND embedding IS NULL;"
   ```
   Явно сказать: «estimate покрывает весь unembedded-корпус (~N всего), из них
   WNDR-топиков ~M; остальное — другие топики». Дождаться явного «ок», затем
   `python -m core.enrich.embedder`.
2. Только после этого — реальный прогон дайджеста (ещё трата на синтез).

### Прогон (после «ок»)
```bash
docker compose up -d db
python -m digest.scheduler --now    # синтез по обоим топикам → доставка в ЛС
```
Проверить:
- бот прислал в личку 2 сообщения (по одному на топик) — глазами в Telegram;
- длина каждого ≤ 4096 (не обрезалось с warning — смотри лог; если обрезалось,
  значит шаг 3 не удержал, зафиксировать в Learnings);
- имена в тексте локальные (PII держится), `[#id]` заменены на `[Имя, дата]`;
- содержимое осмысленно ссылается на реальные сообщения топика.

> Примечание: topic_map грузится в память при старте. Бот-ингестор и scheduler —
> разные процессы; на конфиг влияет только то, что scheduler читает при старте.

## Команды для верификации

```bash
# данные по топикам в БД
docker compose exec db psql -U postgres -d wndrverse -c \
  "SELECT topic, count(*) FROM fragments WHERE topic LIKE 'questions_to_%' GROUP BY topic;"

# разовый прогон (после стоп-точки)
python -m digest.scheduler --now

# артефакт дайджеста сохранён
docker compose exec db psql -U postgres -d wndrverse -c \
  "SELECT id, topic, left(content,50), array_length(fragment_ids,1) AS n_frags \
   FROM artifacts ORDER BY id DESC LIMIT 5;"
```

## Критерии готовности

- [ ] Пред-чек count по топикам выполнен; если 0 данных — СТОП, синтез не запущен.
- [ ] `--estimate` показан до трат (если были неэмбедженные), пользователю явно
      сказано сколько именно WNDR-фрагментов vs весь корпус, получено «ок».
- [ ] `python -m digest.scheduler --now` прислал дайджест(ы) в ЛС `423915315`
      (подтверждено в Telegram).
- [ ] Длина в норме (≤4096; если обрезка сработала — отмечено в Learnings).
- [ ] PII: имена локальные, `[#id]` → `[Имя, дата]`.
- [ ] Артефакт(ы) дайджеста в таблице `artifacts`.
