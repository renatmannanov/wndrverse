# Шаг 5: Enrich — embeddings батчами + дедуп + язык

> Зависит от: шаг 2 (store), шаг 3 (llm), шаг 4 (ingest даёт данные)
> Статус: [ ] pending

## Задача

Проставить embeddings всем загруженным фрагментам. Перенос
`03_ayda_think/services/normalizer_service.py` с двумя улучшениями под наш объём
(~150k vs сотни заметок у ayda).

1. `core/enrich/embedder.py` — перенести логику normalizer:
   - `normalize_all(batch_size=100)` — цикл по unembedded батчами, коммит после
     каждого батча (докачка после сбоя; ayda уже так делает).
   - `_generate_embeddings` → использовать `core.llm.client.embed` (НЕ прямой
     OpenAI вызов из transcription_service).
   - `_detect_language` — перенести как есть (cyrillic ratio, без API).
   - `_check_duplicates` — перенести как есть (find_near_duplicates threshold 0.95).

2. Улучшение под объём:
   - **Прогресс**: логировать `processed / total` каждые N батчей (видеть что не завис).
   - **Оценка стоимости перед запуском**: добавить `--estimate` режим — посчитать
     число unembedded фрагментов и суммарные символы, вывести грубую оценку
     стоимости (text-embedding-3-small: $0.02 / 1M токенов, ~4 символа = 1 токен).
     Это разовый прогон на 150k — надо знать цену заранее.

3. CLI: `python -m core.enrich.embedder [--estimate]`.

**СТОП — деньги на API.** Реальный прогон embeddings тратит деньги (OpenAI). Порядок
обязателен: сначала `--estimate`, ПОКАЗАТЬ оценку пользователю, ДОЖДАТЬСЯ явного «ок»,
и только потом запускать реальный прогон. Не запускать реальный embedder автоматически
сразу после estimate. (Правило глобального CLAUDE.md: рискованные операции — дождись подтверждения.)

**Обезличивание (PII):** в `_generate_embeddings` уходит ТОЛЬКО `text` фрагмента.
Имена/username/sender_name в OpenAI НЕ передаются (они остаются в БД). Это уже так в
коде ayda (embed берёт `f['text']`), но зафиксировать: не добавлять author_name в
эмбеддируемый текст.

## Тесты

- На малом наборе (после ingest только intro): запустить, проверить что
  `embedding IS NULL` count → 0, есть фрагменты с `language='ru'`.

## Команды для верификации

```bash
python -m core.enrich.embedder --estimate     # печатает кол-во и оценку $$ , НЕ тратит API
python -m core.enrich.embedder                 # реальный прогон
docker compose exec db psql -U postgres -d wndrverse -c "SELECT count(*) FROM fragments WHERE embedding IS NULL AND is_duplicate IS NOT TRUE;"   # 0
docker compose exec db psql -U postgres -d wndrverse -c "SELECT language, count(*) FROM fragments GROUP BY language;"
docker compose exec db psql -U postgres -d wndrverse -c "SELECT count(*) FROM fragments WHERE is_duplicate;"   # дубликаты помечены
```

## Критерии готовности

- [ ] `--estimate` печатает число unembedded и оценку стоимости, БЕЗ вызова API
- [ ] После прогона `embedding IS NULL` (среди не-дубликатов) = 0
- [ ] `language` проставлен (есть строки 'ru')
- [ ] Дубликаты помечены `is_duplicate=true`
- [ ] embed идёт через `core.llm.client`, не через прямой OpenAI/transcription_service
- [ ] Прогресс логируется (видно processed/total)
