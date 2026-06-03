# Шаг 3: Backfill всех топиков WNDR через Telethon

> Зависит от: шаг 1 (единый ключ), шаг 2 (старые мигрированы)
> Статус: [ ] pending

## Задача

Снять историю ВСЕХ топиков WNDR chat через Telethon (`telegram-gather`), залить в
локальную БД. Новый backfill старых топиков (offerings/boltalka/…) схлопнётся с
мигрированными старыми (шаг 2) — обновит/добавит, без дублей. Новые топики
(questions_to_*) добавятся с нуля.

### 0. Список всех topic_id
```bash
cd ~/projects/telegram-gather
python fetch_topics_list.py "WNDR chat"
# покажет: topic_id, name, message_count, link для каждого топика
```
Выписать ВСЕ topic_id + соответствие topic_id → имя (наш ключ-топик). Записать
соответствие в progress.md. Особо: топики «Вопросы к Женскому/Мужскому миру» →
их topic_id (может ≠ thread_id 16139/16138 из ссылок — использовать то, что вернул
Telethon для парсинга; thread_id 16139/16138 — для topic_map/бота).

### 1. Маппинг topic_id → наш ключ-топик + cross-check с topic_map (V7)
Наши ключи (из `TOPIC_HINTS` + новые): offerings, requests, intro, daily, boltalka,
harvest, commits, announcements, together, sales, questions_to_women,
questions_to_men. Сопоставить каждому реальный topic_id из шага 0.

**Cross-check для вопросов:** в `core/ingest/topic_map.json` thread_id 16139 →
questions_to_women, 16138 → questions_to_men (это thread_id для БОТА). Telethon
topic_id может ≠ thread_id. Зафиксировать в progress.md ОБА: Telethon topic_id (для
парсинга этого шага) И thread_id (для бота/topic_map). Если для вопросов Telethon
topic_id СОВПАДАЕТ с 16139/16138 — отметить «совпадает»; если нет — записать оба
значения явно, чтобы бот (план B) и backfill не разъехались по топику.

### 2. GATE: сначала ОДИН топик, проверить chat_id, потом остальные (K4)
Сперва снять ОДИН топик и убедиться, что правка шага 1 применилась (в JSON есть
`chat_id`). Если нет — СТОП, иначе весь backfill пойдёт по legacy-ключу `wndr_…` и
задвоит корпус.
```bash
cd ~/projects/telegram-gather
# (a) пробный — один топик:
python fetch_topic.py "WNDR chat" --topic-id <ID_offerings> --output data/exports/wndr --name offerings
# (b) проверить chat_id в этом JSON:
python -c "import json; print(json.load(open('data/exports/wndr/wndr_topic_offerings.json', encoding='utf-8')).get('chat_id'))"
# ОБЯЗАТЕЛЬНО: -1002924475859 (НЕ None, НЕ положительный 2924475859).
# Если None → шаг 1 (fetch_topic.py) не применён/не закоммичен → СТОП.
```
Только ПОСЛЕ успешной проверки (a)+(b) — снять ОСТАЛЬНЫЕ топики:
```bash
# по списку (topic_id, name) из шага 1 — для каждого оставшегося топика:
python fetch_topic.py "WNDR chat" --topic-id <ID> --output data/exports/wndr --name <topic_key>
```
Финальная проверка chat_id у ВСЕХ экспортов:
```bash
python -c "import json,glob; [print(f, json.load(open(f,encoding='utf-8')).get('chat_id')) for f in glob.glob('data/exports/wndr/wndr_topic_*.json')]"
# ожидаем у ВСЕХ: -1002924475859
```

### 3. Залить в локальную БД
Зафиксировано: скопировать JSON в `wndrverse/data/exports/wndr/`, грузить оттуда
(единый путь, без неоднозначности).
```bash
# скопировать экспорты в каталог wndrverse:
cp ~/projects/telegram-gather/data/exports/wndr/wndr_topic_*.json \
   ~/projects/wndrverse/data/exports/wndr/
cd ~/projects/wndrverse
python -m core.ingest.loaders --dir data/exports/wndr
```
`data/` gitignored — сообщения в git не попадают.

### Заметка про дедуп на этом шаге
Старые топики уже в БД с ключом `tg_-1002924475859_{id}` (после шага 2). Новый
backfill тех же сообщений даст ТОТ ЖЕ ключ → дедуп пропустит (duplicates_skipped).
Новые сообщения (которых не было) и новые топики — добавятся. Так корпус становится
полным и актуальным без дублей.

## Тесты

Юнит-тестов нет (реальные данные). Проверка — count по топикам + отсутствие дублей.

## Команды для верификации

```bash
# все топики представлены, count разумный:
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT topic, count(*) FROM fragments GROUP BY topic ORDER BY count(*) DESC;"
# вопросы появились:
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT topic, count(*) FROM fragments WHERE topic LIKE 'questions_to_%' GROUP BY topic;"
# дублей ключа нет:
docker compose exec -T db psql -U postgres -d wndrverse -c \
  "SELECT count(*) - count(DISTINCT external_id) AS dup_keys FROM fragments;"
# ожидаем: 0
```

## Критерии готовности

- [ ] Список всех topic_id получен (`fetch_topics_list.py`), соответствие
      topic_id↔ключ-топик в progress.md; для вопросов зафиксированы И Telethon
      topic_id, И thread_id 16139/16138 (cross-check V7).
- [ ] GATE пройден: пробный 1 топик дал `chat_id = -1002924475859` в JSON ДО парсинга
      остальных (K4).
- [ ] Все топики WNDR залиты; questions_to_women/men count > 0.
- [ ] JSON-экспорты содержат `chat_id = -1002924475859` (проверены ВСЕ).
- [ ] `dup_keys` = 0 (новый backfill схлопнулся со старыми, не задвоил).
