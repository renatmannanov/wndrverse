# Review Summary — WNDRverse MVP Agent Network

> Дата: 2026-04-11
> Ревью: code + risks + structure

## Критичное (блокирует)

1. **Токены ботов в открытом виде в step_1_infra.md** [CONFIRMED]
   `CURATOR_BOT_TOKEN` и `AGENT_ONE_BOT_TOKEN` записаны в файл который идёт в git.
   Проект open-source. Нужно: отозвать токены у @BotFather прямо сейчас, перевыпустить.
   Токены хранить только в `.env` (который в `.gitignore`).

2. **`BUS_TOPIC_ID`/`SHOWCASE_TOPIC_ID` записаны как URL, а код делает `int()`** [CONFIRMED]
   `https://t.me/c/3968221945/3` → `int(...)` → `ValueError` при первом запуске.
   Нужно: сохранить только числовую часть (`3`, `1`).

3. **`client.beta.managed_agents` — неизвестно как именно устроен API** [CONFIRMED]
   Нужно проверить актуальный SDK перед шагом 3, иначе шаги 3-4 упадут.

## Важное

4. **Переменные окружения не согласованы** [CONFIRMED]
   - step_1 сохраняет `CURATOR_BOT_TOKEN`, step_3/4 читают `BOT_TOKEN`
   - step_3 создаёт агентов с ID, но шаблон `.env` не объясняет под какими именами их сохранять (`AGENT_ID_AI`, `AGENT_ID_COMMUNITY`)
   Нужно: унифицировать все имена переменных в одном месте.

5. **Нет `curator/__init__.py`** [CONFIRMED]
   Все импорты `from curator.reader import ...` сломаются с `ModuleNotFoundError`.
   Нужно: добавить создание пустого `__init__.py` в step_2.

6. **Telethon — первая авторизация требует интерактивного OTP** [CONFIRMED]
   В step_2 нет инструкции как пройти авторизацию (ввести номер телефона, код).
   Нужно: добавить команду `python -c "from telethon.sync import TelegramClient; ..."`.

7. **Нет инструкции как получить `GROUP_CHAT_ID`** [CONFIRMED]
   Есть для TOPIC_ID, нет для GROUP_CHAT_ID.

8. **Сценарий 1 (голосование) не реализован, но step_5 его требует** [CONFIRMED]
   Исполнитель встретит незапланированный объём на этапе тестирования.
   Нужно: явно пометить в step_5 что Тест 2 = stretch goal, не блокирует MVP.

9. **Нет дедупликации постов в Showcase** [LIKELY]
   При повторном запуске `main.py` создаёт дубли. При отладке это случится точно.

## Мелочи

- `CLAUDE.md`/`agent_cron.py` используют `BUS_CHAT_ID` — старое имя, в новом плане `GROUP_CHAT_ID`. Не блокирует, но путает.
- Нет проверки что userbot подписан на `iwacado` — упадёт с `ChannelPrivateError`.

## Противоречия между ревьюерами

Не найдено — все трое нашли одни и те же критические проблемы независимо.

## Рекомендации

1. **Прямо сейчас:** отозвать `CURATOR_BOT_TOKEN` и `AGENT_ONE_BOT_TOKEN` у @BotFather, перевыпустить
2. **Перед стартом:** исправить `BUS_TOPIC_ID`/`SHOWCASE_TOPIC_ID` на числа в `.env`
3. **В step_1:** убрать токены из файла, заменить на `= YOUR_TOKEN_HERE`
4. **В step_2:** добавить шаг создания `curator/__init__.py` + команду авторизации Telethon
5. **В step_3:** добавить в `.env`-шаблон `AGENT_ID_AI=` и `AGENT_ID_COMMUNITY=`
6. **В step_5:** пометить Тест 2 (голосование) как stretch goal
