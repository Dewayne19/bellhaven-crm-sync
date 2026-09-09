# Writeup

## Matching approach

Addresses in the CRM are hand-typed, so nothing compares raw — `4930 W Lake Rd`
and `4930 West Lake Road` are one building. I normalize street suffixes and
directionals, postcodes, and care vocabularies first, then match in four tiers.

Names turned out to be actively dangerous, so **every tier is gated on
geography** and a name is only trusted inside a postcode or town that already
agrees. Two cases forced that: `Bellhaven of Carlisle` (Carlisle PA) scores 0.90
against `Bellhaven of New Carlisle` (New Carlisle OH), which holds $156k of
revenue; and there is an `Amberly Manor` in the CRM in Colorado Springs while
the website's is in Hudson, Ohio. Both would have been corrupted by name
similarity alone.

The tiers, in order: exact normalized street+postcode (35 of 35 after
correction); street+town+state when the postcode disagrees (caught Portsmouth,
whose CRM postcode was transposed to 45626); postcode+name ≥ 0.88 (caught
Ashtabula, where the CRM held `PO Box 517` instead of a street); and a weak
same-town tier that is surfaced to a human but never auto-applied.

Where several accounts share an address they are one facility recorded several
times. The survivor is chosen by financial history first — billing needs
whichever account holds the revenue and AR — then closeness to Bellhaven in the
parent tree, name agreement, record completeness, and finally lowest account id
so genuine twins resolve identically on every run.

## Judgement calls worth flagging

**The CHOW test is read strictly** as revenue history *and* outstanding AR both
above zero. That makes Tiffin and Marietta changes of ownership, while Bellhaven
Crossings of Lima — $47k revenue but nothing outstanding — re-parents in place.
Lima turns entirely on that conjunction and is the one reading I would confirm
with billing.

**Preserved accounts gain only the pointer.** The SOP says leave the old account
exactly as it is, so a CHOW sets `chow_current_account` and nothing else; the
explanation goes on the new account.

**Divestitures are flagged, not deactivated.** `Bellhaven of Sandusky` is gone
from the website and `Millstone Care of Sandusky` now occupies the same address.
It also carries $5,200 outstanding, so it is set to `Needs Review` with a note
naming the buyer rather than marked inactive — billing still needs it.

**Care types are mapped, not diffed.** The site says `Short-Term Rehabilitation
& Nursing` where the CRM says `Skilled Nursing`. Diffing them directly proposes
a change on nearly every facility; mapping them yields zero care-type proposals,
which is correct.

**Discovery crawls more than the index.** `Bellhaven Meadows of Findlay` is
linked only from the home page, so walking `/communities` alone finds 34 and
misses it — and it was the one account in the CRM with no parent at all.

## Re-runs

Proposals are keyed by a hash of the operations they would perform and stored
with their decision, so approved *and rejected* items are never raised twice.
Records retired by an earlier run drop out of the match index — without that,
the old side of a completed CHOW still holds the revenue, wins survivor
selection again, and gets proposed for a second CHOW. That was a real bug during
development and has a test now. Re-running against the corrected CRM produces
0 proposals.

## How I used AI tools

I used Claude Code throughout. I directed it to probe the live API and website
first rather than start from the brief, which is how the six data traps above
surfaced — the PO box, the transposed postcode, the cross-state name collision,
the Carlisle near-miss, the homepage-only listing, and the Sandusky sale. I made
the judgement calls on the CHOW conjunction, the divestiture-versus-duplicate
distinction, and the survivor-selection ordering, and had it write tests for
each trap so those decisions are pinned. Two bugs it introduced that I caught in
review: retired records staying in the match index (the double-CHOW above), and
a "nearest record" note that fired on same-state name noise and told Batavia its
nearest match was Ashtabula 200 miles away.

## What I would build next

Confirm the CHOW conjunction with billing. Make field proposals separately
approvable, so a stale name and a stale phone are not one decision. Keep dated
website snapshots, so a facility that vanishes for a day is distinguishable from
a real divestiture. Sync contacts, which the API exposes and the site publishes.
And refuse to queue when a run proposes a large fraction of the portfolio — if
the scraper finds 3 communities instead of 35 that is a site redesign, not 32
divestitures.

## Time spent

Roughly 2 hours.
