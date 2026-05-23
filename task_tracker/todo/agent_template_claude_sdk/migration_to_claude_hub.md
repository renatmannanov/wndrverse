# Миграция wndrverse_agent_claude → ~/claude-hub/projects/wndrverse/

> Status: pending
> Depends on: step_5 (deploy сделан)
> Trigger: создан Claude SDK hub в `~/claude-hub/` на VPS rm_agent@62.238.31.95

## Зачем

В 00_anna проекте принято решение собирать всех Claude SDK агентов на VPS под единым hub'ом
(`~/claude-hub/projects/<name>/`). Это позволит:
- Один общий TG-роутер на все Claude-агенты владельца (`/refind`, `/wndr`, ...)
- Единое место для логов, общего venv-инструментария, скриптов, секретов общего уровня
- Cron-задачи централизованно в `~/claude-hub/cron/`

OpenClaw (`~/.openclaw/`) и Hermes (`~/.hermes/`) — НЕ в hub, они остаются как есть.
Hub только для агентов на Claude Agent SDK.

## Контекст до миграции

Сейчас на VPS:
```
/home/rm_agent/wndrverse_agent_claude/      ← код агента, cloned из GitHub
├── .git/                                   ← origin: github.com/renatmannanov/wndrverse_agent_claude
├── .venv/                                  ← Python venv (paths внутри ABSOLUTE)
├── .env                                    ← 4 переменных, 885 байт (chmod 600)
├── .local/state.db                         ← SQLite, есть данные с smoke-теста (msg_id=60)
├── main.py, bus_client.py, state_db.py
├── members.json, bus-protocol.md
└── requirements.txt
```

Cron НЕ настроен. Запускался вручную: `cd ~/wndrverse_agent_claude && .venv/bin/python main.py`.

## Куда едем

```
/home/rm_agent/claude-hub/projects/wndrverse/    ← новое местоположение
└── (всё содержимое из ~/wndrverse_agent_claude/)
```

`.git`, `.venv`, `.env`, `.local/` — переезжают как есть. GitHub remote не меняется.

## Важно про git-структуру

`~/claude-hub/` — это git checkout репо `github.com/renatmannanov/claude_hub`
(shared-код hub'а). В его `.gitignore` прописано `projects/*/` — он НАМЕРЕННО не трекает
содержимое директории `projects/`.

`~/claude-hub/projects/wndrverse/` после миграции — самостоятельный git checkout с remote
`github.com/renatmannanov/wndrverse_agent_claude` (тот же что был). Это **не submodule**,
просто два независимых git-checkout'а вложены друг в друга. Нормальный паттерн, hub-репо
просто не видит содержимого этой папки.

Что это значит для миграции:
- Простой `mv` сохраняет всю git-историю wndrverse — origin не меняется, .git/ переезжает
- В hub-репо (`~/claude-hub/`) `git status` после миграции НЕ покажет papку wndrverse
  как untracked (она в gitignore) — это правильно
- Push изменений wndrverse работает как раньше: `cd ~/claude-hub/projects/wndrverse && git push`

## Шаги

### Pre-flight

1. Убедиться что hub-каркас уже создан оператором 00_anna:
   ```bash
   ls -la ~/claude-hub/projects/
   ```
   Если папки `~/claude-hub/projects/` нет — **остановиться**, сообщить оператору
   "ждём пока 00_anna создаст hub-каркас" и не продолжать.

2. Проверить что `~/claude-hub/projects/wndrverse/` ещё НЕ существует
   (иначе — оператор уже мигрировал, не дублируем):
   ```bash
   test -d ~/claude-hub/projects/wndrverse && echo "ALREADY EXISTS, stop"
   ```

### Миграция

3. **Простой `mv`** (НЕ копирование — venv с absolute paths):
   ```bash
   mv ~/wndrverse_agent_claude ~/claude-hub/projects/wndrverse
   ```

4. Проверить что venv не сломался — paths внутри `.venv/bin/python` абсолютные,
   но Python venv обычно переживает `mv` если шебанг не залочен на старый путь.
   Тест:
   ```bash
   cd ~/claude-hub/projects/wndrverse
   .venv/bin/python -c "import claude_agent_sdk, telegram, dotenv; print('OK')"
   ```

5. Если упало с "bad interpreter" или "No module named" — пересоздать venv:
   ```bash
   cd ~/claude-hub/projects/wndrverse
   rm -rf .venv
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python -c "import claude_agent_sdk, telegram, dotenv; print('OK')"
   ```

6. Smoke-тест с реальным запуском (idempotent — повторный запуск ничего не сломает):
   ```bash
   cd ~/claude-hub/projects/wndrverse
   .venv/bin/python main.py
   ```
   Ожидание: `fetched=0 inserted=0` (всё уже в state.db с прошлого smoke-теста).
   Если увидишь auth-ошибку — `claude login` НЕ запускать без подтверждения оператора
   (OAuth может требовать interactive браузер).

### Создать PROJECT.md

7. В `~/claude-hub/projects/wndrverse/` создать файл `PROJECT.md`. **Формат: YAML
   frontmatter + markdown** — иначе runner.py из claude-hub не сможет его распарсить.

   ```markdown
   ---
   name: wndrverse
   description: Daily wndrverse Bus session (read → store → SDK ping)
   hub_version: 1
   commands:
     - name: run
       trigger: /wndr_run
       args: optional
       handler: subprocess:main.py
       timeout_sec: 360
   allowed_tools: []
   ---

   # System prompt
   (не используется для subprocess handler)

   # Описание

   Cron-агент для community network wndrverse. Раз в N часов:
   1. Читает новые Bus-сообщения (Telegram supergroup топик)
   2. Сохраняет в SQLite `.local/state.db`
   3. Классифицирует через Claude Agent SDK (OAuth Max)
   4. Генерирует digest в `.local/digests/`
   5. Постит 0-2 сообщения обратно в Bus

   Hard timeout: внутренний asyncio.wait_for=300s, runner-таймаут=360s (буфер на shutdown).

   # Команды

   - `/wndr_run` — запустить полный цикл (как cron, но руками)

   Команда `/wndr` (показать последний digest) добавится позже после step_3 основного
   плана (digest-функционал в main.py пока не реализован).

   # Cron

   Настраивается в claude-hub отдельно (cron/wndrverse_daily.sh, step_7 hub-плана).

   # Секреты

   В `.env` — `AGENT_CLAUDE_TOKEN`, `GROUP_CHAT_ID`, `BUS_TOPIC_ID`, `OWNER_USERNAME`.
   Не использует `ANTHROPIC_API_KEY` (специально дропается в main.py — OAuth-only).

   # Запуск вручную

       cd ~/claude-hub/projects/wndrverse
       .venv/bin/python main.py

   # Repo

   GitHub: https://github.com/renatmannanov/wndrverse_agent_claude
   ```

   **Почему такой формат:**
   - YAML frontmatter обязателен — `runner.py --validate wndrverse` парсит именно его
   - `handler: subprocess:main.py` — runner будет вызывать `.venv/bin/python main.py` с
     `cwd=projects/wndrverse/` (иначе bare imports в main.py упадут)
   - `timeout_sec: 360` — на 60s больше внутреннего `asyncio.wait_for(300)`. Если поставить
     360s в runner и 300s внутри — внутренний триггерится первым, чистый shutdown
   - Только одна команда (`/wndr_run`) — это всё что main.py умеет сейчас. Не закладывай
     `/wndr` под несуществующий digest-показ

### Обновить ссылки на путь

8. В `README.md` репо (`https://github.com/renatmannanov/wndrverse_agent_claude`) обновить
   секцию "Quick start" / "VPS deployment" — заменить `~/wndrverse_agent_claude` на
   `~/claude-hub/projects/wndrverse`.

   **ВАЖНО про push:** текущий remote — HTTPS. На VPS credential helper не настроен,
   gh CLI нет. `git push` зависнет, запросив логин/пароль.

   До push'а проверить что remote доступен:
   ```bash
   cd ~/claude-hub/projects/wndrverse
   git remote -v
   # Если HTTPS — нужен deploy key (или PAT). Если SSH — пробуем сразу.

   # Тест аутентификации без push'а:
   git ls-remote origin HEAD
   # Если зависает с запросом логина — push сделать НЕ получится.
   ```

   Если HTTPS и нет credentials:
   - Остановиться, сообщить владельцу что нужен deploy key для wndrverse_agent_claude
   - Владелец генерирует ключ (по паттерну step_0 в claude-hub плане), кладёт на VPS
   - Переключаем remote на SSH:
     ```bash
     git remote set-url origin git@github-wndrverse:renatmannanov/wndrverse_agent_claude.git
     ```
     где `github-wndrverse` — Host-алиас в `~/.ssh/config` указывающий на новый ключ.

   Когда push работает:
   ```bash
   cd ~/claude-hub/projects/wndrverse
   git add README.md
   git commit -m "docs: update VPS path after move to claude-hub"
   git push
   ```

9. В файле `step_5_deployment.md` (тот же план в твоём wndrverse-репо) добавить запись
   в раздел "Что уже сделано" — что сделана миграция, новый путь.

   Если файла `step_5_deployment.md` нет в твоём task_tracker — НЕ создавай его.
   Просто добавь запись в этот файл (`migration_to_claude_hub.md`) в раздел в самом конце:
   "## История изменений / 2026-XX-XX migration done".

### Безопасность отката

10. **НЕ удалять** старую папку. Если `mv` уже отработал — старой нет; но если делал `cp -r`
    как fallback — переименовать оригинал в `~/wndrverse_agent_claude.OLD` и оставить на 1 неделю.
    Удалить только после явного "да, можно сносить" от оператора.

## Критерии готовности

- [ ] `~/claude-hub/projects/wndrverse/` существует, содержит код агента
- [ ] `.venv/bin/python main.py` отрабатывает без ошибок (idempotent: `fetched=0 inserted=0`)
- [ ] `.git`, `.env`, `.local/state.db` — на месте (`ls -la`)
- [ ] `git remote -v` показывает `github.com/renatmannanov/wndrverse_agent_claude`
- [ ] `git status` чистый ИЛИ закоммичено осознанное изменение (PROJECT.md / README)
- [ ] PROJECT.md создан в новой папке
- [ ] README.md обновлён, запушен в GitHub
- [ ] Старая папка `~/wndrverse_agent_claude/` либо отсутствует (после `mv`), либо `.OLD`-суффикс

## Что НЕ делать в этой задаче

- НЕ настраивать cron — это отдельный шаг после готовности hub-роутера
- НЕ трогать `~/.openclaw/`, `~/.hermes/`, `~/.codex/`, `~/.claude/`, `~/.claude.json`
- НЕ запускать `claude login` без подтверждения оператора (OAuth flow может зависнуть в non-interactive)
- НЕ менять `requirements.txt` или код агента — только переезд + PROJECT.md + README

## Если что-то пошло не так

1. Если `mv` не прошёл (busy и т.п.) — сначала проверить нет ли запущенного процесса:
   `ps aux | grep -E 'python.*wndrverse'`. Убить только с подтверждения оператора.

2. Если venv сломался и `pip install -r requirements.txt` падает на каком-то пакете —
   остановиться, сообщить оператору с полным выводом ошибки. НЕ ставить пакеты вручную
   "наугад".

3. Если smoke-тест упал с auth-ошибкой Claude SDK — НЕ перелогинивать, сообщить оператору.
   Возможно нужен `claude login` с подтверждением, или OAuth токен живёт где-то ещё (`~/.claude/`).
