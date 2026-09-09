"""Durable decision ledger.

Idempotency lives here. A proposal is identified by a hash of the operations
it would perform, so once a reviewer has approved or rejected something, later
runs recognise it and leave it alone. Pending rows that stop being generated
(because someone fixed the record by hand, or the website changed) are retired
as obsolete rather than lingering in the queue.
"""

import json
import sqlite3
from datetime import datetime, timezone

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    key          TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,
    title        TEXT,
    subject      TEXT,
    slug         TEXT,
    account_id   TEXT,
    tier         TEXT,
    score        REAL,
    confidence   TEXT,
    rationale    TEXT,
    ops          TEXT NOT NULL,
    evidence     TEXT,
    field_labels TEXT,
    decision     TEXT NOT NULL DEFAULT 'pending',
    first_seen   TEXT,
    last_seen    TEXT,
    decided_at   TEXT,
    applied_at   TEXT,
    apply_result TEXT
);

CREATE INDEX IF NOT EXISTS proposals_by_decision ON proposals (decision);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at      TEXT,
    communities INTEGER,
    accounts    INTEGER,
    proposed    INTEGER,
    added       INTEGER,
    obsoleted   INTEGER
);
"""

JSON_COLUMNS = ("ops", "evidence", "field_labels")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    connection = sqlite3.connect(str(config.DB_PATH))
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


def _hydrate(row):
    record = dict(row)
    for column in JSON_COLUMNS:
        if record.get(column):
            record[column] = json.loads(record[column])
        elif column == "field_labels":
            record[column] = {}
        elif column == "ops":
            record[column] = []
    return record


def sync(connection, proposals, communities=0, accounts=0):
    """Insert newly seen proposals; refresh last_seen on familiar ones.

    Returns (added, obsoleted). Existing decisions are never overwritten.
    """
    stamp = _now()
    added = 0
    for proposal in proposals:
        existing = connection.execute(
            "SELECT key FROM proposals WHERE key = ?", (proposal["key"],)
        ).fetchone()
        if existing:
            connection.execute(
                "UPDATE proposals SET last_seen = ? WHERE key = ?",
                (stamp, proposal["key"]),
            )
            continue
        connection.execute(
            """
            INSERT INTO proposals (
                key, kind, title, subject, slug, account_id, tier, score,
                confidence, rationale, ops, evidence, field_labels,
                decision, first_seen, last_seen
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'pending',?,?)
            """,
            (
                proposal["key"],
                proposal["kind"],
                proposal.get("title"),
                proposal.get("subject"),
                proposal.get("slug"),
                proposal.get("account_id"),
                proposal.get("tier"),
                proposal.get("score"),
                proposal.get("confidence"),
                proposal.get("rationale"),
                json.dumps(proposal.get("ops") or []),
                json.dumps(proposal.get("evidence") or {}),
                json.dumps(proposal.get("field_labels") or {}),
                stamp,
                stamp,
            ),
        )
        added += 1

    # Anything still pending that this run did not produce no longer reflects
    # reality: retire it so the reviewer is not asked about stale work.
    obsoleted = connection.execute(
        """
        UPDATE proposals
           SET decision = 'obsolete', decided_at = ?
         WHERE decision = 'pending' AND last_seen < ?
        """,
        (stamp, stamp),
    ).rowcount

    connection.execute(
        """
        INSERT INTO runs (ran_at, communities, accounts, proposed, added, obsoleted)
        VALUES (?,?,?,?,?,?)
        """,
        (stamp, communities, accounts, len(proposals), added, obsoleted),
    )
    connection.commit()
    return added, obsoleted


def by_decision(connection, decision):
    rows = connection.execute(
        "SELECT * FROM proposals WHERE decision = ? ORDER BY kind, subject",
        (decision,),
    ).fetchall()
    return [_hydrate(row) for row in rows]


def pending(connection):
    return by_decision(connection, "pending")


def approved_unapplied(connection):
    rows = connection.execute(
        """
        SELECT * FROM proposals
         WHERE decision = 'approved' AND applied_at IS NULL
         ORDER BY CASE kind WHEN 'chow' THEN 0 ELSE 1 END, kind, subject
        """
    ).fetchall()
    return [_hydrate(row) for row in rows]


def get(connection, key):
    row = connection.execute(
        "SELECT * FROM proposals WHERE key = ?", (key,)
    ).fetchone()
    return _hydrate(row) if row else None


def decide(connection, keys, decision):
    """Record approve/reject. Only pending rows can be decided."""
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be approved or rejected")
    stamp = _now()
    changed = 0
    for key in keys:
        changed += connection.execute(
            """
            UPDATE proposals SET decision = ?, decided_at = ?
             WHERE key = ? AND decision = 'pending'
            """,
            (decision, stamp, key),
        ).rowcount
    connection.commit()
    return changed


def mark_applied(connection, key, result):
    connection.execute(
        "UPDATE proposals SET applied_at = ?, apply_result = ? WHERE key = ?",
        (_now(), json.dumps(result), key),
    )
    connection.commit()


def mark_failed(connection, key, error):
    """Record a failed attempt without consuming the approval, so it retries."""
    connection.execute(
        "UPDATE proposals SET apply_result = ? WHERE key = ?",
        (json.dumps({"error": error}), key),
    )
    connection.commit()


def counts(connection):
    rows = connection.execute(
        "SELECT decision, COUNT(*) AS total FROM proposals GROUP BY decision"
    ).fetchall()
    summary = {row["decision"]: row["total"] for row in rows}
    summary["applied"] = connection.execute(
        "SELECT COUNT(*) AS total FROM proposals WHERE applied_at IS NOT NULL"
    ).fetchone()["total"]
    return summary


def last_run(connection):
    row = connection.execute(
        "SELECT * FROM runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None
