# Review Summary — prod-deploy

> Дата: 2026-06-01
> Ревью: code + risks + structure (3 агента, sonnet)

## Критичное (блокирует)

- **K1 (code+risks). `core.db init` + restore полного дампа = конфликт DDL.**
  `core/db.py:83` делает `Base.metadata.create_all` + `CREATE EXTENSION vector`
  (строка 70). `pg_dump` по умолчанию пишет DDL+данные. Порядок «init → restore»
  (step_1 п.4→п.5) → `relation already exists`, restore частично падает, корпус
  неполный. ФИКС: дамп делать `pg_dump --data-only --no-owner` (а схему создаёт
  init), ИЛИ полный дамп БЕЗ предварительного init. Зафиксировать ОДИН способ.
  Это касается и плана A (где делается дамп) — согласовать.

- **K2 (structure+risks). Дамп не создаётся явным шагом в плане A.** data-corpus
  step_5 декларирует «дамп поедет на VPS», но команды `pg_dump` с зафиксированным
  путём/флагами в шагах A нет. Исполнитель B в step_1 п.5 обнаружит, что .sql-файла
  нет. ФИКС: добавить в data-corpus явный под-шаг создания дампа (с теми же флагами,
  что и K1), либо перенести команду дампа целиком в B step_1 (делать на локальной
  машine перед scp).

- **K3 (code+risks). `*.sql` НЕТ в `.gitignore`** (есть только `data/`,
  `topic_map.json`). step_1/step_5 говорят «gitignore *.sql», но паттерна нет → дамп
  с PII (author_name) может попасть в git. ФИКС: добавить `*.sql` в `.gitignore`
  ДО создания дампа.

- **K4 (structure K2). Захардкоженные пути в systemd-юнитах vs условный каталог.**
  step_1 п.0: каталог `~/claude-hub/projects/wndrverse`, «если занято →
  wndrverse-core». Но юниты step_2/step_3 хардкодят
  `/home/rm_agent/claude-hub/projects/wndrverse` в WorkingDirectory/ExecStart/
  EnvironmentFile. Если выбран другой путь — сервис упадёт FileNotFoundError. ФИКС:
  в step_1 зафиксировать ОДИН путь без «если занято», либо явно сказать «подставить
  выбранный путь во ВСЕ юниты step_2/3».

## Важное

- **V1 (code+risks). OnCalendar с таймзоной `Asia/Almaty` — хрупкий синтаксис.**
  step_3 строки ~34,66. На Ubuntu 24.04 (systemd v255) суффикс таймзоны в OnCalendar
  ВАЛИДЕН (агенты ошиблись, сказав «невалидно вообще»), НО надёжнее отдельная
  директива. ФИКС: добавить `[Timer] Persistent=true` (уже есть) + при сомнении
  использовать UTC-время или проверить `systemd-analyze calendar "..."` ДО enable.
  Добавить шаг верификации `systemd-analyze calendar` для обоих таймеров.

- **V2 (risks). chat_id в progress.md — НЕ новый риск (уже в git).** chat_id
  `-1002924475859` УЖЕ закоммичен в `done/digest-scheduler/` и тестах (коммит
  8f4f3c6). Решение 7 PLAN.md «значения в git не писать» относится к ТОКЕНАМ/КЛЮЧАМ
  (их в плане нет), не к chat_id. Уточнить формулировку решения 7: секреты = токены/
  ключи; chat_id де-факто уже в open-source репо. НЕ критично, но уточнить чтобы
  исполнитель не паниковал.

- **V3 (code+risks). pip install ручным списком vs requirements.txt.** step_1 п.2 —
  список пакетов вручную; расходится с `requirements.txt`. ФИКС:
  `pip install -r requirements.txt`.

- **V4 (structure V1). Плейсхолдер `<ветка с влитым data-corpus>`** в step_1 git
  checkout зависит от нерешённого вопроса влития веток (data-corpus step_5). К старту
  B порядок веток должен быть решён. ФИКС: ссылка «см. data-corpus step_5, цепочка
  влития».

- **V5 (code+structure). `digest.scheduler` (ExecStart) vs `delivery digest`
  (CLAUDE.md команды).** Имена расходятся — но это РАЗНЫЕ вещи (scheduler дёргает
  delivery внутри). Не баг, но добавить проверку `python -m digest.scheduler --now`
  работает на VPS ДО включения timer (smoke ExecStart вручную раз).

- **V6 (risks+structure). Порт 5434: нет проверки занятости ДО `docker compose up`.**
  ФИКС: `ss -tlnp | grep 5434` перед поднятием; если занят — override маппинга +
  поправить DATABASE_URL.

- **V7 (risks). Дамп остаётся на VPS после restore.** PII-файл лежит на диске. ФИКС:
  после успешного restore — удалить .sql с VPS (и с локальной машины).

## Мелочи

- **M1 (code). `PYTHONUTF8=1` нет в embedder-юните** (есть в bot/digest). Embedder
  логирует мало кириллицы, но для единообразия добавить.
- **M2 (risks). sudo у rm_agent не верифицирован** — план использует sudo для
  systemd. Если нет прав — застрянет. Проверить `sudo -n true` в начале.
- **M3 (risks+structure). Повторный прогон step_4 синтеза без проверки «артефакт уже
  есть»** — создаст дубль артефакта (не критично, artifacts накапливаются). Низкий.
- **M4 (structure V2). `cd <путь>` не предваряет docker-команды в верификации** —
  если сессия сбросилась, выполнятся из `~`. Решается на месте.

## Противоречия между ревьюерами

- **OnCalendar+таймзона:** code-агент сказал «невалидно, упадёт при daemon-reload»;
  structure-агent — «нужна директива TimeZone=». Оба НЕточны: на systemd v255
  (Ubuntu 24.04) суффикс таймзоны в OnCalendar валиден. Разрешено в V1 — добавить
  `systemd-analyze calendar` верификацию, паники нет.
- **chat_id в git:** risks-агент пометил [LIKELY] «утечёт впервые»; по факту уже в
  git с прошлого плана. Разрешено в V2 — не новый риск.

## Рекомендации (что применить к плану B + один фикс в A)

1. **K1+K2:** зафиксировать способ дампа (`pg_dump --data-only --no-owner`) — добавить
   явный под-шаг создания дампа в data-corpus step_5 (или B step_1), restore БЕЗ
   повторного init конфликта. Один способ, без «либо/или».
2. **K3:** добавить `*.sql` в `.gitignore` (под-шаг в B step_1, ДО дампа).
3. **K4:** убрать «если занято → wndrverse-core», зафиксировать ОДИН путь; либо явная
   инструкция подставить путь во все юниты.
4. **V1:** добавить `systemd-analyze calendar "<OnCalendar>"` верификацию таймеров.
5. **V2:** уточнить решение 7 (секреты=токены/ключи; chat_id уже в репо).
6. **V3:** `pip install -r requirements.txt`.
7. **V4:** ссылка на цепочку влития из data-corpus step_5.
8. **V5:** ручной smoke ExecStart дайджеста ДО enable timer.
9. **V6:** проверка порта 5434 перед up.
10. **V7:** удалить .sql с VPS и локально после restore.
11. **M1/M2:** PYTHONUTF8 в embedder; `sudo -n true` в начале.
