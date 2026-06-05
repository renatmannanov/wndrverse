# Step 1: Выгрузка 11 топиков локально

> Статус: pending

Telethon userbot живёт ТОЛЬКО локально (`C:\Users\renat\projects\telegram-gather\`),
на VPS его нет. Сессия привязана к локальному IP — не тащим на VPS.

## Команды

Для каждого из 11 топиков (cwd = telegram-gather):

```powershell
cd C:\Users\renat\projects\telegram-gather
python fetch_topic.py "WNDR chat" --topic-id <ID> --name <key> --limit 700 -o data/exports/wndr_backfill
```

| key           | --topic-id |
|---------------|-----------|
| requests      | 68        |
| boltalka      | 1         |
| announcements | 70        |
| offerings     | 2262      |
| daily         | 13004     |
| harvest       | 14279     |
| quotes        | 11820     |
| intro         | 12003     |
| commits       | 13002     |
| together      | 11002     |
| sales         | 8718      |

fetch_topic.py сам ставит utf-8 на win32 (строки 17-19). Между топиками скрипт сам
спит 0.3с каждые 200 сообщений (флуд-контроль Telethon).

## Критерий готовности

- В `data/exports/wndr_backfill/` лежат 11 файлов `wndr_topic_<key>.json`.
- Проверка количества: `(Get-ChildItem data/exports/wndr_backfill/*.json).Count` == 11.
- **Валидация каждого JSON** (chat_id обязан совпасть байт-в-байт, иначе дедуп
  промахнётся и будут невидимые двойники):

```powershell
Get-ChildItem data/exports/wndr_backfill/*.json | ForEach-Object {
  $j = Get-Content $_ -Raw | ConvertFrom-Json
  "{0,-16} chat_id={1} total={2}" -f $j.topic_name, $j.chat_id, $j.total_messages
}
# ОЖИДАЕМ: chat_id = -1002924475859 у ВСЕХ 11; total_messages > 0 у всех
```

- ⚠️ **boltalka особый случай:** topic-id 1 = "General" топик форума. Telethon с
  `reply_to=1` может вернуть ПУСТОЙ итератор → `total_messages = 0`. Если так —
  boltalka не выгрузился, нужен другой способ достать его thread_id (не блокирует
  остальные 10; обработать отдельно).
