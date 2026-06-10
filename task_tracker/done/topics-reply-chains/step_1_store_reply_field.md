# Шаг 1: reply_to_msg_id и msg_id в выборке стора

> Зависит от: нет
> Статус: [x] done (2026-06-10)

## Задача

В `core/store/fragments_db.py` расширить `get_embedded_fragments_for_period`
двумя полями в возвращаемых dict'ах (SELECT уже тянет metadata-колонку
реакций — добавляем рядом):

1. `'reply_to_msg_id': str | None` — из `metadata->>'reply_to_msg_id'`
   (`Fragment.metadata_['reply_to_msg_id'].astext`). Telegram msg_id
   родителя, на которое это сообщение ответило. None если не reply.
2. `'msg_id': str | None` — СОБСТВЕННЫЙ Telegram msg_id сообщения, чтобы
   связывать reply-пары без повторного парсинга в каждом вызывающем.
   Вычисляется в Python при сборке dict'а (НЕ в SQL):
   `external_id.rsplit('_', 1)[-1]` если external_id есть и хвост — digits,
   иначе None (легаси-ключи `wndr_{chat}_{msg}` дают digits-хвост тоже —
   подходит; мусорные форматы дают None и сообщение остаётся вне цепочек).

Оба поля — строки (как в metadata), сравнение msg_id == reply_to_msg_id
делается строково. НЕ конвертировать в int (один путь, без двусмысленности).

Сигнатура, фильтры, сортировка, существующие поля — НЕ меняются.
`count_embedded_fragments_for_period` НЕ трогать (счёт не зависит от полей).

## Тесты

- Юнит не нужен (тонкое поле в выборке); проверка — командами ниже.
- Что может сломаться: потребители get_embedded_fragments_for_period —
  `delivery/cli.py` (build_topics_digest) и `core/brain/topics.py`. Они
  читают dict по ключам — ДОБАВЛЕНИЕ ключей безопасно. Прогнать их тесты.

## Команды для верификации

```bash
# оба поля присутствуют и согласованы с БД-фактами
PYTHONUTF8=1 python -c "
from dotenv import load_dotenv; load_dotenv()
from core.store.fragments_db import get_embedded_fragments_for_period
from datetime import datetime
frags = get_embedded_fragments_for_period('boltalka', datetime(2026,5,1), datetime(2026,6,1))
with_reply = [f for f in frags if f['reply_to_msg_id']]
with_mid = [f for f in frags if f['msg_id']]
print('total:', len(frags), 'with reply_to:', len(with_reply), 'with msg_id:', len(with_mid))
print('without msg_id:', len(frags) - len(with_mid))  # ожидаемо 0 или единицы (легаси-ключи)
sample = with_reply[0]
print('sample:', sample['msg_id'], '<- reply to', sample['reply_to_msg_id'])
"
# существующие тесты не сломаны
PYTHONUTF8=1 python -m pytest tests/ -q
```

## Критерии готовности

- [ ] Каждый dict содержит ключи `reply_to_msg_id` и `msg_id` (str|None).
- [ ] На boltalka/май: with reply_to > 0 (порядка сотен); «without msg_id» —
      0 или единицы (НЕ assert: легаси-ключи дают None по дизайну);
      фактическое число записать в progress.md.
- [ ] `python -m pytest tests/ -q` — все зелёные.
