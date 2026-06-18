"""Golden runner — DB-free unit tests (build_digest mocked, no OpenAI/DB)."""

import json
import os

import tests.golden.run as run


def _write_case(tmp_path, name, topic, since, till):
    case = {"name": name, "topic": topic, "since": since, "till": till}
    (tmp_path / f"{name}.json").write_text(json.dumps(case), encoding="utf-8")
    return case


def test_case_range_both_bounds():
    case = {"name": "x", "topic": "t", "since": "2026-05-01", "till": "2026-05-31"}
    since, until = run._case_range(case)
    assert since is not None and until is not None
    assert since.day == 1
    # until is EXCLUSIVE upper bound: 2026-05-31 + 1 day = 2026-06-01
    assert (until.month, until.day) == (6, 1)


def test_case_range_null_bounds_whole_corpus():
    case = {"name": "x", "topic": "t", "since": None, "till": None}
    assert run._case_range(case) == (None, None)


def test_loader_reads_cases(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "_CASES_DIR", str(tmp_path))
    _write_case(tmp_path, "a", "offerings", "2026-05-01", "2026-05-31")
    _write_case(tmp_path, "b", "requests", None, None)
    cases = run._load_cases()
    assert {c["name"] for c in cases} == {"a", "b"}


def test_write_creates_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "_SNAP_DIR", str(tmp_path / "snaps"))
    fake = {"text": "ДАЙДЖЕСТ-ТЕКСТ", "found": 5, "used": 5, "critic_issues": []}
    monkeypatch.setattr(run, "build_digest", lambda *a, **k: fake)
    case = {"name": "case1", "topic": "offerings", "since": "2026-05-01", "till": "2026-05-31"}
    run._cmd_write([case], baseline=False)
    snap = os.path.join(str(tmp_path / "snaps"), "case1.txt")
    assert os.path.exists(snap)
    with open(snap, encoding="utf-8") as fh:
        assert fh.read() == "ДАЙДЖЕСТ-ТЕКСТ"


def test_baseline_suffix(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "_SNAP_DIR", str(tmp_path / "snaps"))
    fake = {"text": "BASE", "found": 3, "used": 3, "critic_issues": []}
    monkeypatch.setattr(run, "build_digest", lambda *a, **k: fake)
    case = {"name": "c", "topic": "t", "since": "2026-05-01", "till": "2026-05-31"}
    run._cmd_write([case], baseline=True)
    assert os.path.exists(os.path.join(str(tmp_path / "snaps"), "c.baseline.txt"))
    assert not os.path.exists(os.path.join(str(tmp_path / "snaps"), "c.txt"))


def test_check_without_snapshot_is_friendly(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run, "_SNAP_DIR", str(tmp_path / "snaps"))
    monkeypatch.setattr(run, "build_digest", lambda *a, **k: {"text": "x"})
    case = {"name": "missing", "topic": "t", "since": "2026-05-01", "till": "2026-05-31"}
    rc = run._cmd_check([case])
    assert rc == 1  # no baseline -> flagged as diff
    assert "нет эталона" in capsys.readouterr().out


def test_check_detects_match_and_diff(tmp_path, monkeypatch):
    snap_dir = tmp_path / "snaps"
    snap_dir.mkdir()
    monkeypatch.setattr(run, "_SNAP_DIR", str(snap_dir))
    (snap_dir / "c.txt").write_text("ЭТАЛОН", encoding="utf-8")
    case = {"name": "c", "topic": "t", "since": "2026-05-01", "till": "2026-05-31"}

    monkeypatch.setattr(run, "build_digest", lambda *a, **k: {"text": "ЭТАЛОН"})
    assert run._cmd_check([case]) == 0  # matches

    monkeypatch.setattr(run, "build_digest", lambda *a, **k: {"text": "ДРУГОЕ"})
    assert run._cmd_check([case]) == 1  # diverges
