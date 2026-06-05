# Промпт для другого окна: добор пропущенных сообщений WNDR (3 июня → сегодня)

> Самодостаточный. Другое окно НЕ знает контекст текущего — здесь всё, что нужно.
> Создан 2026-06-05 из окна, где доделывали дайджест-пайплайн wndrverse.

## Что случилось (проблема)

Realtime ingest-бот wndrverse (`~/wndrverse` на VPS, `-m bot.ingest_bot`) пишет в
БД только сообщения из топиков, прописанных в `core/ingest/topic_map.json`. Там
прописаны **только 2 топика** (`questions_to_women` thread 16139,
`questions_to_men` thread 16138). Все остальные форум-топики группы бот **молча
пропускает** (`skip: no topic for chat=… thread=…` — за 3 дня ~114 пропусков).

Итог: с момента последнего исторического экспорта (**2026-06-03**) realtime
накопил только 2 топика. Остальные 11 топиков «застыли» на 3 июня. Нужно **добрать
сообщения, появившиеся в этих топиках с ~3 июня по сегодня**.

⚠️ Polling-бот прошлое НЕ заберёт (Telegram отдаёт по polling только новое) —
поэтому добор делается ОТДЕЛЬНО, через telegram-gather (Telethon userbot).

## Где что лежит

- **telegram-gather**: `C:\Users\renat\projects\telegram-gather\` (Telethon userbot,
  своя Telethon-сессия в `config.py`). Скрипт выгрузки топика:
  `fetch_topic.py "WNDR chat" --topic-id <ID> --output data/exports/wndr --name <key>`.
  ⚠️ Фильтра по дате у `fetch_topic.py` НЕТ (только `--limit`). Это НЕ проблема —
  см. «Дедуп» ниже: выгружаем топик (целиком или `--limit` последних), а заливка
  в БД сама отбросит уже существующие строки.
- **wndrverse БД + loader**: `~/wndrverse` на VPS `rm_agent@62.238.31.95`
  (ssh `-i ~/.ssh/openclaw_hetzner`), postgres+pgvector в docker на :5434.
  Заливка экспортов: `python -m core.ingest.loaders --dir <exports_dir>` (или env
  `WNDR_EXPORTS_DIR`). Тот же funnel, что у бота.

## Дедуп (почему добор безопасен)

`external_id = tg_{chat_id}_{msg_id}` — единый ключ для file-loader и realtime-бота.
Заливка делает per-row SELECT по external_id и пропускает дубли. Поэтому можно
выгрузить топик целиком и залить — повторно появившиеся сообщения дедупнутся, в БД
добавятся ТОЛЬКО новые (после 3 июня). chat_id для WNDR = **-1002924475859**.

## Маппинг topic_id → ключ (из прошлых экспортов, проверено)

chat: `"WNDR chat"` (chat_id -1002924475859). Прошлый экспорт: `exported_at 2026-06-03`.

| key (для --name и topic в БД) | --topic-id | последнее в БД (докуда есть) |
|------------------------------|-----------|------------------------------|
| boltalka                     | 1         | 2026-06-03 14:21 |
| offerings                    | 2262      | 2026-06-03 13:48 |
| daily                        | 13004     | 2026-06-03 11:44 |
| requests                     | 68        | 2026-06-03 14:31 |
| intro                        | 12003     | 2026-05-30 11:05 |
| commits                      | 13002     | 2026-05-27 19:23 |
| harvest                      | 14279     | 2026-06-02 13:34 |
| sales                        | 8718      | 2026-04-11 18:29 |
| announcements                | 70        | 2026-06-03 14:14 |
| quotes                       | 11820     | 2026-06-02 08:20 |
| together                     | 11002     | 2026-04-13 08:14 |
| questions_to_men             | 16138     | 2026-06-04 19:33 (realtime жив) |
| questions_to_women           | 16139     | 2026-06-05 10:14 (realtime жив) |

questions_to_* добирать НЕ обязательно (realtime их пишет), но повторный прогон не
навредит (дедуп). Приоритет — 11 «застывших» топиков.

## Задача (шаги)

1. В `telegram-gather` для каждого из 11 застывших топиков выгрузить свежие
   сообщения:
   `python fetch_topic.py "WNDR chat" --topic-id <ID> --output data/exports/wndr_backfill --name <key>`
   (можно `--limit 500` чтобы не тянуть всю историю — нужны только последние пару
   недель; если не уверен — без лимита, дедуп всё равно отсечёт старое).
   ⚠️ Скрипт пишет на win32 в utf-8 (уже настроено в самом fetch_topic.py).
2. Перенести `data/exports/wndr_backfill/` на VPS в `~/wndrverse` (scp), либо
   запускать loader локально против VPS-БД, если есть доступ к :5434.
   Рекомендуется на VPS: scp каталог, затем
   `cd ~/wndrverse && python -m core.ingest.loaders --dir <путь к wndr_backfill>`.
3. Проверить, что добавились только новые (дедуп сработал):
   ```bash
   docker compose exec -T db psql -U postgres -d wndrverse -c \
     "SELECT topic, max(created_at), count(*) FROM fragments GROUP BY topic ORDER BY max(created_at) DESC;"
   # last_msg по застывшим топикам должен сдвинуться к сегодняшней дате
   docker compose exec -T db psql -U postgres -d wndrverse -c \
     "SELECT count(*), count(*)-count(DISTINCT external_id) dup FROM fragments;"  # dup=0
   ```
4. ⚠️ embedder-таймер (`wndr-embedder.timer`, каждые 6ч) сам до-эмбеддит новые
   строки (batch по `embedding IS NULL`) — отдельно гонять не нужно, но можно
   форснуть `sudo systemctl start wndr-embedder.service`.

## НЕ в этой задаче

- ❌ Чинить сам realtime-маппинг (добавлять 11 топиков в topic_map.json) — это
  ОТДЕЛЬНАЯ задача (чтобы НОВЫЕ сообщения перестали теряться). Здесь только разовый
  добор прошлого. Если возьмёшься и за маппинг — нужны актуальные thread_id топиков
  (совпадают с --topic-id выше) + перезапуск `wndr-ingest-bot`.
- ❌ Трогать OpenClaw/Hermes на VPS.

## Критерий готовности

- `last_msg` по 11 застывшим топикам сдвинулся с 3 июня к текущей дате.
- `dup=0` в fragments (дедуп цел, ничего не задвоилось).
- total fragments вырос на число реально новых сообщений.
