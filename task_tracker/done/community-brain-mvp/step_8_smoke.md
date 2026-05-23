# Шаг 8: Smoke — end-to-end на реальных данных

> Зависит от: шаги 1-7
> Статус: [ ] pending

## Задача

Прогнать весь пайплайн на реальной выгрузке WNDR и **глазами** оценить качество
дайджеста. Это главная проверка MVP — синтез на 30k сообщений в offerings либо
работает осмысленно, либо нет. Тесты этого не покажут — нужен живой прогон.

### Полный прогон end-to-end

1. Чистая БД — **СТОП, спросить пользователя перед `down -v`**. Флаг `-v` безвозвратно
   удаляет том БД со всеми embeddings (это часы работы и деньги на API, если enrich уже
   был). Сценарии:
   - Первый прогон / БД пустая → можно `docker compose down -v && docker compose up -d db && python -m core.db init`.
   - **Если embeddings уже посчитаны** (повтор smoke после правки) → НЕ делать `down -v`.
     Ingest идемпотентен (external_id), просто пере-ингестировать новое и продолжить.
     Сбрасывать том — только по явному «ок» пользователя.
2. Ingest всех топиков: `python -m core.ingest.loaders --dir "$WNDR_EXPORTS_DIR"`
3. Оценка стоимости: `python -m core.enrich.embedder --estimate` — ПОКАЗАТЬ пользователю,
   дождаться «ок» (трата денег на API).
4. Enrich: `python -m core.enrich.embedder` — дождаться завершения.
5. Дайджесты по 3 разным по смыслу топикам:
   - `python -m delivery digest --topic offerings --period all`
   - `python -m delivery digest --topic harvest --period all`
   - `python -m delivery digest --topic requests --period all`

### Что оценить глазами (записать вывод в progress.md)

- **Дайджест опирается на реальные сообщения** — есть ссылки [автор/#id], а не
  выдуманное общими словами.
- **Семантика топика отражена** — harvest звучит как «итоги», requests как
  «что людям нужно», offerings как «что предлагают». Не одинаковый шаблон.
- **Отбор (Pass 1) не теряет важное** — проверить вручную: взять 2-3 заметных
  оффера из offerings, посмотреть попали ли похожие темы в дайджест.
- **Нет галлюцинаций** — имена/факты в дайджесте есть в исходных сообщениях.

Если качество слабое — зафиксировать ЧТО именно плохо (отбор? промпт? длина?),
это вход для итерации промпта (правим `core/prompts/digest_synthesis.md`).

## Команды для верификации

(см. полный прогон выше — это и есть проверка)

```bash
docker compose exec db psql -U postgres -d wndrverse -c "SELECT topic, count(*) FROM fragments GROUP BY topic ORDER BY 2 DESC;"
docker compose exec db psql -U postgres -d wndrverse -c "SELECT count(*) FROM artifacts;"   # дайджесты сохранились
```

## Критерии готовности

- [ ] Полный прогон (down -v → init → ingest → enrich → digest) проходит без ошибок
- [ ] Все 10 топиков загружены (count по topic > 0 для каждого ожидаемого)
- [ ] Стоимость embeddings зафиксирована в progress.md
- [ ] 3 дайджеста (offerings/harvest/requests) сгенерированы и сохранены в artifacts
- [ ] Дайджесты оценены глазами, вывод оценки записан в progress.md
- [ ] Подтверждено: дайджест опирается на реальные сообщения, без галлюцинаций
