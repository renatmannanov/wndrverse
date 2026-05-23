# Шаг 3: LLM-слой (тонкий провайдер)

> Зависит от: нет (можно параллельно шагу 2; делается до enrich/brain)
> Статус: [ ] pending

## Задача

Один тонкий модуль провайдера, чтобы embeddings и completion вызывались через
него, а не напрямую из сервисов. Это убирает хардкод OpenAI по всему коду
(косяк ayda: `get_openai_client` импортировался из transcription_service в каждом
сервисе) и даёт точку, где синтез позже переключится на Claude.

1. `core/llm/client.py`:
   ```python
   def get_openai_client():
       """Ленивый singleton OpenAI client из OPENAI_API_KEY."""

   def embed(texts: list[str]) -> list[list[float]]:
       """Батч-эмбеддинг через text-embedding-3-small. Возвращает векторы по порядку."""

   def complete(prompt: str, *, model: str = "gpt-4o-mini",
                temperature: float = 0.5, max_tokens: int | None = None) -> str:
       """Один completion-вызов, возвращает текст ответа .strip()."""
   ```
   Модель эмбеддинга и дефолтную completion-модель вынести в константы модуля.

2. Никаких других зависимостей. Не тащить transcription_service из ayda
   (он про Whisper — нам не нужен в MVP).

## Тесты

- Проверка вызовом (требует OPENAI_API_KEY в .env):
  `embed(["привет","hello"])` → 2 вектора длины 1536.
  `complete("Ответь одним словом: столица Франции")` → непустая строка.

## Команды для верификации

```bash
python -c "from core.llm.client import embed; v=embed(['тест']); print(len(v), len(v[0]))"   # 1 1536
python -c "from core.llm.client import complete; print(complete('Скажи ОК'))"                 # непустой ответ
```

## Критерии готовности

- [ ] `core/llm/client.py` экспортирует `get_openai_client`, `embed`, `complete`
- [ ] `embed(['тест'])` возвращает вектор длины 1536
- [ ] `complete(...)` возвращает непустую строку
- [ ] Модель эмбеддинга/completion заданы константами (легко поменять)
- [ ] Нет импорта transcription_service / Whisper-кода
