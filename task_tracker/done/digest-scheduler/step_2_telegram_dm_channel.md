# Шаг 2: Канал доставки telegram_dm

> Зависит от: нет (можно параллельно шагу 1)
> Статус: [ ] pending

## Задача

Реализовать в `delivery/channels.py` канал `telegram_dm` — отправку готового
(уже humanized) текста дайджеста в личку пользователю через бота `BOT_TOKEN_INGEST`.
Сейчас этот канал — `raise NotImplementedError` (extension point, `channels.py:13`).

### Поведение
Функция `send(text, *, channel="stdout")`:
- `stdout` — как сейчас (`print`), не трогать.
- `telegram_dm` — отправить `text` в ЛС `user_id` из ENV `WNDR_DIGEST_DM_USER_ID`
  ботом с токеном `BOT_TOKEN_INGEST`. Синхронная отправка (вызывается из скрипта,
  не из async-хендлера) — использовать `Bot.send_message` через короткий
  `asyncio.run(...)`, т.к. python-telegram-bot v22 — async-only.
- `telegram_group` — оставить `NotImplementedError` (future, не в этом MVP).

### Реализация (зафиксировано)
**ВАЖНО (C2): разнести `telegram_dm` и `telegram_group` на ОТДЕЛЬНЫЕ ветки.**
Сейчас они под одной `elif channel in ("telegram_group","telegram_dm")` →
`NotImplementedError` (`channels.py:13`). Нельзя оставить их вместе: `telegram_group`
должен ОСТАТЬСЯ с `NotImplementedError`, `telegram_dm` — получить реализацию.
Итоговая структура `send()`:
```python
import asyncio, logging, os
logger = logging.getLogger(__name__)

TELEGRAM_MAX = 4096

def send(text: str, *, channel: str = "stdout") -> None:
    if channel == "stdout":
        print(text)
    elif channel == "telegram_dm":
        _send_telegram_dm(text)
    elif channel == "telegram_group":
        raise NotImplementedError("channel 'telegram_group' is a future feature")
    else:
        raise ValueError(f"unknown channel: {channel}")

def _send_telegram_dm(text: str) -> None:
    # sync-only: вызывается из синхронного scheduler (time.sleep loop), не из async.
    from telegram import Bot
    token = os.environ["BOT_TOKEN_INGEST"]
    user_id = int(os.environ["WNDR_DIGEST_DM_USER_ID"])
    if len(text) > TELEGRAM_MAX:
        logger.warning("digest %d chars > %d, truncating", len(text), TELEGRAM_MAX)
        text = text[:TELEGRAM_MAX]
    async def _go():
        bot = Bot(token)
        await bot.send_message(chat_id=user_id, text=text)
    asyncio.run(_go())
```
- Страховочная обрезка до 4096 — ЗДЕСЬ (второй слой; первый — промпт в шаге 3).
- ENV: `WNDR_DIGEST_DM_USER_ID` (новый), `BOT_TOKEN_INGEST` (есть). **Этот шаг
  отвечает за добавление `WNDR_DIGEST_DM_USER_ID` в `.env.example`** (он его вводит);
  ENV шедулера (TZ/AT/PERIOD/TOPICS) добавляет шаг 4 — не дублировать здесь.
- Парсинг markdown НЕ включаем (`parse_mode` не задаём) — дайджест может содержать
  символы, ломающие Markdown-парсер Telegram; шлём как plain text. Проще и не падает.

### НЕ делать здесь
- Не звать synthesis/digest — канал только шлёт готовый текст.
- Не реализовывать telegram_group.
- Не добавлять расписание (это шаг 4).

## Тесты

`tests/test_channels.py` (создать):
- `send("...", channel="stdout")` — печатает (capsys), не падает;
- `send(..., channel="telegram_dm")` с замоканным `telegram.Bot` — проверить, что
  `send_message` вызван с правильными `chat_id` (из ENV) и текстом;
- текст >4096 → в `send_message` уходит ровно 4096 символов (обрезка);
- `channel="telegram_group"` → `NotImplementedError`;
- `channel="bogus"` → `ValueError`.

Мок: `monkeypatch.setenv` для ENV + `monkeypatch.setattr` на `telegram.Bot`
(подменить класс на фейк, чей `send_message` пишет в список). `asyncio.run`
внутри отработает на фейке.

Заметка (M3): тест зовёт `send(...)` синхронно (без pytest-asyncio) — `asyncio.run`
создаёт свой loop, конфликта нет. НЕ помечать тест `@pytest.mark.asyncio` и не
запускать его внутри уже работающего loop — иначе `asyncio.run` бросит
`RuntimeError: event loop is already running`. Если всплывёт — мокать сам
`_send_telegram_dm` целиком (проверять что send() его вызвал), а отправку через
Bot проверять отдельным тестом на фейке без asyncio.run.

## Команды для верификации

```bash
python -m pytest tests/test_channels.py -q
python -c "import delivery.channels"   # импортируется
```

## Критерии готовности

- [ ] `send(text, channel="telegram_dm")` шлёт в ЛС `WNDR_DIGEST_DM_USER_ID`
      ботом `BOT_TOKEN_INGEST` (проверено на моке Bot).
- [ ] Текст >4096 обрезается до 4096 + `logger.warning` (не падает).
- [ ] `telegram_group` → `NotImplementedError`; неизвестный канал → `ValueError`;
      `stdout` работает как раньше.
- [ ] `.env.example` дополнен `WNDR_DIGEST_DM_USER_ID`.
- [ ] `pytest tests/test_channels.py` зелёный.
