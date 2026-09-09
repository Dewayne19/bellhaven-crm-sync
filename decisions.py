"""Export the decision ledger to a readable file.

The ledger itself is a SQLite database and is not committed. This turns it
into DECISIONS.md so the reasoning behind every change is reviewable without
running anything.

    python pipeline.py log
"""

from collections import Counter
from pathlib import Path

import config
import store

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "DECISIONS.md"

KIND_TITLES = {
    "chow": "Change of ownership",
    "reparent": "Re-parented to Bellhaven",
    "duplicate": "Duplicate retired",
    "divested": "Flagged for review",
    "create": "Account created",
    "field_update": "Fields corrected",
}

ORDER = ["chow", "reparent", "duplicate", "divested", "create", "field_update"]


def _summarise(proposal):
    """One line describing what the proposal actually changes."""
    parts = []
    for op in proposal["ops"]:
        fields = {k: v for k, v in (op.get("fields") or {}).items() if k != "note"}
        if op["op"] == "create":
            parts.append("create account under Bellhaven")
        else:
            rendered = ", ".join(
                "%s -> %s" % (name, value) for name, value in sorted(fields.items())
            )
            parts.append("%s: %s" % (op["account_id"], rendered))
    return "; ".join(parts)


def export(path=OUTPUT):
    connection = store.connect()
    applied = [
        p for p in store.by_decision(connection, "approved") if p.get("applied_at")
    ]
    rejected = store.by_decision(connection, "rejected")
    counts = store.counts(connection)
    run = store.last_run(connection)

    lines = [
        "# Decision log",
        "",
        "Every change made to the CRM, why it was made, and what was declined.",
        "Generated from the decision ledger with `python pipeline.py log`.",
        "",
        "| | |",
        "| --- | --- |",
        "| Applied | %d |" % counts.get("applied", 0),
        "| Rejected | %d |" % len(rejected),
        "| Still pending | %d |" % counts.get("pending", 0),
    ]
    if run:
        lines.append("| Last pipeline run | %s |" % run["ran_at"])
        lines.append(
            "| Scope of last run | %d communities, %d CRM accounts |"
            % (run["communities"], run["accounts"])
        )
    lines.append("")

    grouped = Counter(p["kind"] for p in applied)
    lines.append("Applied by kind: " + ", ".join(
        "%s %d" % (kind, grouped[kind]) for kind in ORDER if grouped.get(kind)
    ))
    lines.append("")

    for kind in ORDER:
        rows = [p for p in applied if p["kind"] == kind]
        if not rows:
            continue
        lines.append("## %s (%d)" % (KIND_TITLES.get(kind, kind), len(rows)))
        lines.append("")
        for proposal in sorted(rows, key=lambda p: p.get("subject") or ""):
            lines.append("**%s**" % proposal["title"])
            lines.append("")
            lines.append("- Why: %s" % proposal["rationale"])
            lines.append(
                "- Matched on: %s (score %.2f), %s confidence"
                % (
                    proposal.get("tier") or "n/a",
                    proposal.get("score") or 0.0,
                    proposal.get("confidence"),
                )
            )
            lines.append("- Change: %s" % _summarise(proposal))
            lines.append("- Applied: %s" % proposal.get("applied_at"))
            lines.append("")

    if rejected:
        lines.append("## Declined (%d)" % len(rejected))
        lines.append("")
        lines.append(
            "Rejections are remembered. A later run recognises them and does "
            "not raise them again."
        )
        lines.append("")
        for proposal in rejected:
            lines.append("- **%s** -- %s" % (proposal["title"], proposal["rationale"]))
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    print("wrote %s" % export())
