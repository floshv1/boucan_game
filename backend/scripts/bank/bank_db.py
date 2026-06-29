"""SQLite question bank — canonical store for the French question corpus.

This is the *source of truth* for raw questions, kept separate from the playable
``packs/`` (which the game engine reads). Importers (JsonQuizz, OpenQuizzDB, AI
generation) write here; ``build_packs.py`` queries here and emits valid packs via
``packs_store.save_pack``.

Pure stdlib (``sqlite3``) — no new dependency. The DB is a single file at
``BANK_DB`` (env, default ``data/questionbank.db`` relative to the backend dir).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

DIFFICULTIES = ("debutant", "intermediaire", "expert", "inconnu")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    question     TEXT NOT NULL,
    answer       TEXT NOT NULL,
    choices_json TEXT NOT NULL DEFAULT '[]',  -- JSON array of choices (incl. answer); [] = open-only
    theme        TEXT NOT NULL,
    difficulty   TEXT NOT NULL DEFAULT 'inconnu',
    source       TEXT NOT NULL,
    source_url   TEXT,
    anecdote     TEXT,
    image        TEXT,                         -- optional /media/<file> prompt image (drapeaux, etc.)
    qhash        TEXT NOT NULL UNIQUE,         -- dedup key (normalised question)
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_questions_theme ON questions(theme);
CREATE INDEX IF NOT EXISTS idx_questions_diff ON questions(difficulty);
"""


def db_path() -> Path:
    p = Path(os.environ.get("BANK_DB", "data/questionbank.db"))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the first DBs were created."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(questions)")}
    if "image" not in cols:
        conn.execute("ALTER TABLE questions ADD COLUMN image TEXT")
        conn.commit()


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalize_q(text: str) -> str:
    """Lowercase, drop accents/punctuation, collapse spaces — for dedup hashing."""
    t = _strip_accents(text.lower())
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def dedup_hash(question: str, answer: str = "", image: str | None = None) -> str:
    """Dedup key. Includes answer + image so image rounds that share the same
    prompt text (e.g. every flag asks "À quel pays appartient ce drapeau ?") stay
    distinct, while genuinely identical text questions still collapse."""
    basis = "|".join([normalize_q(question), normalize_q(answer), (image or "")])
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def insert_question(
    conn: sqlite3.Connection,
    *,
    question: str,
    answer: str,
    theme: str,
    choices: list[str] | None = None,
    difficulty: str = "inconnu",
    source: str = "",
    source_url: str | None = None,
    anecdote: str | None = None,
    image: str | None = None,
) -> bool:
    """Insert one question; return True if stored, False if it was a duplicate.

    ``choices`` should be the full set including ``answer`` (4 for QCM). Empty/None
    means the row is buzzer-only (no multiple-choice). Dedup is by ``qhash``.
    """
    question = (question or "").strip()
    answer = (answer or "").strip()
    if not question or not answer:
        return False
    difficulty = difficulty if difficulty in DIFFICULTIES else "inconnu"
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO questions
            (question, answer, choices_json, theme, difficulty, source, source_url, anecdote, image,
             qhash, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            question,
            answer,
            json.dumps(choices or [], ensure_ascii=False),
            theme,
            difficulty,
            source,
            source_url,
            anecdote,
            image,
            dedup_hash(question, answer, image),
            datetime.now(UTC).isoformat(),
        ),
    )
    return cur.rowcount > 0


def counts_by_theme(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    rows = conn.execute(
        "SELECT theme, COUNT(*) AS n FROM questions GROUP BY theme ORDER BY n DESC"
    ).fetchall()
    return [(r["theme"], r["n"]) for r in rows]


def total(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) AS n FROM questions").fetchone()["n"])


def fetch(
    conn: sqlite3.Connection,
    *,
    theme: str | None = None,
    difficulty: str | None = None,
    require_choices: bool = False,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    """Query questions. ``require_choices=True`` keeps only rows with 4 choices
    (needed for QCM). Results are randomised so generated packs vary."""
    sql = "SELECT * FROM questions WHERE 1=1"
    params: list[object] = []
    if theme:
        sql += " AND theme = ?"
        params.append(theme)
    if difficulty:
        sql += " AND difficulty = ?"
        params.append(difficulty)
    if require_choices:
        sql += " AND json_array_length(choices_json) = 4"
    sql += " ORDER BY RANDOM()"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()
