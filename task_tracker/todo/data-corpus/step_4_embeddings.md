# Шаг 4: Эмбеддинги на дельте

> Зависит от: шаг 3 (новый корпус залит)
> Статус: [ ] pending

## Задача

Прогнать эмбеддинги на фрагментах без эмбеддинга (`embedding IS NULL`) — это новые
сообщения и новые топики из шага 3. Старые мигрированные (шаг 2) эмбеддинги уже
имеют, повторно не платим. ⚠️ Трата OpenAI — стоп-точка `--estimate` обязательна.

### Зачем (и почему НЕ блокер для дайджеста)
Дайджест-синтез эмбеддинги НЕ использует (Pass1 — текстовый отбор LLM). Эмбеддинги
нужны для near-dedup (`find_near_duplicates`) и будущего векторного поиска. Делаем,
чтобы корпус был полным перед дампом на прод (план B).

### ⚠️ СТОП-ТОЧКА: деньги
```bash
python -m core.enrich.embedder --estimate
# покажет: N unembedded, ~chars, ~tokens, ~$X (text-embedding-3-small, дёшево)
```
`--estimate` считает весь unembedded-корпус = ровно дельта из шага 3 (старые уже
эмбеджены после миграции). Сообщить пользователю оценку, дождаться «ок». ТОЛЬКО ПОТОМ:
```bash
python -m core.enrich.embedder
```

## Тесты

Юнит-тестов нет (реальная трата API). Проверка — count embedded.

## Команды для верификации

```bash
python -m core.enrich.embedder --estimate     # оценка (без трат)
# ... после «ок»:
python -m core.enrich.embedder                # реальный прогон

docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) FILTER (WHERE embedding IS NULL) AS unembedded FROM fragments;"
# ожидаем: 0
```

## Критерии готовности

- [ ] `--estimate` показан пользователю, «ок» получено ДО реального прогона.
- [ ] `python -m core.enrich.embedder` отработал.
- [ ] `embedding IS NULL` по всему корпусу = 0.
