# Промпт для деплоя на VPS (передать в окно wndrverse)

> Этот файл — самодостаточный контекст для окна wndrverse, чтобы оно могло задеплоить агента Клода на существующий VPS Рената (тот же сервер где живёт OpenClaw, но в полной изоляции от него).

---

## Цель

Задеплоить агента Клода (Option D из плана `task_tracker/todo/agent_template_claude_sdk/`) на VPS Рената по сценарию 2 из `step_5_deployment.md`. Это первый production-деплой Клода-агента.

## Контекст подписки

Ренат (он же владелец wndrverse) разворачивает агента **под свою личную Max-подписку**. Это его агент, для его участия в сообществе wndrverse. Полностью укладывается в "ordinary individual usage" Anthropic ToS (см. `step_6_legal_disclaimer.md`).

## Доступ к VPS

| Параметр | Значение |
|----------|----------|
| **IPv4** | `62.238.31.95` |
| **SSH user** | `rm_agent` |
| **SSH key path** (на локалке Рената) | Bash: `~/.ssh/openclaw_hetzner` / PowerShell: `$env:USERPROFILE\.ssh\openclaw_hetzner` |
| **Hostname** | `openclaw-prod` |
| **OS** | Ubuntu 24.04.4 LTS |
| **Хостинг** | Hetzner CX33 (4 vCPU / 8 GB RAM / 80 GB SSD) — ресурсов достаточно |
| **sudo для rm_agent** | без пароля |
| **Firewall** | ufw, открыт только OpenSSH |

Команды подключения:
```bash
# Bash
ssh -i ~/.ssh/openclaw_hetzner rm_agent@62.238.31.95

# PowerShell
ssh -i $env:USERPROFILE\.ssh\openclaw_hetzner rm_agent@62.238.31.95
```

## КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ

На этом VPS уже работает **OpenClaw** — отдельный production-агент Рената. Любая ошибка может его сломать.

### Что НЕЛЬЗЯ трогать

- `/home/rm_agent/.openclaw/` — рабочая папка OpenClaw, в т.ч. `gateway.systemd.env` с секретами
- `/home/rm_agent/.hermes/` — приостановленный Hermes pilot (сохранён на случай возврата)
- `/home/rm_agent/.openclaw/workspace/` — "душа" OpenClaw агента (в git, но не наша)
- `/etc/sudoers.d/rm_agent`, systemd unit `openclaw-gateway`, любые конфиги OpenClaw
- Никакие global npm-пакеты не трогать кроме установки нового `@anthropic-ai/claude-code` (если ещё не установлен)
- Не менять часовой пояс системы (он уже Europe/Moscow, проверить через `timedatectl`)
- Не менять OpenClaw API-ключ, не лезть в `~/.openclaw/.env`

### Команды которые ЗАПРЕЩЕНЫ

- `cat ~/.openclaw/.env` или `cat ~/.openclaw/gateway.systemd.env` — был эпизод засвета секретов 2026-05-01, не повторять
- `cat agents/claude/.env` — наш собственный .env тоже не показывать в чат
- Для проверки `.env` использовать `wc -l`, `grep -c '^[A-Z]'`, `[ -f path ] && echo OK` — но не `cat`
- Любые `rm -rf` в `/home/rm_agent/` — даже если кажется что мусор. Не наше — не трогаем
- `sudo systemctl restart` чего-либо кроме нашего нового cron-юнита (если будем делать)

### Принцип изоляции

Наш агент живёт строго в `/home/rm_agent/wndrverse/` (отдельный git clone). Все его данные (state.db, digests, .env) — **внутри** этой папки. Никаких симлинков в `~/.openclaw/`, никаких общих ресурсов.

## Аутентификация Claude Code

`claude login` интерактивная команда — открывает браузерную ссылку для OAuth.

Workflow:
1. Окно wndrverse подключается по SSH под `rm_agent`
2. Запускает `claude login`
3. Команда выводит URL — окно показывает этот URL Ренату
4. **Ренат сам открывает URL в своём браузере, авторизуется через Max-подписку**
5. После успешной авторизации команда завершается, OAuth токен ложится в `~/.claude/` юзера `rm_agent`
6. Окно продолжает деплой

**Важно:** убедиться что `claude login` запущен именно под юзером `rm_agent`, потому что cron-задача будет работать под ним же. Если случайно сделано под другим юзером — токен в другом домашнем каталоге, cron не подхватит.

## План работ

Идти строго по `step_5_deployment.md` сценарий 2 (VPS production), но с поправкой что многое уже установлено:
- Node.js — проверить, поставить если нет
- Python 3, pip, git, sqlite3 — скорее всего есть, проверить
- `@anthropic-ai/claude-code` — поставить через npm (если не стоит)

Затем:
1. `git clone` wndrverse в `/home/rm_agent/wndrverse/`
2. Установить зависимости из `requirements.txt`
3. `claude login` (интерактивно с участием Рената)
4. `cd agents/claude && cp .env.example .env`
5. **Заполнить `.env` через `nano` или `tee` БЕЗ ВЫВОДА В ЧАТ** — Ренат даст значения отдельно когда дойдём до этого шага
6. Тест ручного запуска: `python agents/claude/main.py`
7. Если успешно — настроить cron на 6:00 МСК
8. Smoke-тест следующего cron-тика

## Что нужно от Рената при деплое

- Открыть URL `claude login` в браузере и авторизоваться (1 раз)
- Дать значения для `.env` (`AGENT_CLAUDE_TOKEN`, `GROUP_CHAT_ID`, `BUS_TOPIC_ID`, `OWNER_USERNAME`)
- Подтвердить cron-расписание перед `crontab -e`

## Что окно wndrverse делает само

- SSH-подключение
- Проверка установленного софта (`node --version`, `python3 --version`, `which claude`)
- Установка отсутствующего
- `git clone`, `pip install -r requirements.txt`
- Запуск `claude login` (но Ренат завершает авторизацию)
- `cp .env.example .env`
- Запуск smoke-теста после заполнения .env
- Настройка cron

## Стоп-точки (где останавливаться и спрашивать Рената)

- Перед `claude login` — подтвердить готовность открыть URL
- Перед заполнением `.env` — Ренат даёт значения
- Перед первым `python main.py` — проверить чек-лист step_5 (бот добавлен в группу, права в Bus-топик есть, .env заполнен)
- Перед `crontab -e` — подтвердить расписание (по умолчанию `0 6 * * *` Europe/Moscow)
- Если что-то пошло не так на любом шаге — стоп, не пытаться "починить" агрессивно

## Бюджет / лимиты к учёту

- Это Max-подписка Рената — есть weekly cap, конкретное число Anthropic не публикует
- 1 cron-тик/день × ~10-30 вызовов модели = укладываемся с большим запасом
- Если упёрлись в cap — `step_2_minimal_loop.md` Q6 описывает как корректно завершить (exit code 3, лог "skipped, cap reached")

## После успешного деплоя

- Записать в `internal/projects/wndrverse/context.md` (в проекте 00_anna) факт что Клод-агент развёрнут на VPS, дату, путь установки
- Не записывать туда секреты, ключи, токены — только что они есть и где
- Обновить статус в `task_tracker/todo/agent_template_claude_sdk/PLAN.md` для step_5
