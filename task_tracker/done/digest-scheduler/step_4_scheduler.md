# Шаг 4: Планировщик (sleep-loop, stdlib)

> Зависит от: шаг 1 (топики/хинты), шаг 2 (telegram_dm), шаг 3 (длина)
> Статус: [ ] pending

## Задача

Создать долгоживущий процесс, который раз в день в заданное время (таймзона
`Asia/Almaty`) синтезирует дайджест по топикам WNDR и шлёт его в ЛС пользователю.
Планировщик — простой sleep-loop на stdlib (APScheduler НЕ ставим).

Файлы:
- `digest/__init__.py` — **пустой**, обязателен (иначе `python -m digest.scheduler`
  и импорты упадут `ModuleNotFoundError`).
- `digest/scheduler.py` — сам процесс.

Каталог `digest/` новый, в корне — отдельно от `delivery/` (delivery = «как
синтезировать и отправить один дайджест», digest/ = «когда это делать по расписанию»).

### Конфиг (ENV, все с дефолтами)
- `WNDR_DIGEST_TZ` — таймзона расписания, дефолт `Asia/Almaty`.
- `WNDR_DIGEST_AT` — время запуска `HH:MM`, дефолт `09:00`.
- `WNDR_DIGEST_PERIOD` — период выборки сообщений, дефолт `1d`.
- `WNDR_DIGEST_TOPICS` — список топиков через запятую, дефолт
  `questions_to_women,questions_to_men`.
- `WNDR_DIGEST_DM_USER_ID` — куда слать (используется в channels, шаг 2).

### Логика (зафиксировано)
```python
import logging, os, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from delivery.cli import _run_digest, parse_period   # готовый путь синтез+доставка
from core.store.fragments_db import get_fragments_for_digest

logger = logging.getLogger(__name__)

def _seconds_until_next(at_hhmm: str, tz: ZoneInfo) -> float:
    """Секунд до следующего наступления времени at_hhmm в зоне tz."""
    hh, mm = map(int, at_hhmm.split(":"))
    now = datetime.now(tz)
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()

def run_once(topics: list[str], period: str) -> None:
    """Один прогон: дайджест по каждому топику → доставка в ЛС.

    Guard (V1): если по топику за период 0 фрагментов — пропускаем БЕЗ синтеза
    (не тратим OpenAI и не шлём бесполезное «недостаточно данных» в ЛС).
    """
    since = parse_period(period)   # импорт — наверху модуля (для патча в тестах)
    for topic in topics:
        try:
            frags = get_fragments_for_digest(topic=topic, since=since)
            if not frags:
                logger.info("skip topic=%s — 0 fragments for period=%s", topic, period)
                continue
            _run_digest(topic, period, channel="telegram_dm")
            logger.info("digest sent: topic=%s period=%s (%d frags)", topic, period, len(frags))
        except Exception:
            logger.exception("digest FAILED topic=%s (continuing)", topic)

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        from dotenv import load_dotenv; load_dotenv()
    except ImportError:
        pass
    tz = ZoneInfo(os.getenv("WNDR_DIGEST_TZ", "Asia/Almaty"))
    at = os.getenv("WNDR_DIGEST_AT", "09:00")
    period = os.getenv("WNDR_DIGEST_PERIOD", "1d")
    topics = [t.strip() for t in
              os.getenv("WNDR_DIGEST_TOPICS", "questions_to_women,questions_to_men").split(",")
              if t.strip()]
    logger.info("scheduler up: tz=%s at=%s period=%s topics=%s", tz, at, period, topics)
    while True:
        sleep_s = _seconds_until_next(at, tz)
        logger.info("next digest in %.0f min (%s %s)", sleep_s/60, at, tz.key)
        time.sleep(sleep_s)
        run_once(topics, period)
        time.sleep(60)  # перешагнуть целевую минуту, не сработать дважды

if __name__ == "__main__":
    main()
```

### Запуск (единственная форма — зафиксировано)
`python -m digest.scheduler` (модульный; `python digest/scheduler.py` НЕ
использовать — ломает абсолютные импорты `delivery.*`). Для разового прогона без
ожидания — флаг `--now` (см. ниже).

### Флаг --now (для smoke и ручного запуска)
Добавить в main() argparse: `--now` → выполнить `run_once` немедленно и выйти (не
входить в цикл). Это и есть «ручной запуск дайджеста» сейчас + основа для будущего
`--angle`. Без `--now` — обычный цикл по расписанию.
```python
import argparse
p = argparse.ArgumentParser()
p.add_argument("--now", action="store_true", help="run once immediately and exit")
args = p.parse_args()
if args.now:
    run_once(topics, period); return
```

### Заметка по guard
`get_fragments_for_digest` в `run_once` выбирает фрагменты повторно (потом ещё раз
внутри `_run_digest`). Это лишний DB-запрос, но дешёвый (БД, не OpenAI) и читаемый —
НЕ оптимизировать прокидыванием готового списка в _run_digest (это переписывание
ядра, вне скоупа). Цена guard'а — один SELECT, выгода — не тратим OpenAI на пустой
топик. Оставить как есть.

### НЕ делать здесь
- Не ставить APScheduler/cron/systemd.
- Не реализовывать триггер по накоплению (бэклог).
- Не деплоить на VPS.
- Не добавлять `--angle` (только `--now`); сигнатура `_run_digest` уже принимает
  topic — угол прокинется позже без переделки.

## Тесты

`tests/test_scheduler.py`:
- `_seconds_until_next("09:00", ZoneInfo("Asia/Almaty"))` → число в (0, 86400].
  Зафиксировать «now» нельзя без мока datetime — проверить только диапазон и тип.
- `run_once(["t1","t2"], "1d")` с замоканными `get_fragments_for_digest`
  (возвращает непустой список) и `_run_digest` → `_run_digest` вызван для каждого
  топика с `channel="telegram_dm"`; если один топик кидает Exception — второй всё
  равно вызывается (try/except).
- **guard (V1):** `get_fragments_for_digest` вернул `[]` → `_run_digest` НЕ вызван
  для этого топика (пропуск без синтеза).

Чтобы тест мог патчить функции через `monkeypatch.setattr(scheduler, "...")`:
импорты `_run_digest`, `parse_period`, `get_fragments_for_digest` вынести в НАЧАЛО
модуля `scheduler.py` (module-level), а не внутрь `run_once`. Тогда тест патчит
`scheduler._run_digest` и `scheduler.get_fragments_for_digest` единообразно.
(В примере реализации выше они показаны внутри run_once для наглядности — в коде
поднять наверх модуля.)

## Команды для верификации

```bash
python -m pytest tests/test_scheduler.py -q
python -c "import digest.scheduler"   # импорт (нужен digest/__init__.py)

# разовый прогон вручную — В ШАГЕ 5 (тратит OpenAI, после --estimate):
#   python -m digest.scheduler --now
```

## Критерии готовности

- [ ] `digest/__init__.py` (пустой) + `digest/scheduler.py` есть; импортируется.
- [ ] `_seconds_until_next` возвращает корректную задержку до `HH:MM` в зоне tz
      (диапазон-тест зелёный).
- [ ] `run_once` зовёт `_run_digest(topic, period, channel="telegram_dm")` для
      каждого топика; падение одного топика не роняет остальные (тест).
- [ ] guard (V1): топик с 0 фрагментов за период → `_run_digest` НЕ вызван (тест).
- [ ] `--now` делает разовый прогон и выходит (без цикла).
- [ ] Конфиг целиком из ENV с дефолтами (TZ/AT/PERIOD/TOPICS/DM_USER_ID).
- [ ] `.env.example` дополнен `WNDR_DIGEST_TZ`, `WNDR_DIGEST_AT`,
      `WNDR_DIGEST_PERIOD`, `WNDR_DIGEST_TOPICS` (НЕ DM_USER_ID — его добавляет
      шаг 2, чтобы не дублировать).
- [ ] `pytest tests/test_scheduler.py` зелёный.
