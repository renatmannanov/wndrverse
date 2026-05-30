# Шаг 6: enrich + digest на боевых данных группы

> Зависит от: шаг 5 (в БД есть реальные сообщения от бота)
> Статус: [ ] pending

## Задача

Прогнать существующий пайплайн enrich (embeddings) → digest на данных, которые
бот реально накопил из группы (например, дать группе пожить ~час+ или накидать
достаточно сообщений вручную), и убедиться что realtime-данные проходят весь
путь так же, как файловые.

### ⚠️ СТОП-ТОЧКА: деньги на OpenAI
enrich тратит OpenAI API. **Порядок обязателен:**
1. Сначала оценка БЕЗ трат:
   ```bash
   python -m core.enrich.embedder --estimate
   ```
2. Показать пользователю оценку стоимости/числа фрагментов.
   **ВАЖНО:** `--estimate` считает ВЕСЬ unembedded-корпус
   (`count_unembedded_fragments()` НЕ фильтрует по `tgbot_%`). Если в БД остались
   неэмбеднутые файловые фрагменты — оценка покроет и их, не только группу.
   Явно сказать пользователю: «это оценка по всему unembedded, не только по
   ботовым данным; ботовых сейчас ~N штук (см. SQL ниже)».
   ```bash
   # сколько ИМЕННО ботовых ждут эмбеддинга (для контекста к оценке)
   docker compose exec db psql -U postgres -d wndrverse -c \
     "SELECT count(*) FROM fragments WHERE external_id LIKE 'tgbot_%' AND embedding IS NULL;"
   ```
3. **Дождаться явного «ок»** от пользователя.
4. Только потом реальный прогон.

### Прогон (после «ок»)
```bash
python -m core.enrich.embedder            # реальные embeddings (тратит OpenAI)
python -m delivery digest --topic <topic-группы> --period all
```

### Что проверяем
- embeddings проставились у ботовых фрагментов (embedding IS NOT NULL);
- digest по топику группы синтезируется и осмысленно ссылается на реальные
  сообщения;
- PII не утекла: в выводе digest имена локальные (решение 8 из community-brain-mvp
  держится — это и так так, проверяем что адаптер ничего не сломал).

## Команды для верификации

```bash
# оценка ПЕРЕД тратой
python -m core.enrich.embedder --estimate

# (после «ок») embeddings проставлены у ботовых фрагментов (юзер postgres)
docker compose exec db psql -U postgres -d wndrverse -c \
  "SELECT count(*) FROM fragments WHERE external_id LIKE 'tgbot_%' AND embedding IS NOT NULL;"

# digest по топику группы
python -m delivery digest --topic <topic> --period all
```

## Критерии готовности

- [ ] `--estimate` показан пользователю ДО трат, получено «ок».
- [ ] embeddings проставлены у ботовых фрагментов (count > 0 с embedding NOT NULL).
- [ ] digest по топику группы синтезируется без ошибок и опирается на реальные
      сообщения.
- [ ] PII-поведение не изменилось (имена локальные в выводе).
