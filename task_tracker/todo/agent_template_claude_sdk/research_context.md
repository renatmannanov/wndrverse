# Research context (предсобранный)

> Что уже найдено в обсуждении до создания плана. Использовать как стартовую точку для step_1, не переделывать с нуля.

Всё ниже — цитаты из официальных источников Anthropic и Claude Code, собранные через WebFetch на 2026-05-04. Если документы обновятся — перепроверить.

## Часть 1. ToS — что разрешено / запрещено / серая зона

### 1.1. Запрещено явно (red lines)

**Claude Code Legal & Compliance** — https://code.claude.com/docs/en/legal-and-compliance

> "OAuth authentication is intended exclusively for purchasers of Claude Free, Pro, Max, Team, and Enterprise subscription plans and is designed to support **ordinary use of Claude Code and other native Anthropic applications**."

> "Developers building products or services that interact with Claude's capabilities, including those using the Agent SDK, should use API key authentication... Anthropic does not permit third-party developers to offer Claude.ai login or to **route requests through Free, Pro, or Max plan credentials on behalf of their users**."

> "Anthropic reserves the right to take measures to enforce these restrictions and may do so without prior notice."

**Claude Agent SDK Overview** — https://code.claude.com/docs/en/agent-sdk/overview

> "Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK. Please use the API key authentication methods described in this document instead."

> "Use of the Claude Agent SDK is governed by Anthropic's Commercial Terms of Service..."

**Что это значит для wndrverse:**
- ❌ НЕЛЬЗЯ: SaaS где наш сервис подсовывает чужим юзерам наш OAuth-токен → значит Option D НЕ может быть managed-хостингом на нашей инфре
- ❌ НЕЛЬЗЯ: один OAuth обслуживает нескольких людей → каждый участник логинится сам своей Max
- ✅ МОЖНО: участник запускает агента сам, на своей подписке, под своим OAuth, на своём устройстве — это "ordinary use of Claude Code"

### 1.2. Автоматизация — нюанс

**Anthropic Consumer Terms, Section 3** — https://www.anthropic.com/legal/consumer-terms

> "Except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it, [you may not] access the Services through automated or non-human means, whether through a bot, script, or otherwise."

**Что это значит для wndrverse:**
- Claude Code сам по себе = "explicitly permit" для автоматизации (он по природе скриптовый)
- Cron-триггер от человека (юзер сам поставил cron) укладывается в "ordinary use"
- Дёрганье от другого бота напрямую — серая зона, поэтому в плане выбрана **асинхронная коммуникация через Bus** вместо реалтайм agent-to-agent

### 1.3. Лимиты / "ordinary individual usage"

**Claude Code Legal & Compliance** — https://code.claude.com/docs/en/legal-and-compliance

> "Claude Code usage is subject to the Anthropic Usage Policy. **Advertised usage limits for Pro and Max plans assume ordinary, individual usage of Claude Code and the Agent SDK.**"

**Help Center** — https://support.claude.com/en/articles/14552983-models-usage-and-limits-in-claude-code, https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work

- Лимиты на Pro/Max общие на все продукты ("usage limits that are shared across Claude and Claude Code")
- На Max есть weekly cap
- Конкретного числа "N вызовов в день = OK / N+1 = нет" Anthropic **не публикует**

**Что это значит для wndrverse:**
- Численного потолка нет — есть оценочное "ordinary individual"
- Архитектура плана (1 cron-тик в день, ~10-30 вызовов модели за тик) укладывается с большим запасом
- Anthropic оставляет за собой право трактовать → escape hatch: при проблемах переходим на Option B (API)

### 1.4. Обработка чужого контента

**Anthropic Consumer Terms, Section 4** — https://www.anthropic.com/legal/consumer-terms

> "By submitting Inputs to our Services, you represent and warrant that you have all rights, licenses, and permissions that are necessary for us to process the Inputs under our Terms and to provide the Services to you, including for example, to integrate with third-party services, to share Materials with others at your direction, and to take Actions."

**Что это значит для wndrverse:**
- Прямого запрета на инпут чужих сообщений из публичной группы НЕТ
- Ответственность "у меня есть права это инпутить" — на участнике
- Поскольку участник сам член группы и анализ нужен ему лично для участия в группе — это укладывается в "personal use"

### 1.5. Серые зоны (где правил нет, решаем сами в плане)

1. **Триггер не от человека напрямую** — другой агент кладёт сообщение в Bus, мой агент при следующем cron его читает. Прямого запрета нет, но дальше от "ordinary individual" чем чистая ручная работа в Claude Code.
   → **Решение в плане:** только асинхронно через Bus, никаких прямых вызовов.

2. **Несколько Max-юзеров в общей шине** — каждый агент использует только credential своего владельца, формального нарушения нет. Но "coordinate across multiple accounts" может быть истолковано — поэтому фиксируем в disclaimer.

3. **Где кончается Consumer и начинается Commercial** — Consumer Terms не покрывают Pro/Max через Agent SDK; Agent SDK официально под Commercial Terms независимо от auth. Это потенциальный конфликт между "я использую Claude Code через подписку" и "я зову Agent SDK из своего кода".
   → **Решение в плане:** Honest disclaimer, escape hatch на Option B.

## Часть 2. Источники для технического step_1

Эти ссылки точно идти проверять при выполнении step_1 (документация эволюционирует, цифры/API могут поменяться):

- https://code.claude.com/docs/en/agent-sdk/overview — общий обзор
- https://code.claude.com/docs/en/agent-sdk — вся секция
- https://code.claude.com/docs/en/legal-and-compliance — детали OAuth
- https://github.com/anthropics/claude-agent-sdk-python — Python SDK
- https://github.com/anthropics/claude-agent-sdk-typescript — TS SDK
- https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan — про подписку

## Часть 3. Что НЕ удалось проверить в обсуждении (остаётся в step_1)

Эти вопросы из step_1 ещё не закрыты, требуют WebFetch / чтения README репозиториев:

- **Q1** Какой язык SDK для wndrverse — Python / TS / subprocess CLI? (есть ли Python SDK с feature parity)
- **Q2** Как именно SDK подхватывает OAuth-сессию (где хранится токен, что приоритетнее если в env есть и API-ключ, и OAuth)
- **Q3** Точный формат `allowed_tools` — какой минимум для нашей задачи
- **Q4** Готовые MCP-серверы для Telegram (есть ли стабильные)
- **Q5** Hard-timeout сессии — встроенный или ставим snaружи через `signal.SIGALRM`
- **Q6** Поведение SDK при упирании в weekly cap Max — какая именно ошибка, как её ловить

Step_1 дозаполняет этот файл (или сам себя) ответами на Q1-Q6.

## Часть 4. Архитектурный draft (зафиксирован в PLAN.md)

```
on cron trigger (1x/day, человек выставил время):
    init Claude Agent SDK
        with OAuth (полагается на завершённый claude login)
        with allowed_tools = [минимум — TG read/write, SQLite, file]
        with hard timeout = 300s

    session.run(prompt = """
        читай Bus за 24h,
        классифицируй каждое сообщение по двум осям,
        запиши в SQLite,
        сгенери дайджест для меня,
        выбери agent_pick + agent_summary,
        запиши их в Bus.
    """)

    on success: log + exit 0
    on timeout: kill + log + exit 2
    on rate limit: log "skipped, cap reached" + exit 3
    on auth error: log "run claude login first" + exit 4
```

## Часть 5. Что предлагаю обсудить с пользователем перед step_1

(Эти вопросы могут изменить step_1 — лучше решить заранее)

1. **Python vs TypeScript SDK.** wndrverse сейчас на Python. Если Python SDK существенно отстаёт от TS — может стоит сделать D на TS (отступление от стека проекта). Зависит от того что найдём в step_1.

2. **MCP-сервер для TG vs прямой python-telegram-bot.** Первое — модно и расширяемо, второе — проще и переиспользует то что уже есть в `agent-template/sources/`. По умолчанию плана — второе.

3. **Что считать "семантическим совпадением" интересов.** Сейчас curator делает лексический matching токенов. Личный агент через SDK может делать семантический ("AI for kids" ≈ "детское обучение программированию"). Это плюс, но добавляет токены/время на классификацию. Принять как ОК?

Эти три вопроса — стоп-точка перед запуском step_1.
