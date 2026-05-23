"""
Thin LLM provider: embeddings + completion through one module.

Everything goes through here so the rest of the code never imports OpenAI
directly (ayda's mistake: get_openai_client lived in transcription_service and
was imported all over). This is also the single place where synthesis can later
switch to Claude behind a flag.
"""

import os
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()  # load .env so OPENAI_API_KEY is available for CLI runs
except ImportError:
    pass

from openai import OpenAI

logger = logging.getLogger(__name__)

# --- model constants (change here to swap models) ---
EMBED_MODEL = "text-embedding-3-small"   # 1536-dim
COMPLETION_MODEL = "gpt-4o-mini"

_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    """Lazy singleton OpenAI client from OPENAI_API_KEY."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured. Add it to .env file.")
        _client = OpenAI(api_key=api_key)
    return _client


def embed(texts: list[str]) -> list[list[float]]:
    """Batch-embed texts via EMBED_MODEL. Returns vectors in input order.

    PII: only the text is sent — never names/usernames. Order is preserved by
    the embeddings API, so the caller matches vector[i] back to its fragment id.
    """
    if not texts:
        return []
    client = get_openai_client()
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


def complete(
    prompt: str,
    *,
    model: str = COMPLETION_MODEL,
    temperature: float = 0.5,
    max_tokens: int | None = None,
) -> str:
    """One completion call. Returns the response text, stripped."""
    client = get_openai_client()
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    response = client.chat.completions.create(**kwargs)
    return (response.choices[0].message.content or "").strip()
