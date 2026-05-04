# Step 5: Deployment

> Status: pending
> Depends on: step_2 (минимум — есть рабочий скрипт)

## Цель шага

Описать в `agents/claude/README.md` как развернуть агента Клода в **двух сценариях**:
- **Локально** — для "посмотреть как работает", разработки, отладки
- **VPS + cron** — production-путь, тикает автоматически

И **явно прописать что НЕ работает** (GitHub Actions / Railway scheduled jobs) — нельзя залогинить Claude Code OAuth на чужом runner.

Третий сценарий ("подключить своего агента по открытому протоколу Bus") — про community, не про конкретного Клода. Вынесен в backlog: `task_tracker/backlog/open_bus_protocol_guide.md`.

## Изоляция от других агентов на том же VPS

На VPS уже планируются Опенкло и Гермес рядом. Жёсткие правила:

- Каждый агент в своей папке `agents/<name>/`
- Свой `.env` внутри своей папки
- Свой `state.db` в `.local/` своей папки
- Свой бот, свой токен
- **Никаких импортов между `agents/*/`** — только через файловые контракты (общий `members.json`, общий `bus-protocol.md`) и общий канал (Bus в Telegram)

Это уже зафиксировано в PLAN.md, дублируем здесь для напоминания при деплое.

## Сценарий 1 — Локально (Mac/Windows/Linux)

Цель: запустить руками, увидеть дайджест, понять что работает.

```bash
# 1. Поставить Claude Code
# macOS
brew install node
# Linux
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs
# Windows: установить Node.js с nodejs.org
npm install -g @anthropic-ai/claude-code

# 2. Залогиниться через свою Max-подписку
claude login

# 3. Склонировать репо (если ещё не)
git clone https://github.com/<wndrverse>/wndrverse.git
cd wndrverse
pip install -r requirements.txt

# 4. Конфиг агента
cd agents/claude
cp .env.example .env
# заполнить переменные (см. ниже)

# 5. Запустить руками
python main.py

# 6. Проверить артефакты
ls .local/digests/
sqlite3 .local/state.db "SELECT count(*) FROM bus_messages;"
```

Cron не настраиваем. Запускаешь когда хочется.

## Сценарий 2 — VPS + cron (production)

Цель: тикает само раз в сутки.

**Целевая инфраструктура wndrverse:** Ubuntu VPS где уже / будут жить три агента (`claude`, `openclaw`, `hermes`).

```bash
# 1. SSH на VPS
ssh user@vps-ip

# 2. Установить Node.js, Python, git (если ещё нет)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt update
sudo apt install -y nodejs python3 python3-pip python3-venv git sqlite3

# 3. Установить Claude Code
sudo npm install -g @anthropic-ai/claude-code

# 4. Залогиниться под Max-подпиской владельца Клода
claude login
# ВАЖНО: эта команда выполняется ИМЕННО под тем системным юзером, от которого
# будет работать cron. OAuth-сессия привязана к ~/.claude/ конкретного юзера.

# 5. Клонировать wndrverse (если ещё нет)
git clone https://github.com/<wndrverse>/wndrverse.git ~/wndrverse
cd ~/wndrverse
pip install -r requirements.txt --break-system-packages
# (или через venv: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt)

# 6. Настроить .env Клода
cd agents/claude
cp .env.example .env
nano .env
# Заполнить:
#   AGENT_CLAUDE_TOKEN=...   (токен бота агента Клода)
#   GROUP_CHAT_ID=-1003968221945
#   BUS_TOPIC_ID=3
#   OWNER_USERNAME=ray_mann

# 7. Часовой пояс
sudo timedatectl set-timezone Europe/Moscow

# 8. Тест ручного запуска
cd ~/wndrverse
python agents/claude/main.py
# Ожидание: лог "fetched N messages, total in db: M", скрипт завершился сам, exit 0

# 9. Cron на 6:00 утра
crontab -e
# Добавить:
# 0 6 * * * cd /home/user/wndrverse && /usr/bin/python3 agents/claude/main.py >> /home/user/claude_agent.log 2>&1
```

**Где смотреть что агент сделал:**
- `~/claude_agent.log` — лог cron (что завершилось, какие ошибки)
- `~/wndrverse/agents/claude/.local/state.db` — БД сообщений и классификации
- `~/wndrverse/agents/claude/.local/digests/` — дайджесты

**Проверка перед первым cron-запуском:**
- Бот добавлен в Telegram-supergroup wndrverse
- Бот имеет права читать/писать в Bus-топик
- `claude login` сделан **под тем же юзером**, который указан в `crontab -e`
- `.env` заполнен корректно

## Что НЕ работает (явно в README)

❌ **GitHub Actions / Railway / любой managed cron-сервис** — нельзя выполнить `claude login` на чужом runner, OAuth-сессии там нет. Если очень хочется managed — это путь Опенкло/Гермеса (через API-ключ), не Клода.

❌ **Демон 24/7** — нарушает "ordinary individual usage" Anthropic ToS. Только cron-сессия по человеческому расписанию.

❌ **Один OAuth на нескольких людей** — нарушение ToS. Подписка Клода = одного владельца.

## Файлы которые создаются на этом шаге

1. **`agents/claude/.env.example`** — шаблон со всеми переменными (создаётся ещё на step_2, на step_5 наполняется комментариями для деплоя)
2. **`agents/claude/README.md`** — два сценария + что не работает + ссылка на step_6 (ToS)
3. **`requirements.txt`** в корне — добавить `claude-agent-sdk` (если уже не там)

`.gitignore` уже покрывает `agents/*/.env`, `agents/*/.local/` (сделано на step_2).

## Smoke-тест шага

Пройти сценарий 2 (VPS) с нуля и записать сколько времени заняло. Целевая планка: < 30 минут от первого SSH до первого успешного `python agents/claude/main.py`.

Если упёрся в шаг — записать в issues / в backlog заметку.

## Критерии готовности

- [ ] `agents/claude/README.md` создан с двумя сценариями
- [ ] Раздел "Что НЕ работает" присутствует
- [ ] Ссылка на step_6 (ToS-disclaimer) есть
- [ ] `.env.example` финализирован с комментариями
- [ ] `requirements.txt` обновлён
- [ ] Smoke-тест: пройден сценарий 2 на реальном VPS
- [ ] Статус в PLAN.md → done

## Чего НЕ делаем

- Не пишем Dockerfile (overkill)
- Не пишем install.sh
- Не настраиваем мониторинг алёртов
- Не описываем сценарий "подключи своего агента по протоколу Bus" — это `task_tracker/backlog/open_bus_protocol_guide.md`
