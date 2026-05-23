"""
Enrich: embeddings + language detection + dedup for unembedded fragments.

Ported from ayda normalizer_service with two changes for our volume (~150k):
- progress logging (processed / total)
- a --estimate mode that prints count + a cost estimate WITHOUT calling the API.

PII: only fragment text is sent to OpenAI (embed). Names/usernames stay in the DB.
Do NOT add author_name to the embedded text.
"""

import sys
import logging

from core.llm.client import embed, EMBED_MODEL
from core.store.fragments_db import (
    get_unembedded_fragments,
    count_unembedded_fragments,
    sum_unembedded_chars,
    update_embedding,
    update_fragment_fields,
    find_near_duplicates,
)

logger = logging.getLogger(__name__)

# text-embedding-3-small pricing (USD per 1M tokens), ~4 chars ≈ 1 token.
_USD_PER_1M_TOKENS = 0.02
_CHARS_PER_TOKEN = 4


def estimate() -> dict:
    """Print count of unembedded fragments + a rough cost estimate. No API call."""
    n = count_unembedded_fragments()
    chars = sum_unembedded_chars()
    tokens = chars / _CHARS_PER_TOKEN
    cost = tokens / 1_000_000 * _USD_PER_1M_TOKENS
    info = {'unembedded': n, 'chars': chars, 'est_tokens': int(tokens), 'est_usd': cost}
    logger.info(
        "ESTIMATE: %d unembedded fragments, ~%d chars, ~%d tokens, model %s → ~$%.4f",
        n, chars, int(tokens), EMBED_MODEL, cost,
    )
    return info


def _detect_language(text: str) -> str:
    """Detect language by letter chars (no API). >70% cyrillic→ru, <30%→en, else mixed."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 'mixed'
    cyrillic = sum(1 for c in letters if 'Ѐ' <= c <= 'ӿ')
    ratio = cyrillic / len(letters)
    if ratio > 0.7:
        return 'ru'
    elif ratio < 0.3:
        return 'en'
    return 'mixed'


def _check_duplicates(fragment_id: int, embedding: list[float]) -> bool:
    """Mark is_duplicate if cosine similarity > 0.95 with an existing original."""
    dupes = find_near_duplicates(embedding, threshold=0.95, exclude_id=fragment_id)
    if dupes:
        update_fragment_fields(fragment_id, is_duplicate=True)
        logger.debug("Fragment %s duplicate of %s (dist=%.4f)",
                     fragment_id, dupes[0]['id'], dupes[0]['distance'])
        return True
    return False


def _process_batch(fragments: list[dict]) -> dict:
    """Embed a batch, detect language, check duplicates. Commits per-item via CRUD."""
    try:
        texts = [f['text'] for f in fragments]   # ONLY text → OpenAI (PII)
        embeddings = embed(texts)
    except Exception as e:
        logger.error("Embedding generation failed: %s", e)
        return {'embedded': 0, 'duplicates': 0, 'errors': len(fragments)}

    embedded = duplicates = errors = 0
    for frag, emb in zip(fragments, embeddings):
        try:
            update_embedding(frag['id'], emb)
            update_fragment_fields(frag['id'], language=_detect_language(frag['text']))
            if _check_duplicates(frag['id'], emb):
                duplicates += 1
            else:
                embedded += 1
        except Exception as e:
            logger.error("Error processing fragment %s: %s", frag['id'], e)
            errors += 1
    return {'embedded': embedded, 'duplicates': duplicates, 'errors': errors}


def normalize_all(batch_size: int = 100) -> dict:
    """Embed all unembedded fragments, batch by batch (commit after each → resumable).

    Logs progress (processed / total).
    """
    total = count_unembedded_fragments()
    logger.info("Starting enrich: %d unembedded fragments", total)
    embedded = duplicates = errors = processed = 0

    while True:
        fragments = get_unembedded_fragments(limit=batch_size)
        if not fragments:
            break
        res = _process_batch(fragments)
        embedded += res['embedded']
        duplicates += res['duplicates']
        errors += res['errors']
        processed += len(fragments)
        logger.info("Progress: %d / %d  (+%d embedded, +%d dup, +%d err)",
                    processed, total, res['embedded'], res['duplicates'], res['errors'])
        # Safety: if a whole batch errored, embeddings stay NULL → infinite loop. Stop.
        if res['embedded'] == 0 and res['duplicates'] == 0 and res['errors'] == len(fragments):
            logger.error("Whole batch failed; stopping to avoid an infinite loop.")
            break

    logger.info("Enrich complete: %d embedded, %d duplicates, %d errors",
                embedded, duplicates, errors)
    return {'embedded': embedded, 'duplicates': duplicates, 'errors': errors}


def _main(argv: list[str]) -> int:
    import argparse

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Embed unembedded fragments")
    parser.add_argument("--estimate", action="store_true",
                        help="Print count + cost estimate, do NOT call the API")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args(argv)

    if args.estimate:
        estimate()
        return 0
    normalize_all(batch_size=args.batch_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
