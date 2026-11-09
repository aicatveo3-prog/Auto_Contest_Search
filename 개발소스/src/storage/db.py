import csv
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS contests (
    ix           INTEGER PRIMARY KEY,
    title        TEXT,
    category     TEXT,
    eligibility  TEXT,
    host         TEXT,
    sponsor      TEXT,
    status       TEXT,
    status_label TEXT,
    listing_status TEXT,
    flags        TEXT,
    start_date   TEXT,
    end_date     TEXT,
    dday         TEXT,
    prize_total  TEXT,
    prize_total_amount TEXT,
    prize_first  TEXT,
    prize_first_amount TEXT,
    prize_first_label TEXT,
    prize_first_count INTEGER,
    prize_breakdown TEXT,
    homepage_url TEXT,
    detail_url   TEXT,
    thumbnail    TEXT,
    attachments  TEXT,
    body_text    TEXT,
    summary      TEXT,
    sum_task     TEXT,
    sum_topic    TEXT,
    sum_format   TEXT,
    sum_target   TEXT,
    sum_submit   TEXT,
    sum_notes    TEXT,
    ai_policy    TEXT,
    ai_modality  TEXT,
    ai_evidence  TEXT,
    source_level TEXT,
    confidence   REAL,
    fit_score    REAL,
    bookmarked   INTEGER DEFAULT 0,
    collected_at TEXT,
    detail_fetched_at TEXT,
    analyzed_at  TEXT
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_contests_status ON contests(status);
CREATE INDEX IF NOT EXISTS idx_contests_ai_policy ON contests(ai_policy);
CREATE INDEX IF NOT EXISTS idx_contests_bookmarked ON contests(bookmarked);
"""

COLUMNS = [
    "ix", "title", "category", "eligibility", "host", "sponsor",
    "status", "status_label", "flags", "start_date", "end_date", "dday",
    "prize_total", "prize_total_amount", "prize_first", "prize_first_amount",
    "prize_first_label", "prize_first_count", "prize_breakdown", "homepage_url",
    "detail_url", "thumbnail", "attachments", "body_text", "summary",
    "sum_task", "sum_topic", "sum_format", "sum_target", "sum_submit",
    "sum_notes", "ai_policy",
    "ai_modality", "ai_evidence", "source_level", "confidence", "fit_score",
    "bookmarked", "collected_at", "analyzed_at",
]

_STORED_COLUMNS = set(COLUMNS) | {"listing_status", "detail_fetched_at"}
_JSON_COLUMNS = {"attachments", "prize_breakdown"}


def connect(db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    return connection


def init_db(connection):
    connection.executescript(SCHEMA)
    existing = {row[1] for row in connection.execute("PRAGMA table_info(contests)")}
    for column in (*COLUMNS, "listing_status", "detail_fetched_at"):
        if column in existing:
            continue
        column_type = "INTEGER" if column.endswith("_count") or column.endswith("_value") or column == "bookmarked" else "TEXT"
        connection.execute(f"ALTER TABLE contests ADD COLUMN {column} {column_type}")
    connection.executescript(INDEXES)
    connection.commit()


def _normalize(data):
    normalized = {}
    for key, value in data.items():
        if key not in _STORED_COLUMNS:
            continue
        if key in _JSON_COLUMNS and isinstance(value, (list, tuple, set)):
            value = json.dumps(list(value), ensure_ascii=False)
        normalized[key] = value
    return normalized


def upsert_contest(connection, data, *, commit=True):
    record = _normalize(data)
    if "ix" not in record or record["ix"] is None:
        raise ValueError("upsert_contest requires 'ix'")

    columns = list(record.keys())
    placeholders = ", ".join("?" for _ in columns)
    assignments = ", ".join(f"{col}=excluded.{col}" for col in columns if col != "ix")
    sql = (
        f"INSERT INTO contests ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT(ix) DO UPDATE SET {assignments}"
    )
    connection.execute(sql, [record[col] for col in columns])
    if commit:
        connection.commit()


def get_contests(connection, where=None, params=(), order="ix DESC"):
    query = "SELECT * FROM contests"
    if where:
        query += f" WHERE {where}"
    query += f" ORDER BY {order}"
    return [dict(row) for row in connection.execute(query, params)]


def count(connection, where=None, params=()):
    query = "SELECT COUNT(*) FROM contests"
    if where:
        query += f" WHERE {where}"
    return connection.execute(query, params).fetchone()[0]


def set_bookmark(connection, ix, value=1):
    cursor = connection.execute(
        "UPDATE contests SET bookmarked=? WHERE ix=?", (1 if value else 0, ix)
    )
    connection.commit()
    return cursor.rowcount


def get_bookmarks(connection):
    return [dict(row) for row in connection.execute(
        "SELECT * FROM contests WHERE bookmarked=1 ORDER BY end_date IS NULL, end_date ASC"
    )]


def list_bookmark_ids(connection):
    return [row[0] for row in connection.execute(
        "SELECT ix FROM contests WHERE bookmarked=1 ORDER BY ix DESC"
    )]


def _csv_value(value):
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def export_csv(connection, path, rows=None):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = rows if rows is not None else get_contests(connection)
    with open(target, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow([_csv_value(row.get(col)) for col in COLUMNS])
    return target
