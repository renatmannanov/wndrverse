# Шаг 7: Delivery + CLI

> Зависит от: шаг 6 (synthesis)
> Статус: [ ] pending

## Задача

Тонкий слой доставки. В MVP канал = stdout. Заложить интерфейс так, чтобы
будущие каналы (telegram группа/личка) добавлялись без переделки brain/core.

1. `delivery/channels.py`:
   ```python
   def send(text: str, *, channel: str = "stdout") -> None:
       """Отправить готовый текст в канал. MVP: stdout.
       Future: 'telegram_group', 'telegram_dm'."""
   ```
   В MVP реализован только stdout (print). Telegram-каналы — заглушки с
   `raise NotImplementedError("future")`, чтобы было видно точку расширения.

2. `delivery/cli.py` — точка входа MVP:
   ```
   python -m delivery digest --topic offerings --period 1w [--channel stdout]
   ```
   - `--topic` — имя топика (offerings/harvest/...) или `all` (без фильтра).
   - `--period` — `1w` / `1m` / `all` → переводится в `since` datetime.

   **Свой `parse_period` (НЕ брать из telegram-gather).** Тамошний парсер умеет только
   `h/d/w` — на `1m` он тихо вернёт 1 день (`m` падает в else → days=1). Написать свой
   в `delivery/cli.py`:
   - `all` → `since = None` (весь корпус, обрабатывается ДО парсера).
   - суффиксы: `h`=часы, `d`=дни, `w`=недели, `m`=месяцы (30 дней).
   - `since = datetime.utcnow() - timedelta(...)`.
   - неизвестный суффикс → явная ошибка (raise), НЕ молчаливый фолбэк.

   - Поток: `get_fragments_for_digest(topic, since)` → `synthesize(topic, frags)`
     → подстановка имён (см. п.4) → `channels.send(content)`.
   - Передавать `topic_type` в synthesize по имени топика (маппинг семантики из PLAN).

3. Параметр `--period all` для smoke (весь корпус по топику).

4. **Подстановка имён на выводе (PII-решение из PLAN п.8).** Синтез возвращает текст
   со ссылками `[#id]` (без имён — имена в OpenAI не уходят). На выводе подставить имена
   локально из БД: для каждого `[#id]` в тексте дайджеста найти `author_name` фрагмента
   и заменить `[#id]` → `[author_name, дата]` (или `[аноним, дата]` если author_name пуст
   или sender_id None). Это делается в delivery, не в core. Функция вроде
   `humanize_refs(content: str, fragments: list[dict]) -> str`.

## Тесты

Юнит-тесты не нужны (тонкий клей). Проверка — реальным запуском (это и есть
вход в smoke-шаг 8).

## Команды для верификации

```bash
python -m delivery digest --topic offerings --period all
python -m delivery digest --topic harvest --period all
python -m delivery digest --topic all --period 1m
```
Каждая выдаёт связный дайджест в stdout без traceback.

## Критерии готовности

- [ ] `python -m delivery digest --topic offerings --period all` печатает дайджест в stdout
- [ ] `--period 1w/1m/all` корректно фильтрует по дате (1m = 30 дней, НЕ 1 день; all = весь корпус)
- [ ] неизвестный суффикс периода → ошибка, не молчаливый фолбэк
- [ ] `--topic all` работает без фильтра по топику
- [ ] На выводе `[#id]` заменены на `[Имя, дата]` локально из БД (имя НЕ из OpenAI)
- [ ] None-автор выводится как `[аноним, дата]`, не `[None, ...]`
- [ ] topic_type прокидывается в synthesize (harvest/commits/daily осмыслены по-разному)
- [ ] telegram-каналы — заглушки NotImplementedError (точка расширения видна)
