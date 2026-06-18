"""Golden-set runner — manual output regression for the digest (snapshot mode).

Runs a fixed set of {topic, date-range} cases through `build_digest` and writes
each digest's text to a snapshot file. Comparison is done by hand via `git diff`
on the snapshot files (human-in-the-loop; no automatic verdict).

PII / git: snapshot files hold the HUMANIZED digest (real names + @handles) — they
are PII and MUST NOT be committed. `tests/golden/snapshots/` is gitignored. Only
`cases/*.json` (topic + dates, no PII) and this runner go to git.

Usage:
    python -m tests.golden.run                 # all cases -> <name>.txt
    python -m tests.golden.run --case NAME     # one case
    python -m tests.golden.run --baseline      # snapshot CURRENT code -> <name>.baseline.txt
    python -m tests.golden.run --check         # compare vs existing <name>.txt, exit 1 on diff

Needs a live DB (docker compose up -d db) and OPENAI_API_KEY in .env — every case
is a real synthesis call (OpenAI spend). Keep case periods NARROW (one month).
"""

import argparse
import glob
import json
import os
import sys

from dotenv import load_dotenv

# build_digest / parse_date_range are module-level public fns in delivery.cli,
# already imported by the bot — the same path /summary uses.
from delivery.cli import build_digest, parse_date_range

_HERE = os.path.dirname(__file__)
_CASES_DIR = os.path.join(_HERE, "cases")
_SNAP_DIR = os.path.join(_HERE, "snapshots")


def _load_cases() -> list[dict]:
    """Read every cases/*.json into a list of dicts {name, topic, since, till}."""
    cases = []
    for path in sorted(glob.glob(os.path.join(_CASES_DIR, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            cases.append(json.load(fh))
    return cases


def _case_range(case: dict):
    """(since, until) datetimes for a case. null/null bounds -> (None, None) = whole corpus.

    Both bounds present -> parse_date_range (until EXCLUSIVE), same as /summary.
    A single null bound is treated as open on that side.
    """
    since_s, till_s = case.get("since"), case.get("till")
    if since_s and till_s:
        return parse_date_range(since_s, till_s)
    # at least one open bound: build the pair piecewise (None = open)
    since = parse_date_range(since_s, since_s)[0] if since_s else None
    until = parse_date_range(till_s, till_s)[1] if till_s else None
    return since, until


def _snapshot_path(name: str, baseline: bool) -> str:
    suffix = ".baseline.txt" if baseline else ".txt"
    return os.path.join(_SNAP_DIR, f"{name}{suffix}")


def _run_case(case: dict) -> dict | None:
    """Call build_digest for one case. Returns its result dict (or None on 0 fragments)."""
    since, until = _case_range(case)
    return build_digest(case["topic"], since=since, until=until)


def _summary_line(case: dict, result: dict | None) -> str:
    if result is None:
        return f"{case['name']}: 0 fragments — no digest (skipped)"
    issues = result.get("critic_issues", [])
    return (f"{case['name']}: found={result.get('found')} used={result.get('used')} "
            f"len={len(result.get('text', ''))} critic_issues={len(issues)}")


def _cmd_write(cases: list[dict], baseline: bool) -> int:
    os.makedirs(_SNAP_DIR, exist_ok=True)
    for case in cases:
        result = _run_case(case)
        print(_summary_line(case, result))
        if result is None:
            continue
        with open(_snapshot_path(case["name"], baseline), "w", encoding="utf-8") as fh:
            fh.write(result["text"])
    return 0


def _cmd_check(cases: list[dict]) -> int:
    """Compare fresh output vs existing (non-baseline) snapshot. exit 1 on any diff."""
    any_diff = False
    for case in cases:
        snap = _snapshot_path(case["name"], baseline=False)
        if not os.path.exists(snap):
            print(f"{case['name']}: нет эталона — запусти без --check сначала")
            any_diff = True
            continue
        result = _run_case(case)
        new_text = "" if result is None else result.get("text", "")
        with open(snap, encoding="utf-8") as fh:
            old_text = fh.read()
        if new_text != old_text:
            print(f"{case['name']}: РАСХОЖДЕНИЕ с эталоном")
            any_diff = True
        else:
            print(f"{case['name']}: совпадает")
    return 1 if any_diff else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Digest golden-set runner (snapshot mode).")
    parser.add_argument("--case", help="run only this case (by name)")
    parser.add_argument("--baseline", action="store_true",
                        help="write <name>.baseline.txt (snapshot of CURRENT code)")
    parser.add_argument("--check", action="store_true",
                        help="compare vs existing snapshot, exit 1 on diff (no overwrite)")
    args = parser.parse_args(argv)

    load_dotenv()  # DATABASE_URL / OPENAI_API_KEY, same as delivery.cli

    cases = _load_cases()
    if args.case:
        cases = [c for c in cases if c.get("name") == args.case]
        if not cases:
            print(f"кейс не найден: {args.case}")
            return 1

    if args.check:
        return _cmd_check(cases)
    return _cmd_write(cases, baseline=args.baseline)


if __name__ == "__main__":
    sys.exit(main())
