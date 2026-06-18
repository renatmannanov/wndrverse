"""
Brain — community digest synthesis (two-pass).

Ported from ayda synthesis_service, rewritten for a COMMUNITY digest (not one
person's thought evolution). Prompts live in core/prompts/*.md. LLM via
core.llm.client.complete.

PII: fragments are grouped by author in code (before synthesis) and fed to the
LLM as "[@N] (k сообщ.):\\ntext1\\n---\\ntext2" — no author_name / username. [@N]
is an anonymous per-author key; the digest comes back with [@N] refs and the real
names are substituted locally on output (delivery) via author_refs {N: name},
never sent to OpenAI.
"""

import os
import json
import logging

from core.llm.client import complete, COMPLETION_MODEL, COMPLETION_MODEL_SYNTHESIS
from core.store.fragments_db import save_artifact

logger = logging.getLogger(__name__)

# A/B/C tested 2026-06-04 on questions_to_women May (73 msgs): synthesizing ALL
# fragments beat Pass-1 selection (5 themes vs 3, and cheaper — no Pass-1 call).
# So we only fall back to Pass-1 selection for genuinely large periods; a month
# of one topic (typ. 45–130 msgs) now goes whole into synthesis.
MAX_FRAGMENTS_WITHOUT_SELECTION = 150  # below this, no Pass-1 selection
SELECTION_TARGET = 20                   # Pass 1 picks ~this many
INPUT_HARD_CAP = 800                    # cap fed into Pass 1 (last-by-date) — context guard
# Synthesis output ceiling. The prompt targets ~2800 chars of Cyrillic (up to
# ~3500); Cyrillic is token-expensive (~0.5–0.7 tok/char on gpt-4o), so 2200
# clipped output mid-sentence near the upper bound. 3200 gives headroom.
SYNTHESIS_MAX_TOKENS = 3200

# Terminal punctuation a complete digest is expected to end on. Includes the
# typographic closing quote (U+201D) and guillemet (U+00BB) seen in real output.
_TERMINAL_CHARS = {'.', '!', '?', '…', ')', '»', '"', '”', '“'}

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "prompts")

# Topic semantics injected into prompts so harvest ≠ offerings ≠ requests, etc.
TOPIC_HINTS = {
    'harvest': "Топик «итоги цикла»: люди подводят результаты завершённого этапа.",
    'commits': "Топик «начало цикла»: люди берут на себя обязательства/планы на этап.",
    'daily': "Топик «дневник/прогресс»: ежедневные апдейты о ходе работы.",
    'offerings': "Топик «офферы»: что люди ПРЕДЛАГАЮТ (услуги, навыки, ресурсы).",
    'requests': "Топик «запросы»: что людям НУЖНО (помощь, контакты, ресурсы).",
    'intro': "Топик «знакомства»: кто пришёл в сообщество, чем занимается.",
    'sales': "Топик «продажи»: предложения о продаже/покупке.",
    'boltalka': "Топик «болталка»: свободное общение, выдели ценное среди шума.",
    'announcements': "Топик «анонсы»: важные объявления сообщества.",
    'together': "Топик «ретро/вместе»: совместная рефлексия, что получилось у группы.",
    'questions_to_women': "Топик «вопросы к женскому миру»: мужчины задают вопросы "
                          "женщинам сообщества. Выдели главные темы вопросов и суть "
                          "ответов/обсуждений.",
    'questions_to_men':   "Топик «вопросы к мужскому миру»: женщины задают вопросы "
                          "мужчинам сообщества. Выдели главные темы вопросов и суть "
                          "ответов/обсуждений.",
}

# Human-facing topic names (the original Telegram forum-topic titles) for the
# digest header. Keys not listed here fall back to the raw key (see
# delivery.cli._digest_header). NOT PII — just display labels, safe in git.
TOPIC_DISPLAY_NAMES = {
    'boltalka': "Болталка",
    'offerings': "Community offerings",
    'daily': "Daily следы",
    'requests': "Запросы",
    'intro': "Кто мы?",
    'questions_to_women': "Вопросы к Женскому миру",
    'questions_to_men': "Вопросы к Мужскому миру",
    'commits': "Коммиты",
    'harvest': "Харвест",
    'announcements': "Анонсы | Организационное",
    'quotes': "Цитатник",
    # sales / together: no pretty name -> header shows the raw key
}


def _load_prompt(name: str) -> str:
    with open(os.path.join(_PROMPTS_DIR, name), encoding="utf-8") as fh:
        return fh.read()


def synthesize(topic: str, fragments: list[dict], topic_type: str | None = None) -> dict:
    """Two-pass community digest.

    fragments: [{id, text, created_at(str), author_name, sender_id, tags}, ...] by date.
    topic_type: semantic key for the prompt hint (defaults to topic).
    Returns {'content': str, 'fragment_ids': [int], 'author_refs': {N: name},
    'found': int, 'model': str}.
    'found' = how many fragments came in (the period total); fragment_ids =
    those actually fed into synthesis (all of them, unless Pass-1 trimmed).
    author_refs maps the anonymous [@N] key to a display name (from the DB) for
    local substitution — it never goes to OpenAI and must not be logged (PII).
    """
    topic_type = topic_type or topic
    topic_hint = TOPIC_HINTS.get(topic_type, "")
    found = len(fragments)

    if len(fragments) < 3:
        content = _insufficient_data_message(topic, fragments)
        return {'content': content, 'fragment_ids': [f['id'] for f in fragments],
                'author_refs': {}, 'found': found, 'model': COMPLETION_MODEL}

    # Hard-cap input BEFORE Pass 1: take the most recent by date (context guard).
    if len(fragments) > INPUT_HARD_CAP:
        logger.info("Capping input %d → %d (last by date)", len(fragments), INPUT_HARD_CAP)
        fragments = sorted(fragments, key=lambda f: f['created_at'])[-INPUT_HARD_CAP:]

    # Pass 1: LLM selection (by text, NOT vector search) if too many.
    if len(fragments) > MAX_FRAGMENTS_WITHOUT_SELECTION:
        logger.info("Pass 1: selecting ~%d from %d", SELECTION_TARGET, len(fragments))
        selected_ids = _select_fragments(topic, topic_hint, fragments)
        selected = [f for f in fragments if f['id'] in selected_ids]
        selected.sort(key=lambda f: f['created_at'])
        logger.info("Pass 1 done: %d selected", len(selected))
    else:
        selected = fragments

    # Group selected fragments BY AUTHOR (in code — the LLM never sees names, so
    # it cannot group "по человеку" itself). One [@N] block per author.
    grouped_text, author_refs = _group_by_author(selected)

    # Pass 2: synthesis.
    logger.info("Pass 2: synthesizing %d fragments (%d authors) on '%s'",
                len(selected), len(author_refs), topic)
    content = _synthesize_fragments(topic, topic_hint, grouped_text)

    # Pass 3 (optional): critic validates content vs sources, logs defects, does
    # NOT rewrite. Both args are [@N]-form (names never substituted here) — PII safe.
    # OFF by default (extra gpt-4o call); enable with WNDR_DIGEST_CRITIC for golden
    # runs / quality debugging.
    defects = _critique(content, grouped_text) if _critic_enabled() else []
    if defects:
        logger.warning("digest critic found %d issue(s) on '%s': %s",
                       len(defects), topic, defects)

    result = {
        'content': content,
        'fragment_ids': [f['id'] for f in selected],
        'author_refs': author_refs,   # {N: name} — PII, local substitution only
        'found': found,
        'model': COMPLETION_MODEL_SYNTHESIS,  # the model that formed the content
        'critic_issues': defects,     # [] when critic disabled or no defects
    }
    return result


def _author_key(f: dict):
    """Stable per-author key: sender_id if present, else author_name, else anon.

    Anonymous messages (no sender_id, no author_name) each become their own
    "author" — we can't tell them apart, so we don't merge them.
    """
    if f.get('sender_id') is not None:
        return ('id', f['sender_id'])
    if f.get('author_name'):
        return ('name', f['author_name'])
    return ('anon', f['id'])


def _display_name(f: dict) -> str:
    """Local display string for an author: 'Name @handle' / 'Name' / 'аноним'.

    The @handle (Telegram username, from the DB) is appended bare (no brackets)
    so Telegram auto-links it to the profile. Falls back to the name alone when
    there is no handle, and to 'аноним' when there is no real author at all. This
    is PII — built locally on output, never sent to OpenAI.
    """
    has_real_author = f.get('sender_id') is not None or f.get('author_name')
    name = (f.get('author_name') if has_real_author else None) or 'аноним'
    handle = (f.get('username') or '').strip()
    return f"{name} @{handle}" if handle else name


def _group_by_author(fragments: list[dict]) -> tuple[str, dict[int, str]]:
    """Group fragments by author, preserving first-seen (date) order.

    Returns (grouped_text, author_refs):
      grouped_text feeds the LLM — each author is one [@N] block with all their
        texts joined by '---'. NO names: PII never leaves this process.
      author_refs maps N -> display string ('Name @handle' from the DB), for local
        substitution of [@N] -> display after synthesis.
    """
    order: list = []        # author keys, first-seen order
    by_key: dict = {}       # key -> {'name': str, 'texts': [str]}
    for f in sorted(fragments, key=lambda x: x['created_at'] or ''):
        k = _author_key(f)
        if k not in by_key:
            order.append(k)
            # display name taken from the author's FIRST message (handle included)
            by_key[k] = {'name': _display_name(f), 'texts': []}
        by_key[k]['texts'].append(f['text'])

    blocks: list[str] = []
    author_refs: dict[int, str] = {}
    for n, k in enumerate(order, start=1):
        author_refs[n] = by_key[k]['name']
        texts = by_key[k]['texts']
        joined = "\n---\n".join(texts)
        head = f"[@{n}] ({len(texts)} сообщ.):" if len(texts) > 1 else f"[@{n}]:"
        blocks.append(f"{head}\n{joined}")
    return "\n\n".join(blocks), author_refs


def _select_fragments(topic: str, topic_hint: str, fragments: list[dict]) -> set[int]:
    """Pass 1: LLM picks most relevant fragment IDs. No names sent — only id+date+text.

    Full text (no truncation): the A/B/C test showed truncating to 100 chars made
    Pass-1 pick by message *openings* and miss the substance, dropping whole themes.
    Pass-1 only runs for large periods anyway (> MAX_FRAGMENTS_WITHOUT_SELECTION).
    """
    fragments_list = "\n".join(
        f"[{f['id']}] {(f['created_at'] or '')[:10]} — {f['text']}"
        for f in fragments
    )
    prompt = _load_prompt("digest_selection.md").format(
        topic=topic, topic_hint=topic_hint, target=SELECTION_TARGET,
        fragments_list=fragments_list,
    )
    raw = complete(prompt, temperature=0.0)  # id selection — deterministic
    logger.debug("Selection raw: %s", raw)

    valid_ids = {f['id'] for f in fragments}
    selected: set[int] = set()
    for token in raw.replace('\n', ',').split(','):
        token = token.strip().strip('[]#')
        try:
            fid = int(token)
        except ValueError:
            continue
        if fid in valid_ids:
            selected.add(fid)

    # Fallback: if too few returned, keep the most recent SELECTION_TARGET.
    if len(selected) < 5:
        logger.warning("Selection returned %d ids; falling back to last %d by date",
                       len(selected), SELECTION_TARGET)
        recent = sorted(fragments, key=lambda f: f['created_at'])[-SELECTION_TARGET:]
        return {f['id'] for f in recent}
    return selected


def _looks_truncated(text: str) -> bool:
    """True if `text` likely got cut off mid-output (no terminal punctuation).

    Pure / testable without OpenAI. Trailing whitespace/newlines are ignored.
    Empty text -> False (not this guard's concern). A signal only — the caller
    logs a warning; it does NOT retry or raise.
    """
    stripped = text.rstrip()
    if not stripped:
        return False
    return stripped[-1] not in _TERMINAL_CHARS


def _synthesize_fragments(topic: str, topic_hint: str, grouped_text: str) -> str:
    """Pass 2: build the digest from author-grouped text.

    grouped_text is already grouped by author (see _group_by_author): each author
    is one [@N] block. No names sent — only [@N] keys + texts.
    """
    prompt = _load_prompt("digest_synthesis.md").format(
        topic=topic, topic_hint=topic_hint, fragments_text=grouped_text,
    )
    # max_tokens is a CEILING (SYNTHESIS_MAX_TOKENS), paired with the soft prompt
    # length instruction. Shorter output is fine. temperature 0.4: livelier, less
    # templated phrasing. Names are pinned by the [@N] contract (substituted
    # locally), so a higher temp can't desync them.
    content = complete(prompt, model=COMPLETION_MODEL_SYNTHESIS,
                       temperature=0.4, max_tokens=SYNTHESIS_MAX_TOKENS)
    # Anti-truncation signal: if the output doesn't end on terminal punctuation it
    # may have been clipped at the token ceiling. Log only (for golden set + prod
    # monitoring) — never retry or mutate the text.
    if _looks_truncated(content):
        tail = content.rstrip()[-20:]
        logger.warning("synthesis output may be truncated on '%s': len=%d, ends with %r",
                       topic, len(content), tail)
    return content


def _critic_enabled() -> bool:
    """True if the self-critic (Pass-3) is on. OFF by default — it costs an extra
    synthesis-model call. Enable with WNDR_DIGEST_CRITIC truthy (1/true/yes)."""
    return os.getenv("WNDR_DIGEST_CRITIC", "").strip().lower() in {"1", "true", "yes"}


def _parse_json_array(raw: str) -> list:
    """Tolerantly parse a JSON array of strings out of an LLM reply.

    Models (gpt-4o) often wrap the array in a ```json … ``` fence or add prose.
    Strip a leading/trailing code fence, then fall back to the first '[' … last ']'
    slice. Raises (caught by the caller) if no array can be recovered.
    """
    s = raw.strip()
    if s.startswith("```"):
        # drop the opening fence line (```json / ```) and any trailing fence
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("["), s.rfind("]")
        if start != -1 and end > start:
            return json.loads(s[start:end + 1])
        raise


def _critique(digest: str, grouped_text: str) -> list[str]:
    """Pass 3: validate the digest against its sources; return a list of defect
    descriptions ([] if none). Does NOT rewrite the digest.

    PII: both `digest` and `grouped_text` are [@N]-form (no names) — nothing here
    goes to OpenAI but anonymous keys + texts. Fail-soft: any error (network,
    unparseable output) -> [] + warning, never raises (must not break the digest).
    """
    prompt = _load_prompt("digest_critic.md").format(digest=digest, sources=grouped_text)
    try:
        raw = complete(prompt, model=COMPLETION_MODEL_SYNTHESIS, temperature=0.0)
        defects = _parse_json_array(raw)
    except Exception as exc:  # JSON error, network, anything — fail soft
        logger.warning("critic output unparseable/failed (%s); skipping", exc)
        return []
    if not isinstance(defects, list):
        logger.warning("critic returned non-list (%r); skipping", type(defects).__name__)
        return []
    return [str(d) for d in defects]


def _insufficient_data_message(topic: str, fragments: list[dict]) -> str:
    """<3 fragments: a plain listing. Uses the display name (Name @handle) directly
    — this branch is self-contained, it never goes through the [@N] substitution."""
    lines = [f"По топику «{topic}» найдено только {len(fragments)} сообщений — "
             f"недостаточно для дайджеста.\n"]
    for f in fragments:
        lines.append(f"• {_display_name(f)} ({(f['created_at'] or '')[:10]}) {f['text'][:150]}")
    return "\n".join(lines)


def synthesize_and_save(topic: str, fragments: list[dict], topic_type: str | None = None) -> dict:
    """synthesize() + persist the digest as an artifact. Returns the result + artifact_id."""
    result = synthesize(topic, fragments, topic_type=topic_type)
    artifact_id = save_artifact(
        topic=topic, content=result['content'], fragment_ids=result['fragment_ids']
    )
    result['artifact_id'] = artifact_id
    return result
