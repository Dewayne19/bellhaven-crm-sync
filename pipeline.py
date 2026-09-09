"""Command line entry point for the Bellhaven website/CRM sync.

    python pipeline.py propose     scrape, match, refresh the review queue
    python pipeline.py status      queue and last-run summary
    python pipeline.py apply       push approved changes to the CRM
    python pipeline.py audit       verify the CRM end state independently
    python pipeline.py log         export the decision history to DECISIONS.md
    python pipeline.py review      serve the review app

Only `apply` writes to the CRM, and only for proposals a reviewer approved.
"""

import argparse
import json
import sys
from collections import Counter

import apply as apply_command
import audit as audit_command
import classify
import config
import crm
import scrape
import store


def _load_snapshot(use_cache):
    if use_cache and config.SNAPSHOT_PATH.exists():
        snapshot = json.loads(config.SNAPSHOT_PATH.read_text(encoding="utf-8"))
        print(
            "using cached snapshot from %s (%d communities)"
            % (snapshot.get("scraped_at"), snapshot.get("count", 0))
        )
        return snapshot
    snapshot = scrape.scrape()
    config.SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print("scraped %d communities from %s" % (snapshot["count"], config.SITE_BASE))
    return snapshot


def cmd_propose(args):
    snapshot = _load_snapshot(args.cached)
    client = crm.Crm()
    accounts = client.list_accounts()
    print("loaded %d CRM accounts" % len(accounts))

    proposals, matches, missing = classify.build(accounts, snapshot["communities"])

    tiers = Counter(m.tier or "no match" for m in matches)
    print(
        "\nmatching: "
        + ", ".join("%s=%d" % pair for pair in sorted(tiers.items()))
    )
    print("under Bellhaven but absent from the website: %d" % len(missing))

    connection = store.connect()
    added, obsoleted = store.sync(
        connection, proposals, len(snapshot["communities"]), len(accounts)
    )

    kinds = Counter(p["kind"] for p in proposals)
    print("\nproposals generated: %d" % len(proposals))
    for kind, total in sorted(kinds.items()):
        print("  %-13s %d" % (kind, total))
    print("\n%d new to review, %d retired as obsolete" % (added, obsoleted))
    _print_queue(connection)
    return 0


def _print_queue(connection):
    summary = store.counts(connection)
    print(
        "queue: %d pending, %d approved, %d rejected, %d applied, %d obsolete"
        % (
            summary.get("pending", 0),
            summary.get("approved", 0),
            summary.get("rejected", 0),
            summary.get("applied", 0),
            summary.get("obsolete", 0),
        )
    )


def cmd_status(args):
    connection = store.connect()
    _print_queue(connection)
    run = store.last_run(connection)
    if run:
        print(
            "last run %s: %d communities, %d accounts, %d proposals (%d new)"
            % (
                run["ran_at"],
                run["communities"],
                run["accounts"],
                run["proposed"],
                run["added"],
            )
        )
    waiting = store.pending(connection)
    if waiting:
        print("\npending by kind:")
        for kind, total in sorted(Counter(p["kind"] for p in waiting).items()):
            print("  %-13s %d" % (kind, total))
    return 0


def cmd_apply(args):
    return apply_command.main(["--dry-run"] if args.dry_run else [])


def cmd_audit(args):
    return audit_command.main(use_cached=args.cached)


def cmd_log(args):
    import decisions

    path = decisions.export()
    print("wrote %s" % path)
    return 0


def cmd_review(args):
    from review.app import create_app

    app = create_app()
    print("review app on http://127.0.0.1:%d" % args.port)
    app.run(host="127.0.0.1", port=args.port, debug=False)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    propose = sub.add_parser("propose", help="refresh the review queue")
    propose.add_argument(
        "--cached",
        action="store_true",
        help="reuse the stored website snapshot instead of scraping again",
    )
    propose.set_defaults(func=cmd_propose)

    status = sub.add_parser("status", help="show queue counts")
    status.set_defaults(func=cmd_status)

    apply_parser = sub.add_parser("apply", help="apply approved proposals")
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.set_defaults(func=cmd_apply)

    audit_parser = sub.add_parser(
        "audit", help="verify the CRM end state against the website and the SOP"
    )
    audit_parser.add_argument(
        "--cached",
        action="store_true",
        help="reuse the stored website snapshot instead of scraping again",
    )
    audit_parser.set_defaults(func=cmd_audit)

    log_parser = sub.add_parser("log", help="export the decision history")
    log_parser.set_defaults(func=cmd_log)

    review = sub.add_parser("review", help="serve the review app")
    review.add_argument("--port", type=int, default=5000)
    review.set_defaults(func=cmd_review)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
