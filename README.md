# Bellhaven website / CRM sync

Keeps the CRM's picture of which facilities Bellhaven Senior Living owns in
step with the operator's public website. It scrapes the site, matches each
community to a CRM account, classifies what is wrong, and puts every proposed
change in front of a reviewer. Only approved changes are written back.

The first run against the uncorrected CRM raised 35 proposals; all 35 were
reviewed, approved and applied. Re-running now matches all 35 communities on
exact address and proposes nothing. See [DECISIONS.md](DECISIONS.md) for what
changed and why, and `python pipeline.py audit` to verify it independently.

## Setup

```
pip install -r requirements.txt
cp .env.example .env        # then paste your CRM token into it
```

## Running it

```
python pipeline.py propose          # scrape, match, refresh the review queue
python pipeline.py review           # review app on http://127.0.0.1:5000
python pipeline.py apply --dry-run  # print the calls without sending them
python pipeline.py apply            # write approved changes to the CRM
python pipeline.py status           # queue counts
python pipeline.py audit            # verify the CRM end state independently
python pipeline.py log              # export the decision history to DECISIONS.md
python -m unittest test_sync        # tests
```

`propose` and `status` never write. `apply` only ever touches proposals a
reviewer approved in the app.

## How matching works

Addresses in this CRM are typed by hand, so nothing can be compared raw:
`4930 W Lake Rd` and `4930 West Lake Road` are the same building. Everything
is normalized first — street suffixes and directionals reduced to one
spelling, postcodes to five digits, care types mapped between the two
vocabularies.

Names are worse than useless on their own. `Bellhaven of Carlisle` in Carlisle
PA scores 0.90 against `Bellhaven of New Carlisle` in New Carlisle OH, which
carries $156,000 of revenue, and there is an `Amberly Manor` in the CRM sitting
in Colorado Springs while the website's is in Hudson, Ohio. So **every tier is
gated on geography** and a name is only ever trusted inside a postcode or town
that already agrees. The counts below are from the first run, before any
corrections had been applied:

| Tier | Rule | What it catches |
| --- | --- | --- |
| `address` | normalized street + postcode | the ordinary case: 29 of 35 on the first run, 35 of 35 now |
| `street+city` | street, town, state agree; postcode does not | Portsmouth, whose CRM postcode is transposed (45626 for 45662) |
| `zip+name` | postcode agrees, name ≥ 0.88 | Ashtabula, where the CRM holds `PO Box 517` instead of a street |
| `weak` | same town, name 0.70–0.88 | surfaced for a human, never applied automatically |

When several accounts share one address they are one facility recorded several
times. The survivor is chosen by financial history first — the billing team
needs whichever account holds the revenue and AR — then closeness to Bellhaven
in the parent tree, then agreement with the website name, then which record is
more completely filled in, and finally the lowest account id so that genuine
twins resolve the same way on every run.

## What the first run proposed

All of these were approved and applied, which is why a re-run is now silent.

| Kind | Count | Meaning |
| --- | --- | --- |
| `chow` | 2 | Change of ownership under the SOP: new account created, old one preserved |
| `reparent` | 4 | Filed under the wrong parent, no AR to protect, moved directly |
| `duplicate` | 7 | Same building recorded twice; loser points at survivor and goes inactive |
| `divested` | 3 | Under Bellhaven but gone from the website; flagged, never deleted |
| `create` | 4 | On the website with no CRM account |
| `field_update` | 15 | Matched confidently, some values stale |

## Decisions worth knowing about

**The CHOW test is read strictly.** The SOP says revenue history *and*
outstanding AR above zero, so both must be true. That makes Tiffin
($84,000 / $12,400) and Marietta ($51,250 / $3,800) changes of ownership, while
Bellhaven Crossings of Lima — $47,000 of revenue but nothing outstanding — is
re-parented in place. Lima is the case that turns on the conjunction, and it is
worth confirming that reading is what the billing team means.

**A preserved account gains only the pointer.** The SOP says to leave the old
account exactly as it is, so a CHOW sets `chow_current_account` and nothing
else. The explanation of what happened goes in the new account's note instead.

**Divestitures are flagged, not deactivated.** `Bellhaven of Sandusky` is
absent from the website and `Millstone Care of Sandusky` now sits at the same
address, which reads as a sale. It also has $5,200 outstanding, so the account
is set to `Needs Review` with a note naming the buyer rather than being marked
inactive — the billing team still needs it. Alliance and Coldwater are absent
with no successor at their address, so they get the same flag with a different
note.

**Care types are mapped, not diffed.** The website says `Short-Term
Rehabilitation & Nursing` where the CRM says `Skilled Nursing`, and `Memory
Support` for `Memory Care`. Comparing them directly proposes a change on nearly
every facility; mapping them means no care-type proposals at all, which is the
right answer.

**Formatting-only differences are dropped.** A street that normalizes to the
same value produces no proposal. Names are an exception — the website is the
authority on what a facility is called, and an outdated name is a real fix — so
a rename is proposed whenever the raw strings differ, tagged `low` confidence
when only the spelling moved (`Centre`/`Center`) and `high` when it is a
genuine rebrand (`Riverbend Manor Care Center` → `Bellhaven of Chagrin Falls`).

**Phone numbers are proposed but marked low.** On the first run nine agreed
with the website and thirteen did not. The site is the operator's own published
number so it is probably the fresher of the two, but it is presentation rather
than ownership, so those land as low confidence and can be bulk-rejected
without touching anything that matters. Here they were approved.

**The scraper crawls more than the index.** `Bellhaven Meadows of Findlay` is
linked only from the home page, never from the paginated `/communities` list.
Walking the index alone finds 34 communities and silently misses it — and it
happens to be the one account in the CRM with no parent at all. Discovery
therefore reads the home and about pages too.

## Re-running safely

A proposal is identified by a hash of the operations it would perform, stored
in `data/state.sqlite` with its decision. That gives three properties:

- An approved-and-applied proposal is not raised again.
- A **rejected** proposal is not raised again either. Saying no is a decision
  and it sticks.
- Records retired by an earlier run drop out of the match index entirely.
  Without this, the old side of a completed change of ownership still holds the
  revenue history, wins survivor selection a second time, and gets proposed for
  another CHOW. This was a real bug during development and there is a test for
  it now.

Account creation is the one operation the API cannot undo, so it is guarded on
both sides: before creating, in case an earlier run got part way through, and
afterwards in case the response does not carry the new id. Both use the same
street/postcode/parent identity rule as the matcher.

Pending proposals that stop being generated — because someone fixed the record
by hand, or the website changed — are retired as obsolete rather than left in
the queue.

## Daily schedule

`.github/workflows/daily.yml` runs `propose` at 07:00 New York on a cron and
uploads the refreshed queue as an artifact. It deliberately does **not** apply
anything; writing stays behind the review app. The decision ledger is carried
between runs in the Actions cache, which is the cheapest thing that works here
— in production it belongs in a real database.

Equivalent crontab entry:

```
0 7 * * *  cd /srv/bellhaven-sync && /usr/bin/python3 pipeline.py propose >> log/sync.log 2>&1
```

## Verifying the result

`python pipeline.py audit` is the one to run. It ignores the decision ledger
and the pipeline entirely, pulls the live CRM and the live website, and checks
the invariants that should hold once the corrections are in:

- every published community resolves to exactly one live account, under Bellhaven
- no two live Bellhaven accounts describe the same building
- every preserved account keeps its parent, its revenue and its AR, and points
  at a live successor under Bellhaven
- every retired duplicate is inactive and resolves to a live survivor
- nothing Bellhaven owns was deactivated while money was outstanding
- anything under Bellhaven but missing from the website is flagged for review

It exits non-zero on any breach, so it doubles as a CI gate. It also reports
problems it finds outside Bellhaven's estate without counting them as
failures — `Harvest Hill Estates` sits under a competitor parent, inactive with
$4,000 outstanding, and was already that way in the seed data.

[DECISIONS.md](DECISIONS.md) is the readable export of the ledger: all 35
changes, the reasoning behind each, and anything declined.

## Layout

```
config.py      settings and thresholds
normalize.py   address, name and care-type normalization
scrape.py      website scraper
match.py       tiered, geography-gated matching
classify.py    matches -> proposals with operations and evidence
store.py       SQLite decision ledger
apply.py       executes approved proposals
audit.py       independent end-state verification
decisions.py   ledger -> DECISIONS.md
pipeline.py    CLI
review/        Flask review app
test_sync.py   tests, one per trap in the data
```

## What I would build next

- **Confirm the CHOW conjunction with billing.** Lima hinges on it, and one
  sentence from them settles whether revenue alone should also trigger it.
- **Split field proposals by materiality.** Approving a proposal currently
  accepts all of its fields; a stale name and a stale phone should be separately
  approvable.
- **Track website history.** Snapshots are overwritten, so a facility that
  vanishes for one day and returns looks identical to a real divestiture.
  Keeping dated snapshots would let the divestiture rule require a few days of
  absence before flagging.
- **Contacts.** The API exposes contacts and the website publishes an
  administrator per community, which is an obvious next sync.
- **Alert on shape changes.** If the scraper suddenly finds 3 communities
  instead of 35, that is a site redesign, not 32 divestitures. A run that
  proposes a large fraction of the portfolio should refuse to queue and page
  someone instead.
