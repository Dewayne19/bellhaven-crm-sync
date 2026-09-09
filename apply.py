"""Apply approved proposals to the CRM.

Nothing here selects work: it only executes what a reviewer has already
approved. Operations inside one proposal run in order and can pass values to
each other, which is how a change of ownership creates the new account and
then points the old one at it.

Run with --dry-run to print the exact calls without sending them.
"""

import sys

import store
from crm import Crm, CrmError
from normalize import norm_street, norm_zip


def _resolve(value, bindings):
    """Substitute a value produced by an earlier op in the same proposal."""
    if isinstance(value, str) and value.startswith("$"):
        name = value[1:]
        if name not in bindings:
            raise CrmError("unresolved reference %s" % value)
        return bindings[name]
    return value


def _created_id(response):
    """Pull the new account id out of whichever envelope the API returns."""
    if not isinstance(response, dict):
        return ""
    if response.get("account_id"):
        return response["account_id"]
    data = response.get("data")
    if isinstance(data, dict):
        return data.get("account_id") or ""
    return ""


def _find_existing(client, fields):
    """Look for an account this pipeline already created for a facility.

    Creation is the one operation the API cannot undo, so it is guarded on
    both sides: before creating, in case an earlier run got part way through,
    and afterwards, in case the response envelope hides the new id. The match
    is on normalized street, postcode and parent, which is the same identity
    rule the matcher uses.
    """
    street = fields.get("billing_street") or ""
    zip_code = fields.get("billing_zip") or ""
    if not street or not zip_code:
        return ""
    try:
        found = client.search_accounts(street=street, zip_code=zip_code)
    except CrmError:
        return ""
    for account in found:
        same_place = (
            norm_street(account.get("billing_street")) == norm_street(street)
            and norm_zip(account.get("billing_zip")) == norm_zip(zip_code)
        )
        same_parent = (account.get("parent_id") or "") == (
            fields.get("parent_id") or ""
        )
        if same_place and same_parent:
            return account.get("account_id") or ""
    return ""


def apply_proposal(client, proposal):
    bindings = {}
    results = []
    for op in proposal["ops"]:
        fields = {
            name: _resolve(value, bindings)
            for name, value in (op.get("fields") or {}).items()
        }
        kind = op.get("op")

        if kind == "create":
            existing = "" if client.dry_run else _find_existing(client, fields)
            if existing:
                new_id = existing
                results.append(
                    {
                        "op": "create",
                        "account_id": new_id,
                        "fields": fields,
                        "reused": True,
                    }
                )
            else:
                response = client.create_account(fields)
                new_id = _created_id(response)
                if not new_id and not client.dry_run:
                    new_id = _find_existing(client, fields)
                results.append(
                    {"op": "create", "account_id": new_id, "fields": fields}
                )

            if op.get("bind"):
                if not new_id:
                    if not client.dry_run:
                        raise CrmError(
                            "created the account but could not determine its id; "
                            "resolve by hand before retrying"
                        )
                    new_id = "<new-account-id>"
                bindings[op["bind"]] = new_id

        elif kind == "patch":
            account_id = _resolve(op.get("account_id"), bindings)
            client.update_account(account_id, fields)
            results.append(
                {"op": "patch", "account_id": account_id, "fields": fields}
            )

        else:
            raise CrmError("unknown operation %r" % (kind,))

    return results


def run(dry_run=False, limit=None):
    """Apply every approved, not-yet-applied proposal. Returns a summary."""
    client = Crm(dry_run=dry_run)
    connection = store.connect()
    queue = store.approved_unapplied(connection)
    if limit:
        queue = queue[:limit]

    applied, failed, log = 0, 0, []
    for proposal in queue:
        try:
            results = apply_proposal(client, proposal)
        except CrmError as exc:
            failed += 1
            log.append(
                {
                    "key": proposal["key"],
                    "title": proposal["title"],
                    "ok": False,
                    "error": str(exc),
                }
            )
            if not dry_run:
                # Leave it approved so it can be retried once the cause is fixed.
                store.mark_failed(connection, proposal["key"], str(exc))
            continue

        applied += 1
        log.append(
            {
                "key": proposal["key"],
                "title": proposal["title"],
                "ok": True,
                "results": results,
            }
        )
        if not dry_run:
            store.mark_applied(connection, proposal["key"], results)

    return {
        "dry_run": dry_run,
        "applied": applied,
        "failed": failed,
        "queued": len(queue),
        "log": log,
    }


def main(argv=None):
    args = list(argv if argv is not None else sys.argv[1:])
    dry_run = "--dry-run" in args
    summary = run(dry_run=dry_run)

    if not summary["queued"]:
        print("Nothing approved is waiting to be applied.")
        return 0

    for entry in summary["log"]:
        if entry["ok"]:
            for result in entry["results"]:
                print(
                    "  %-6s %-20s %s"
                    % (
                        result["op"],
                        result["account_id"],
                        ", ".join(sorted(result["fields"])),
                    )
                )
            print("ok     %s" % entry["title"])
        else:
            print("FAILED %s -- %s" % (entry["title"], entry["error"]))

    print(
        "\n%s%d applied, %d failed, out of %d approved."
        % (
            "[dry run] " if dry_run else "",
            summary["applied"],
            summary["failed"],
            summary["queued"],
        )
    )
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
