# Decision log

Every change made to the CRM, why it was made, and what was declined.
Generated from the decision ledger with `python pipeline.py log`.

| | |
| --- | --- |
| Applied | 35 |
| Rejected | 0 |
| Still pending | 0 |
| Last pipeline run | 2026-09-09T18:22:26+00:00 |
| Scope of last run | 35 communities, 127 CRM accounts |

Applied by kind: chow 2, reparent 4, duplicate 7, divested 3, create 4, field_update 15

## Change of ownership (2)

**Change of ownership: Bellhaven of Marietta**

- Why: Now listed under Bellhaven but the CRM account sits under Cedar Trail Communities (Parent Account) and carries revenue of 51250 with 3800 still outstanding, so the SOP requires a new account rather than a re-parent.
- Matched on: address (score 1.00), high confidence
- Change: create account under Bellhaven; 001A34WFSUYHCRBLFT: chow_current_account -> $new_account
- Applied: 2026-09-09T18:21:43+00:00

**Change of ownership: Bellhaven of Tiffin**

- Why: Now listed under Bellhaven but the CRM account sits under Cedar Trail Communities (Parent Account) and carries revenue of 84000 with 12400 still outstanding, so the SOP requires a new account rather than a re-parent.
- Matched on: address (score 1.00), high confidence
- Change: create account under Bellhaven; 001U6RW32TY0WSXZZB: chow_current_account -> $new_account
- Applied: 2026-09-09T18:21:44+00:00

## Re-parented to Bellhaven (4)

**Re-parent Bellhaven Crossings of Lima to Bellhaven**

- Why: Listed on the Bellhaven website; the CRM still has it under Harborview Care Group (Parent Account). No outstanding AR, so the existing account moves directly.
- Matched on: address (score 1.00), high confidence
- Change: 001LGFPBJY4N9MB6KL: parent_id -> 0015QAPLGS3FVYEEEM, phone -> (231) 539-3617
- Applied: 2026-09-09T18:21:59+00:00

**Re-parent Bellhaven Meadows of Findlay to Bellhaven**

- Why: Listed on the Bellhaven website; the CRM still has it under no parent. No outstanding AR, so the existing account moves directly.
- Matched on: address (score 1.00), high confidence
- Change: 001UKEFGADQ8YCZ4YM: parent_id -> 0015QAPLGS3FVYEEEM, phone -> (231) 533-2969
- Applied: 2026-09-09T18:22:02+00:00

**Re-parent Kettering Care Centre to Bellhaven**

- Why: Listed on the Bellhaven website; the CRM still has it under Harborview Care Group (Parent Account). No outstanding AR, so the existing account moves directly.
- Matched on: address (score 0.65), high confidence
- Change: 001WR41PYNWXCAE2X4: name -> Bellhaven of Kettering, parent_id -> 0015QAPLGS3FVYEEEM, phone -> (231) 269-5449
- Applied: 2026-09-09T18:22:06+00:00

**Re-parent Cedar Trail of Zanesville to Bellhaven**

- Why: Listed on the Bellhaven website; the CRM still has it under Cedar Trail Communities (Parent Account). No outstanding AR, so the existing account moves directly.
- Matched on: address (score 0.62), high confidence
- Change: 001H1JMVZWP46D5VUF: name -> Bellhaven of Zanesville, parent_id -> 0015QAPLGS3FVYEEEM, phone -> (814) 599-2533
- Applied: 2026-09-09T18:22:10+00:00

## Duplicate retired (7)

**Retire duplicate Cedar Trail of Monroe**

- Why: Shares a street address and postcode with Bellhaven Gardens of Monroe, which is kept because it sits closest to Bellhaven in the parent tree.
- Matched on: address (score 1.00), high confidence
- Change: 0011AB44D05WLA9HTX: duplicate_of_account -> 001U1750VLVJAGG1S5, status -> Inactive
- Applied: 2026-09-09T18:21:48+00:00

**Retire duplicate Monroe Gardens Care Center**

- Why: Shares a street address and postcode with Bellhaven Gardens of Monroe, which is kept because it sits closest to Bellhaven in the parent tree.
- Matched on: address (score 1.00), high confidence
- Change: 00159PL81N38KM4FHM: duplicate_of_account -> 001U1750VLVJAGG1S5, status -> Inactive
- Applied: 2026-09-09T18:21:48+00:00

**Retire duplicate Harborview Shores of Erie**

- Why: Shares a street address and postcode with Bellhaven Shores of Erie, which is kept because it sits closest to Bellhaven in the parent tree.
- Matched on: address (score 1.00), high confidence
- Change: 001BLYF02K97SZLZHH: duplicate_of_account -> 001CVBBCSDM7YHN220, status -> Inactive
- Applied: 2026-09-09T18:21:49+00:00

**Retire duplicate Kettering Nursing & Rehabilitation**

- Why: Shares a street address and postcode with Kettering Care Centre, which is kept because it sits closest to Bellhaven in the parent tree.
- Matched on: address (score 0.65), high confidence
- Change: 0016KTS1UAWBRXS09J: duplicate_of_account -> 001WR41PYNWXCAE2X4, status -> Inactive
- Applied: 2026-09-09T18:21:49+00:00

**Retire duplicate Kettering Senior Campus**

- Why: Shares a street address and postcode with Kettering Care Centre, which is kept because it sits closest to Bellhaven in the parent tree.
- Matched on: address (score 0.65), high confidence
- Change: 001B7XZAA3AFALS9GP: duplicate_of_account -> 001WR41PYNWXCAE2X4, status -> Inactive
- Applied: 2026-09-09T18:21:49+00:00

**Retire duplicate Bellhaven of Owosso**

- Why: Shares a street address and postcode with Bellhaven of Owosso, which is kept because it sits closest to Bellhaven in the parent tree.
- Matched on: address (score 1.00), high confidence
- Change: 001QU150PM4Z15UA71: duplicate_of_account -> 001EGU7BMJ942ZTRE6, status -> Inactive
- Applied: 2026-09-09T18:21:50+00:00

**Retire duplicate Harborview Nursing & Rehab of Port Clinton**

- Why: Shares a street address and postcode with Bellhaven of Port Clinton, which is kept because it sits closest to Bellhaven in the parent tree.
- Matched on: address (score 1.00), high confidence
- Change: 001JD2MWRA74LTSN24: duplicate_of_account -> 001UELXDAKFRKB8932, status -> Inactive
- Applied: 2026-09-09T18:21:50+00:00

## Flagged for review (3)

**Flag Bellhaven Care Center of Alliance for review**

- Why: No longer listed on the Bellhaven website and no other operator appears at this address; likely closed or divested.
- Matched on: absent-from-site (score 0.00), medium confidence
- Change: 00116ETS45BL7DTQP7: status -> Needs Review
- Applied: 2026-09-09T18:21:47+00:00

**Flag Bellhaven of Coldwater for review**

- Why: No longer listed on the Bellhaven website and no other operator appears at this address; likely closed or divested.
- Matched on: absent-from-site (score 0.00), medium confidence
- Change: 0016PVXH4B25HWR7QE: status -> Needs Review
- Applied: 2026-09-09T18:21:47+00:00

**Flag Bellhaven of Sandusky for review**

- Why: No longer listed on the Bellhaven website, and Millstone Care of Sandusky occupies the same address under Millstone Health Partners (Parent Account) -- this looks like a sale of the facility.
- Matched on: absent-from-site (score 0.00), medium confidence
- Change: 001SXSF4ELF0Z2LGDM: status -> Needs Review
- Applied: 2026-09-09T18:21:47+00:00

## Account created (4)

**Create account for Amberly Manor**

- Why: no CRM account shares this address, postcode or town
- Matched on: none (score 0.00), medium confidence
- Change: create account under Bellhaven
- Applied: 2026-09-09T18:21:45+00:00

**Create account for Bellhaven at Union Square**

- Why: same town but the address differs; too weak to act on automatically
- Matched on: weak (score 0.71), low confidence
- Change: create account under Bellhaven
- Applied: 2026-09-09T18:21:45+00:00

**Create account for Bellhaven of Batavia**

- Why: no CRM account shares this address, postcode or town
- Matched on: none (score 0.00), medium confidence
- Change: create account under Bellhaven
- Applied: 2026-09-09T18:21:24+00:00

**Create account for Bellhaven of Carlisle**

- Why: no CRM account shares this address, postcode or town
- Matched on: none (score 0.00), medium confidence
- Change: create account under Bellhaven
- Applied: 2026-09-09T18:21:46+00:00

## Fields corrected (15)

**Update Bellhaven Gardens of Monroe**

- Why: Matched on street and postcode match exactly after normalization. The website disagrees with the CRM on: phone.
- Matched on: address (score 1.00), low confidence
- Change: 001U1750VLVJAGG1S5: phone -> (814) 412-2218
- Applied: 2026-09-09T18:21:50+00:00

**Update Bellhaven Health Care Center of Ashland**

- Why: Matched on street and postcode match exactly after normalization. The website disagrees with the CRM on: phone, spelling.
- Matched on: address (score 1.00), low confidence
- Change: 001RJ0D7Z5MAZN5HX5: name -> Bellhaven Healthcare Centre of Ashland, phone -> (517) 314-5115
- Applied: 2026-09-09T18:21:51+00:00

**Update Bellhaven Rehab and Nursing of Grove City**

- Why: Matched on street and postcode match exactly after normalization. The website disagrees with the CRM on: spelling.
- Matched on: address (score 1.00), low confidence
- Change: 001TZCSTBZFM6K5BGN: name -> Bellhaven Rehabilitation & Nursing of Grove City
- Applied: 2026-09-09T18:21:51+00:00

**Update Bellhaven Shores of Erie**

- Why: Matched on street and postcode match exactly after normalization. The website disagrees with the CRM on: phone.
- Matched on: address (score 1.00), low confidence
- Change: 001CVBBCSDM7YHN220: phone -> (614) 792-9343
- Applied: 2026-09-09T18:21:51+00:00

**Update Sunny Acres Retirement Home**

- Why: Matched on street and postcode match exactly after normalization. The website disagrees with the CRM on: phone, rename.
- Matched on: address (score 0.24), high confidence
- Change: 0017MN2JYAJBDS8WQZ: name -> Bellhaven Willow Creek, phone -> (419) 394-5494
- Applied: 2026-09-09T18:21:52+00:00

**Update Bellhaven of Sycamore Ridge**

- Why: Matched on street and postcode match exactly after normalization. The website disagrees with the CRM on: phone, spelling.
- Matched on: address (score 1.00), low confidence
- Change: 00191H7JR16471SZ34: name -> Bellhaven at Sycamore Ridge, phone -> (260) 365-6510
- Applied: 2026-09-09T18:21:52+00:00

**Update Bellhaven of Ashtabula**

- Why: Matched on same postcode and near-identical name; the CRM holds a PO box instead of the street address. The website disagrees with the CRM on: po box replaced.
- Matched on: zip+name (score 1.00), high confidence
- Change: 001NXP9X46CWEPSLSV: billing_street -> 3156 W Prospect Rd
- Applied: 2026-09-09T18:21:53+00:00

**Update Riverbend Manor Care Center**

- Why: Matched on street and postcode match exactly after normalization. The website disagrees with the CRM on: phone, rename.
- Matched on: address (score 0.32), high confidence
- Change: 001RJU1X4NBWC1Q0G7: name -> Bellhaven of Chagrin Falls, phone -> (231) 283-7448
- Applied: 2026-09-09T18:21:53+00:00

**Update Chesterton Senior Commons**

- Why: Matched on street and postcode match exactly after normalization. The website disagrees with the CRM on: rename.
- Matched on: address (score 0.44), high confidence
- Change: 0013NUZQHQUEZ8DXEG: name -> Bellhaven of Chesterton
- Applied: 2026-09-09T18:21:53+00:00

**Update Bellhaven of Defiance**

- Why: Matched on street and postcode match exactly after normalization. The website disagrees with the CRM on: phone.
- Matched on: address (score 1.00), low confidence
- Change: 001R4PXTUD9R6FNN8V: phone -> (330) 691-2711
- Applied: 2026-09-09T18:21:54+00:00

**Update Bellhaven of Goshen**

- Why: Matched on street and postcode match exactly after normalization. The website disagrees with the CRM on: phone.
- Matched on: address (score 1.00), low confidence
- Change: 001JQER1RMYKNRLNME: phone -> (330) 405-6040
- Applied: 2026-09-09T18:21:02+00:00

**Update Bellhaven of Marion**

- Why: Matched on street and postcode match exactly after normalization. The website disagrees with the CRM on: phone.
- Matched on: address (score 1.00), low confidence
- Change: 0015L38R1Z5947ZZP7: phone -> (517) 847-7948
- Applied: 2026-09-09T18:21:54+00:00

**Update Bellhaven of Port Clinton**

- Why: Matched on street and postcode match exactly after normalization. The website disagrees with the CRM on: phone.
- Matched on: address (score 1.00), low confidence
- Change: 001UELXDAKFRKB8932: phone -> (330) 733-6423
- Applied: 2026-09-09T18:21:54+00:00

**Update Bellhaven of Portsmouth**

- Why: Matched on street, town and state agree; the CRM postcode disagrees and looks wrong. The website disagrees with the CRM on: postcode.
- Matched on: street+city (score 1.00), high confidence
- Change: 001CF3LDWVRGL09P4F: billing_zip -> 45662
- Applied: 2026-09-09T18:21:55+00:00

**Update Arbors at Bellhaven Dayton**

- Why: Matched on street and postcode match exactly after normalization. The website disagrees with the CRM on: phone, spelling.
- Matched on: address (score 1.00), low confidence
- Change: 0010KJFP601YNTZVDA: name -> The Arbors at Bellhaven - Dayton, phone -> (260) 254-7592
- Applied: 2026-09-09T18:21:55+00:00
