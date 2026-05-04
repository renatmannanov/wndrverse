"""
SQLite state for the Claude agent.

Stores Bus messages we have already seen so:
- we don't pay SDK tokens to re-classify them next cron tick
- we know the cursor (last seen tg_message_id) to fetch only new ones
- later steps (3, 4) can ALTER TABLE to add classification fields
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS bus_messages (
    tg_message_id INTEGER PRIMARY KEY,
    posted_at     TEXT NOT NULL,
    author        TEXT NOT NULL,
    source        TEXT NOT NULL,
    text          TEXT NOT NULL,
    raw           TEXT NOT NULL,
    seen_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posted_at ON bus_messages(posted_at);
CREATE INDEX IF NOT EXISTS idx_author    ON bus_messages(author);
"""


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_last_seen_message_id(db_path: Path) -> int | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT MAX(tg_message_id) AS m FROM bus_messages").fetchone()
        return row["m"]


def insert_message(
    db_path: Path,
    tg_message_id: int,
    posted_at: str,
    author: str,
    source: str,
    text: str,
    raw: str,
    seen_at: str,
) -> bool:
    """Returns True if inserted, False if already existed (PK conflict)."""
    try:
        with connect(db_path) as conn:
            conn.execute(
                "INSERT INTO bus_messages "
                "(tg_message_id, posted_at, author, source, text, raw, seen_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (tg_message_id, posted_at, author, source, text, raw, seen_at),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def count_messages(db_path: Path) -> int:
    with connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM bus_messages").fetchone()
        return row["c"]
