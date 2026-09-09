"""Independent verification of the CRM end state.

This does not read the decision ledger and does not trust the pipeline. It
pulls the live CRM and the live website and checks the invariants that should
hold once the corrections have been applied. A clean audit is the evidence
that the data is actually right, rather than that the run reported success.

    python pipeline.py audit

Exits non-zero if any invariant is broken, so it also works as a CI gate.
"""

import json
import sys

import config
import match
import scrape
from crm import Crm, is_facility
from match import is_superseded
from normalize import address_key

BELL = config.BELLHAVEN_PARENT_ID


class Result:
    def __init__(self):
        self.checks = []
        self.notes = []

    def add(self, name, failures, detail=""):
        self.checks.append(
            {"name": name, "failures": failures, "detail": detail}
        )

    def note(self, name, lines):
        """An observation outside this pipeline's remit. Never a failure."""
        if lines:
            self.notes.append({"name": name, "lines": lines})

    @property
    def broken(self):
        return sum(len(check["failures"]) for check in self.checks)

    def report(self):
        for check in self.checks:
            status = "PASS" if not check["failures"] else "FAIL"
            print("[%s] %s" % (status, check["name"]))
            if check["detail"] and not check["failures"]:
                print("       %s" % check["detail"])
            for line in check["failures"]:
                print("       %s" % line)
        for note in self.notes:
            print("[NOTE] %s" % note["name"])
            for line in note["lines"]:
                print("       %s" % line)
        print()
        if self.broken:
            print("%d problem(s) found." % self.broken)
        else:
            print("All checks passed.")
        return 0 if not self.broken else 1


def _load_communities(use_cached):
    if use_cached and config.SNAPSHOT_PATH.exists():
        return json.loads(config.SNAPSHOT_PATH.read_text(encoding="utf-8"))[
            "communities"
        ]
    return scrape.scrape()["communities"]


def audit(use_cached=False):
    client = Crm()
    accounts = client.list_accounts()
    communities = _load_communities(use_cached)

    by_id = {a["account_id"]: a for a in accounts}
    live = [a for a in accounts if is_facility(a) and not is_superseded(a)]
    index = match.Index(accounts)
    result = Result()

    # 1. Every published community resolves to exactly one live account, and
    #    that account sits under Bellhaven.
    failures = []
    for community in communities:
        key = address_key(community["street"], community["zip"])
        cluster = index.by_address.get(key, []) if key else []
        if len(cluster) != 1:
            failures.append(
                "%s -> %d live accounts at %s"
                % (community["name"], len(cluster), community["street"])
            )
        elif (cluster[0].get("parent_id") or "") != BELL:
            failures.append(
                "%s -> %s is under %s"
                % (
                    community["name"],
                    cluster[0]["name"],
                    cluster[0].get("parent_name") or "no parent",
                )
            )
    result.add(
        "every website community maps to one live Bellhaven account",
        failures,
        "%d communities checked" % len(communities),
    )

    # 2. No two live Bellhaven accounts describe the same building.
    seen, failures = {}, []
    for account in live:
        if (account.get("parent_id") or "") != BELL:
            continue
        key = address_key(account.get("billing_street"), account.get("billing_zip"))
        if not key:
            continue
        if key in seen:
            failures.append(
                "%s and %s share %s"
                % (seen[key], account["name"], account.get("billing_street"))
            )
        seen[key] = account["name"]
    result.add("no duplicate addresses under Bellhaven", failures)

    # 3. Change of ownership: the old record keeps its parent and its money,
    #    and points at a live successor under Bellhaven.
    failures, chow_count = [], 0
    for account in accounts:
        successor_id = (account.get("chow_current_account") or "").strip()
        if not successor_id:
            continue
        chow_count += 1
        successor = by_id.get(successor_id)
        if not successor:
            failures.append(
                "%s points at missing account %s" % (account["name"], successor_id)
            )
            continue
        if (successor.get("parent_id") or "") != BELL:
            failures.append(
                "%s: successor %s is not under Bellhaven"
                % (account["name"], successor["name"])
            )
        if (account.get("parent_id") or "") == BELL:
            failures.append(
                "%s: old record was re-parented; it should have been left alone"
                % account["name"]
            )
        if (account.get("lifetime_revenue") or 0) <= 0 or (
            account.get("outstanding_ar") or 0
        ) <= 0:
            failures.append(
                "%s: kept as a CHOW but does not meet the revenue-and-AR test"
                % account["name"]
            )
    result.add(
        "changes of ownership preserve the billing record",
        failures,
        "%d preserved account(s)" % chow_count,
    )

    # 4. Retired duplicates are inactive and point somewhere real and live.
    failures, dup_count = [], 0
    for account in accounts:
        survivor_id = (account.get("duplicate_of_account") or "").strip()
        if not survivor_id:
            continue
        dup_count += 1
        survivor = by_id.get(survivor_id)
        if not survivor:
            failures.append(
                "%s points at missing account %s" % (account["name"], survivor_id)
            )
        elif is_superseded(survivor):
            failures.append(
                "%s points at %s, which is itself retired"
                % (account["name"], survivor["name"])
            )
        if account.get("status") != "Inactive":
            failures.append(
                "%s is marked a duplicate but status is %s"
                % (account["name"], account.get("status"))
            )
    result.add(
        "retired duplicates resolve to a live survivor",
        failures,
        "%d retired account(s)" % dup_count,
    )

    # 5. Nothing with money owed was switched off. Scoped to the accounts this
    #    pipeline is responsible for: Bellhaven's own, plus the records it
    #    retired or superseded. Competitor books are reported separately below
    #    rather than counted as failures against this run.
    def ours(account):
        return (
            (account.get("parent_id") or "") == BELL
            or (account.get("duplicate_of_account") or "").strip()
            or (account.get("chow_current_account") or "").strip()
        )

    owed_and_off = [
        a for a in accounts
        if a.get("status") == "Inactive" and (a.get("outstanding_ar") or 0) > 0
    ]
    result.add(
        "no Bellhaven account with open AR was deactivated",
        [
            "%s is Inactive with %s outstanding"
            % (a["name"], a.get("outstanding_ar"))
            for a in owed_and_off
            if ours(a)
        ],
    )
    result.note(
        "pre-existing data quality issues outside Bellhaven's estate",
        [
            "%s (%s) is Inactive with %s outstanding -- untouched by this "
            "pipeline, flagged for whoever owns that book"
            % (a["name"], a.get("parent_name") or "no parent", a.get("outstanding_ar"))
            for a in owed_and_off
            if not ours(a)
        ],
    )

    # 6. Anything still under Bellhaven but absent from the site is flagged.
    published = set()
    for community in communities:
        key = address_key(community["street"], community["zip"])
        for account in index.by_address.get(key, []) if key else []:
            published.add(account["account_id"])
    failures = [
        "%s is under Bellhaven, absent from the website, and still %s"
        % (a["name"], a.get("status"))
        for a in live
        if (a.get("parent_id") or "") == BELL
        and a["account_id"] not in published
        and a.get("status") != "Needs Review"
    ]
    result.add("facilities missing from the website are flagged for review", failures)

    return result


def main(use_cached=False):
    print("Auditing %s\n" % config.CRM_BASE)
    return audit(use_cached).report()


if __name__ == "__main__":
    sys.exit(main("--cached" in sys.argv[1:]))
