"""Turn matches into concrete, reviewable change proposals.

Each proposal carries the exact API operations it would run, the evidence
behind it, and a stable key. The key is a hash of the operations, so a
proposal that has already been decided is recognised on the next run and
never re-enters the queue.
"""

import hashlib
import json
from datetime import date

import config
from match import (
    TIER_WEAK,
    match_all,
)
from normalize import (
    address_key,
    is_po_box,
    map_care_types,
    norm_city,
    norm_name,
    norm_phone,
    norm_state,
    norm_street,
    norm_zip,
)

# Fields whose values change how sales works the account. Everything else is
# presentation and is grouped separately so a reviewer can triage quickly.
COSMETIC_LABELS = {"spelling", "phone"}

KIND_ORDER = [
    "chow",
    "reparent",
    "duplicate",
    "divested",
    "create",
    "field_update",
]


def _proposal_key(kind, subject_id, ops):
    payload = json.dumps(
        {"kind": kind, "subject": subject_id, "ops": ops},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _account_view(account):
    """Trimmed account record for display in the review app."""
    keys = (
        "account_id", "name", "parent_id", "parent_name", "billing_street",
        "billing_city", "billing_state", "billing_zip", "care_type", "status",
        "phone", "lifetime_revenue", "outstanding_ar", "chow_current_account",
        "duplicate_of_account", "note",
    )
    return {key: account.get(key) for key in keys}


def _diff_fields(community, account):
    """Website-vs-CRM disagreements, with formatting noise filtered out.

    Street and postcode are compared after normalization so that
    "4930 W Lake Rd" and "4930 West Lake Road" do not generate busywork.
    """
    changes, labels = {}, {}

    site_name = (community.get("name") or "").strip()
    crm_name = (account.get("name") or "").strip()
    if site_name and site_name != crm_name:
        changes["name"] = site_name
        labels["name"] = (
            "rename" if norm_name(site_name) != norm_name(crm_name) else "spelling"
        )

    site_street = (community.get("street") or "").strip()
    crm_street = account.get("billing_street") or ""
    if site_street and norm_street(site_street) != norm_street(crm_street):
        changes["billing_street"] = site_street
        labels["billing_street"] = (
            "po box replaced" if is_po_box(crm_street) else "address"
        )

    if norm_zip(community.get("zip")) != norm_zip(account.get("billing_zip")):
        changes["billing_zip"] = community.get("zip")
        labels["billing_zip"] = "postcode"

    if norm_city(community.get("city")) != norm_city(account.get("billing_city")):
        changes["billing_city"] = community.get("city")
        labels["billing_city"] = "town"

    if norm_state(community.get("state")) != norm_state(account.get("billing_state")):
        changes["billing_state"] = community.get("state")
        labels["billing_state"] = "state"

    mapped = map_care_types(community.get("care_types"))
    if mapped and (account.get("care_type") or "").strip() not in mapped:
        changes["care_type"] = mapped[0]
        labels["care_type"] = "care type"

    site_phone = (community.get("phone") or "").strip()
    if site_phone and norm_phone(site_phone) != norm_phone(account.get("phone")):
        changes["phone"] = site_phone
        labels["phone"] = "phone"

    return changes, labels


def _materiality(labels):
    if any(label not in COSMETIC_LABELS for label in labels.values()):
        return "high"
    return "low"


def _needs_chow(account):
    """The SOP branch: preserve the old account only when billing needs it.

    Read strictly as revenue history AND outstanding AR, both above zero. On
    this data that is Tiffin and Marietta; Bellhaven Crossings of Lima has
    revenue but no open AR and so is re-parented directly.
    """
    return (account.get("lifetime_revenue") or 0) > 0 and (
        account.get("outstanding_ar") or 0
    ) > 0


def _new_account_fields(community, note):
    mapped = map_care_types(community.get("care_types"))
    return {
        "name": community.get("name"),
        "parent_id": config.BELLHAVEN_PARENT_ID,
        "billing_street": community.get("street"),
        "billing_city": community.get("city"),
        "billing_state": community.get("state"),
        "billing_zip": community.get("zip"),
        "care_type": mapped[0] if mapped else "",
        "phone": community.get("phone"),
        "status": "Active",
        "note": note,
    }


def _same_address_other_operator(index, account):
    """Accounts at this address belonging to somebody other than Bellhaven."""
    key = address_key(account.get("billing_street"), account.get("billing_zip"))
    if not key:
        return []
    return [
        other for other in index.by_address.get(key, [])
        if other["account_id"] != account["account_id"]
        and (other.get("parent_id") or "") != config.BELLHAVEN_PARENT_ID
    ]


def _duplicate_ops(losers, survivor_ref, survivor_label):
    ops = []
    for loser in losers:
        note = (
            "Duplicate of %s (%s). Same street address and postcode; "
            "retired by the website sync." % (survivor_label, survivor_ref)
        )
        ops.append(
            {
                "op": "patch",
                "account_id": loser["account_id"],
                "fields": {
                    "duplicate_of_account": survivor_ref,
                    "status": "Inactive",
                    "note": note,
                },
            }
        )
    return ops


def build(accounts, communities):
    matches, missing, index = match_all(accounts, communities)
    today = date.today().isoformat()
    proposals = []

    def add(kind, subject_id, ops, **extra):
        if not ops:
            return
        proposal = {
            "key": _proposal_key(kind, subject_id, ops),
            "kind": kind,
            "ops": ops,
        }
        proposal.update(extra)
        proposals.append(proposal)

    for m in matches:
        community = m.community
        site_view = dict(community)

        # No trustworthy match: the facility needs its own account. A weak-tier
        # candidate is shown as evidence but never written to.
        if not m.confident:
            candidate = m.near_misses or []
            if m.tier == TIER_WEAK and m.survivor:
                candidate = [
                    {
                        "account_id": m.survivor["account_id"],
                        "name": m.survivor.get("name"),
                        "street": m.survivor.get("billing_street"),
                        "city": m.survivor.get("billing_city"),
                        "state": m.survivor.get("billing_state"),
                        "zip": m.survivor.get("billing_zip"),
                        "parent_name": m.survivor.get("parent_name"),
                        "score": m.score,
                    }
                ] + [
                    n for n in m.near_misses
                    if n["account_id"] != m.survivor["account_id"]
                ]

            # Only a candidate in the same town is worth calling out. A
            # same-state name resemblance two hundred miles away is noise and
            # would make the note actively misleading.
            local = [
                c for c in candidate
                if norm_city(c.get("city")) == norm_city(community.get("city"))
            ]

            note = "Listed on the Bellhaven website (%s) with no CRM account. " \
                   "Created by the website sync on %s." % (community["url"], today)
            if local:
                note += (
                    " Nearest existing record in the same town: %s at %s (%s) -- "
                    "different street address, treated as a separate facility."
                    % (
                        local[0]["name"],
                        local[0]["street"],
                        local[0].get("parent_name") or "no parent",
                    )
                )
            add(
                "create",
                community["slug"],
                [{"op": "create", "fields": _new_account_fields(community, note),
                  "bind": "new_account"}],
                title="Create account for %s" % community["name"],
                subject=community["name"],
                slug=community["slug"],
                account_id="",
                tier=m.tier or "none",
                score=m.score,
                confidence="low" if local else "medium",
                rationale=m.reason,
                evidence={"site": site_view, "crm": None, "candidates": candidate},
                field_labels={},
            )
            continue

        survivor = m.survivor
        changes, labels = _diff_fields(community, survivor)
        parent_id = survivor.get("parent_id") or ""
        wrong_parent = parent_id != config.BELLHAVEN_PARENT_ID

        if wrong_parent and _needs_chow(survivor):
            # Preserve the billing record untouched apart from the mandated
            # pointer; the explanation lives on the new account.
            note = (
                "Change of ownership from %s. Supersedes account %s, which is "
                "retained for billing (lifetime revenue %s, outstanding AR %s). "
                "Created by the website sync on %s."
                % (
                    survivor.get("parent_name") or "a previous parent",
                    survivor["account_id"],
                    survivor.get("lifetime_revenue"),
                    survivor.get("outstanding_ar"),
                    today,
                )
            )
            fields = _new_account_fields(community, note)
            ops = [
                {"op": "create", "fields": fields, "bind": "new_account"},
                {
                    "op": "patch",
                    "account_id": survivor["account_id"],
                    "fields": {"chow_current_account": "$new_account"},
                },
            ]
            # Any twin at the same address points at the new current record.
            ops.extend(
                _duplicate_ops(m.duplicates, "$new_account", community["name"])
            )
            add(
                "chow",
                survivor["account_id"],
                ops,
                title="Change of ownership: %s" % community["name"],
                subject=community["name"],
                slug=community["slug"],
                account_id=survivor["account_id"],
                tier=m.tier,
                score=m.score,
                confidence="high",
                rationale=(
                    "Now listed under Bellhaven but the CRM account sits under %s "
                    "and carries revenue of %s with %s still outstanding, so the "
                    "SOP requires a new account rather than a re-parent."
                    % (
                        survivor.get("parent_name"),
                        survivor.get("lifetime_revenue"),
                        survivor.get("outstanding_ar"),
                    )
                ),
                evidence={
                    "site": site_view,
                    "crm": _account_view(survivor),
                    "candidates": [],
                },
                field_labels={},
            )
            continue

        if wrong_parent:
            fields = {"parent_id": config.BELLHAVEN_PARENT_ID}
            fields.update(changes)
            merged_labels = dict(labels)
            merged_labels["parent_id"] = "parent"
            add(
                "reparent",
                survivor["account_id"],
                [{"op": "patch", "account_id": survivor["account_id"],
                  "fields": fields}],
                title="Re-parent %s to Bellhaven" % survivor.get("name"),
                subject=community["name"],
                slug=community["slug"],
                account_id=survivor["account_id"],
                tier=m.tier,
                score=m.score,
                confidence="high",
                rationale=(
                    "Listed on the Bellhaven website; the CRM still has it under "
                    "%s. No outstanding AR, so the existing account moves directly."
                    % (survivor.get("parent_name") or "no parent")
                ),
                evidence={
                    "site": site_view,
                    "crm": _account_view(survivor),
                    "candidates": [],
                },
                field_labels=merged_labels,
            )
        elif changes:
            add(
                "field_update",
                survivor["account_id"],
                [{"op": "patch", "account_id": survivor["account_id"],
                  "fields": changes}],
                title="Update %s" % survivor.get("name"),
                subject=community["name"],
                slug=community["slug"],
                account_id=survivor["account_id"],
                tier=m.tier,
                score=m.score,
                confidence=_materiality(labels),
                rationale="Matched on %s. The website disagrees with the CRM on: %s."
                          % (m.reason, ", ".join(sorted(set(labels.values())))),
                evidence={
                    "site": site_view,
                    "crm": _account_view(survivor),
                    "candidates": [],
                },
                field_labels=labels,
            )

        # Duplicate clean-up for non-CHOW clusters, one proposal per loser so
        # each can be judged on its own.
        if m.duplicates:
            for loser in m.duplicates:
                ops = _duplicate_ops(
                    [loser], survivor["account_id"], survivor.get("name")
                )
                add(
                    "duplicate",
                    loser["account_id"],
                    ops,
                    title="Retire duplicate %s" % loser.get("name"),
                    subject=community["name"],
                    slug=community["slug"],
                    account_id=loser["account_id"],
                    tier=m.tier,
                    score=m.score,
                    confidence="high",
                    rationale=(
                        "Shares a street address and postcode with %s, which is "
                        "kept because %s."
                        % (
                            survivor.get("name"),
                            "it carries the revenue and AR history"
                            if (survivor.get("lifetime_revenue") or 0)
                            + (survivor.get("outstanding_ar") or 0) > 0
                            else "it sits closest to Bellhaven in the parent tree",
                        )
                    ),
                    evidence={
                        "site": site_view,
                        "crm": _account_view(loser),
                        "candidates": [_account_view(survivor)],
                    },
                    field_labels={},
                )

    # Accounts still under Bellhaven that the website no longer lists.
    for account in missing:
        others = _same_address_other_operator(index, account)
        has_ar = (account.get("outstanding_ar") or 0) > 0
        if others:
            reason = (
                "No longer listed on the Bellhaven website, and %s occupies the "
                "same address under %s -- this looks like a sale of the facility."
                % (others[0].get("name"), others[0].get("parent_name"))
            )
        else:
            reason = (
                "No longer listed on the Bellhaven website and no other operator "
                "appears at this address; likely closed or divested."
            )
        note = reason
        if has_ar:
            note += (
                " Account preserved rather than deactivated: %s of AR is still "
                "outstanding." % account.get("outstanding_ar")
            )
        note += " Flagged by the website sync on %s." % today

        if (account.get("status") or "") == "Needs Review":
            continue
        add(
            "divested",
            account["account_id"],
            [{"op": "patch", "account_id": account["account_id"],
              "fields": {"status": "Needs Review", "note": note}}],
            title="Flag %s for review" % account.get("name"),
            subject=account.get("name"),
            slug="",
            account_id=account["account_id"],
            tier="absent-from-site",
            score=0.0,
            confidence="medium",
            rationale=reason,
            evidence={
                "site": None,
                "crm": _account_view(account),
                "candidates": [_account_view(o) for o in others],
            },
            field_labels={"status": "status"},
        )

    order = {kind: position for position, kind in enumerate(KIND_ORDER)}
    proposals.sort(
        key=lambda p: (order.get(p["kind"], 99), p.get("subject") or "")
    )
    return proposals, matches, missing
