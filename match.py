"""Link website communities to CRM accounts.

Every tier is gated on geography. Names in this data set are actively
misleading -- "Bellhaven of Carlisle" (Carlisle PA) scores 0.90 against
"Bellhaven of New Carlisle" (New Carlisle OH), which carries real revenue --
so a name is only ever trusted inside an already-agreeing postcode or town.
"""

from collections import defaultdict

import config
from crm import is_facility
from normalize import (
    address_key,
    is_po_box,
    name_sim,
    norm_city,
    norm_state,
    norm_street,
    norm_zip,
)

TIER_ADDRESS = "address"
TIER_STREET_CITY = "street+city"
TIER_ZIP_NAME = "zip+name"
TIER_WEAK = "weak"

CONFIDENT_TIERS = (TIER_ADDRESS, TIER_STREET_CITY, TIER_ZIP_NAME)

_ACQUIRED_ORDER = list(config.ACQUIRED_PARENT_IDS)


def _financial_history(account):
    revenue = account.get("lifetime_revenue") or 0
    receivable = account.get("outstanding_ar") or 0
    return revenue + receivable > 0


def _parent_rank(account):
    """Preference order for which account survives a duplicate cluster.

    The Bellhaven account first, then accounts inherited through an
    acquisition (in the order those acquisitions happened), then orphans,
    then anything belonging to an unrelated operator.
    """
    parent = account.get("parent_id") or ""
    if parent == config.BELLHAVEN_PARENT_ID:
        return (0, 0)
    if parent in config.ACQUIRED_PARENT_IDS:
        return (1, _ACQUIRED_ORDER.index(parent))
    if not parent:
        return (2, 0)
    return (3, 0)


def is_superseded(account):
    """True for records already retired by a previous approved run.

    An account that points at a successor (chow_current_account) or at a
    surviving twin (duplicate_of_account) is history. Keeping these out of the
    match indexes is what makes re-runs idempotent: without it the old side of
    a completed change of ownership still holds the revenue history, wins
    survivor selection again, and gets proposed for a second CHOW.
    """
    return bool(
        (account.get("chow_current_account") or "").strip()
        or (account.get("duplicate_of_account") or "").strip()
    )


class Index:
    """Lookup structures over the live facility accounts held in the CRM."""

    def __init__(self, accounts):
        self.facilities = [
            a for a in accounts if is_facility(a) and not is_superseded(a)
        ]
        self.superseded = [
            a for a in accounts if is_facility(a) and is_superseded(a)
        ]
        self.by_id = {a["account_id"]: a for a in accounts}
        self.by_address = defaultdict(list)
        self.by_street_city = defaultdict(list)
        self.by_zip = defaultdict(list)
        self.by_city = defaultdict(list)

        for account in self.facilities:
            street = account.get("billing_street")
            zip_code = norm_zip(account.get("billing_zip"))
            city = norm_city(account.get("billing_city"))
            state = norm_state(account.get("billing_state"))

            key = address_key(street, zip_code)
            if key:
                self.by_address[key].append(account)
            if not is_po_box(street) and norm_street(street) and city and state:
                self.by_street_city[(norm_street(street), city, state)].append(account)
            if zip_code:
                self.by_zip[zip_code].append(account)
            if city and state:
                self.by_city[(city, state)].append(account)


class Match:
    def __init__(self, community, tier=None, cluster=None, survivor=None,
                 score=0.0, reason="", near_misses=None):
        self.community = community
        self.tier = tier
        self.cluster = cluster or []
        self.survivor = survivor
        self.score = score
        self.reason = reason
        self.near_misses = near_misses or []

    @property
    def confident(self):
        return self.tier in CONFIDENT_TIERS

    @property
    def duplicates(self):
        """Cluster members that lose to the survivor."""
        if not self.survivor:
            return []
        return [
            a for a in self.cluster
            if a["account_id"] != self.survivor["account_id"]
        ]


_COMPLETENESS_FIELDS = (
    "billing_street", "billing_city", "billing_state", "billing_zip",
    "care_type", "phone",
)


def _completeness(account):
    """How many meaningful fields are populated, for choosing between twins."""
    return sum(
        1 for field in _COMPLETENESS_FIELDS
        if (account.get(field) or "").strip()
    )


def pick_survivor(cluster, community):
    """Choose which of several accounts at one address is the real record.

    Financial history wins outright: the billing team needs whichever account
    carries the revenue and AR. After that comes closeness to Bellhaven in the
    parent tree, then agreement with the name on the website, then whichever
    record is more completely filled in. The final sort on account_id means
    genuine twins still resolve the same way on every run.
    """
    return sorted(
        cluster,
        key=lambda a: (
            0 if _financial_history(a) else 1,
            _parent_rank(a),
            -name_sim(a.get("name"), community["name"]),
            -_completeness(a),
            a.get("account_id") or "",
        ),
    )[0]


def _near_misses(index, community, limit=3):
    """Best same-state candidates, whether or not they cleared a threshold.

    Shown to the reviewer as the evidence behind a no-match call.
    """
    state = norm_state(community.get("state"))
    scored = []
    for account in index.facilities:
        if norm_state(account.get("billing_state")) != state:
            continue
        score = name_sim(account.get("name"), community["name"])
        if score > 0.3:
            scored.append((score, account))
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("account_id") or ""))
    return [
        {
            "account_id": account["account_id"],
            "name": account.get("name"),
            "street": account.get("billing_street"),
            "city": account.get("billing_city"),
            "state": account.get("billing_state"),
            "zip": account.get("billing_zip"),
            "parent_name": account.get("parent_name"),
            "score": score,
        }
        for score, account in scored[:limit]
    ]


def match_community(index, community):
    street = community.get("street")
    zip_code = norm_zip(community.get("zip"))
    city = norm_city(community.get("city"))
    state = norm_state(community.get("state"))

    def build(tier, cluster, reason):
        survivor = pick_survivor(cluster, community)
        score = name_sim(survivor.get("name"), community["name"])
        return Match(community, tier, cluster, survivor, score, reason)

    key = address_key(street, zip_code)
    if key and index.by_address.get(key):
        return build(
            TIER_ADDRESS,
            index.by_address[key],
            "street and postcode match exactly after normalization",
        )

    structural = index.by_street_city.get((norm_street(street), city, state))
    if structural:
        return build(
            TIER_STREET_CITY,
            structural,
            "street, town and state agree; the CRM postcode disagrees and looks wrong",
        )

    named = [
        a for a in index.by_zip.get(zip_code, [])
        if name_sim(a.get("name"), community["name"]) >= config.NAME_STRONG
    ]
    if named:
        reason = "same postcode and near-identical name"
        if any(is_po_box(a.get("billing_street")) for a in named):
            reason += "; the CRM holds a PO box instead of the street address"
        return build(TIER_ZIP_NAME, named, reason)

    weak = [
        (name_sim(a.get("name"), community["name"]), a)
        for a in index.by_city.get((city, state), [])
    ]
    weak = [
        pair for pair in weak
        if config.NAME_WEAK <= pair[0] < config.NAME_STRONG
    ]
    if weak:
        weak.sort(key=lambda pair: (-pair[0], pair[1].get("account_id") or ""))
        best = weak[0][1]
        return Match(
            community,
            TIER_WEAK,
            [best],
            best,
            weak[0][0],
            "same town but the address differs; too weak to act on automatically",
            _near_misses(index, community),
        )

    return Match(
        community,
        None,
        [],
        None,
        0.0,
        "no CRM account shares this address, postcode or town",
        _near_misses(index, community),
    )


def match_all(accounts, communities):
    """Return (matches, accounts_under_bellhaven_missing_from_site, index)."""
    index = Index(accounts)
    matches = [match_community(index, community) for community in communities]

    claimed = {
        account["account_id"]
        for m in matches
        if m.confident
        for account in m.cluster
    }
    missing = [
        account for account in index.facilities
        if account["account_id"] not in claimed
        and (account.get("parent_id") or "") == config.BELLHAVEN_PARENT_ID
    ]
    missing.sort(key=lambda a: a.get("name") or "")
    return matches, missing, index
