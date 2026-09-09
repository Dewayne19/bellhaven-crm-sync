"""Local review app.

Shows every proposed change beside the evidence behind it and the literal API
calls it would make. Nothing reaches the CRM until a reviewer approves it here
and then runs the apply step.
"""

import os
import sys

from flask import Flask, flash, redirect, render_template, request, url_for

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import apply as apply_command  # noqa: E402
import config  # noqa: E402
import store  # noqa: E402

KIND_LABELS = {
    "chow": (
        "Change of ownership",
        "Facility moved to Bellhaven but the old account carries revenue and "
        "open AR, so it is preserved and a new account is created alongside it.",
    ),
    "reparent": (
        "Wrong parent",
        "Listed on the Bellhaven website but filed under another parent, with "
        "no outstanding AR to protect.",
    ),
    "duplicate": (
        "Duplicate account",
        "Two or more accounts describe the same building. The loser points at "
        "the survivor and goes inactive.",
    ),
    "divested": (
        "No longer on the website",
        "Still filed under Bellhaven but absent from the site. Flagged for a "
        "human rather than deleted.",
    ),
    "create": (
        "Missing account",
        "On the website with nothing to match in the CRM.",
    ),
    "field_update": (
        "Stale fields",
        "Matched confidently; some values disagree with the website.",
    ),
}

FIELD_LABELS = {
    "name": "Name",
    "parent_id": "Parent",
    "billing_street": "Street",
    "billing_city": "Town",
    "billing_state": "State",
    "billing_zip": "Postcode",
    "care_type": "Care type",
    "phone": "Phone",
    "status": "Status",
    "duplicate_of_account": "Duplicate of",
    "chow_current_account": "Superseded by",
    "note": "Note",
}

KIND_ORDER = ["chow", "reparent", "duplicate", "divested", "create", "field_update"]


def _display(field, value, proposal):
    """Human-readable form of a value that is otherwise an opaque id."""
    if value == "$new_account":
        return "the new account created above"
    if field == "parent_id" and value == config.BELLHAVEN_PARENT_ID:
        return "Bellhaven Senior Living (%s)" % value
    if field == "duplicate_of_account":
        candidates = proposal.get("evidence", {}).get("candidates") or []
        for candidate in candidates:
            if candidate.get("account_id") == value:
                return "%s (%s)" % (candidate.get("name"), value)
    return value


def _changes(proposal):
    """Flatten the operations into field-level before/after rows."""
    crm_record = (proposal.get("evidence") or {}).get("crm") or {}
    labels = proposal.get("field_labels") or {}
    rows = []
    for op in proposal.get("ops") or []:
        creating = op.get("op") == "create"
        for field, value in (op.get("fields") or {}).items():
            if creating and field in ("note",):
                continue
            old = "" if creating else crm_record.get(field)
            if field == "parent_id" and not creating:
                old = crm_record.get("parent_name") or old
            rows.append(
                {
                    "field": FIELD_LABELS.get(field, field),
                    "label": labels.get(field, ""),
                    "old": old,
                    "new": _display(field, value, proposal),
                    "creating": creating,
                }
            )
    return rows


def _api_calls(proposal):
    calls = []
    for op in proposal.get("ops") or []:
        if op.get("op") == "create":
            calls.append({"method": "POST", "path": "/accounts", "body": op.get("fields")})
        else:
            calls.append(
                {
                    "method": "PATCH",
                    "path": "/accounts/%s" % op.get("account_id"),
                    "body": op.get("fields"),
                }
            )
    return calls


def _decorate(proposal):
    proposal = dict(proposal)
    proposal["changes"] = _changes(proposal)
    proposal["calls"] = _api_calls(proposal)
    return proposal


def _grouped(proposals):
    groups = []
    for kind in KIND_ORDER:
        rows = [_decorate(p) for p in proposals if p["kind"] == kind]
        if not rows:
            continue
        title, blurb = KIND_LABELS.get(kind, (kind, ""))
        groups.append(
            {"kind": kind, "title": title, "blurb": blurb, "rows": rows}
        )
    return groups


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("REVIEW_SECRET", "bellhaven-sync-local")

    @app.route("/")
    def queue():
        connection = store.connect()
        pending = store.pending(connection)
        return render_template(
            "queue.html",
            groups=_grouped(pending),
            counts=store.counts(connection),
            last_run=store.last_run(connection),
            pending_total=len(pending),
            approved_waiting=len(store.approved_unapplied(connection)),
        )

    @app.route("/decided")
    def decided():
        connection = store.connect()
        return render_template(
            "decided.html",
            approved=[_decorate(p) for p in store.by_decision(connection, "approved")],
            rejected=[_decorate(p) for p in store.by_decision(connection, "rejected")],
            obsolete=store.by_decision(connection, "obsolete"),
            counts=store.counts(connection),
        )

    @app.route("/decide", methods=["POST"])
    def decide():
        keys = request.form.getlist("key")
        decision = request.form.get("decision")
        if not keys:
            flash("Nothing selected.", "warn")
            return redirect(url_for("queue"))
        connection = store.connect()
        changed = store.decide(connection, keys, decision)
        flash("%d proposal(s) %s." % (changed, decision), "ok")
        return redirect(url_for("queue"))

    @app.route("/apply", methods=["POST"])
    def apply_approved():
        dry_run = bool(request.form.get("dry_run"))
        summary = apply_command.run(dry_run=dry_run)
        if not summary["queued"]:
            flash("Nothing approved is waiting to be applied.", "warn")
        elif summary["failed"]:
            failures = "; ".join(
                entry["error"] for entry in summary["log"] if not entry["ok"]
            )
            flash(
                "%d applied, %d failed: %s"
                % (summary["applied"], summary["failed"], failures),
                "error",
            )
        else:
            flash(
                "%s%d proposal(s) applied to the CRM."
                % ("[dry run] " if dry_run else "", summary["applied"]),
                "ok",
            )
        return redirect(url_for("queue"))

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
