"""Tests for the parts that are easy to get quietly wrong.

Each case here is a trap that is actually present in the sandbox data, so a
regression shows up as a failing test rather than as a corrupted account.

    python -m unittest test_sync -v
"""

import unittest

import classify
import config
import match
import normalize


BELL = config.BELLHAVEN_PARENT_ID
HARBORVIEW = "001FJZYHR7MLFMNPLL"
CEDAR = "001FWSQ30SFW6S7604"
JUNIPER = "001DAAUWV2J3SHQJ34"


def account(account_id, name, street, city, state, zip_code, parent=BELL,
            revenue=0, receivable=0, care="Skilled Nursing", status="Active",
            chow="", duplicate_of=""):
    return {
        "account_id": account_id,
        "name": name,
        "parent_id": parent,
        "parent_name": "parent %s" % parent,
        "billing_street": street,
        "billing_city": city,
        "billing_state": state,
        "billing_zip": zip_code,
        "care_type": care,
        "status": status,
        "phone": "",
        "lifetime_revenue": revenue,
        "outstanding_ar": receivable,
        "chow_current_account": chow,
        "duplicate_of_account": duplicate_of,
        "note": "",
    }


def community(name, street, city, state, zip_code, care=None, phone="",
              slug=None):
    return {
        "slug": slug or name.lower().replace(" ", "-"),
        "url": "https://example.test/communities/x",
        "name": name,
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_code,
        "care_types": care if care is not None else ["Short-Term Rehabilitation & Nursing"],
        "phone": phone,
        "administrator": "",
    }


class Normalization(unittest.TestCase):
    def test_street_suffixes_and_directionals_collapse(self):
        self.assertEqual(
            normalize.norm_street("4930 West Lake Road"),
            normalize.norm_street("4930 W Lake Rd"),
        )
        self.assertEqual(
            normalize.norm_street("3313 Wilmington Pike"),
            normalize.norm_street("3313 Wilmington Pk"),
        )

    def test_po_box_is_not_an_address_key(self):
        self.assertTrue(normalize.is_po_box("PO Box 517"))
        self.assertIsNone(normalize.address_key("PO Box 517", "44004"))
        self.assertIsNotNone(normalize.address_key("3156 W Prospect Rd", "44004"))

    def test_spelling_variants_score_identical(self):
        self.assertEqual(
            normalize.name_sim(
                "Bellhaven Healthcare Centre of Ashland",
                "Bellhaven Health Care Center of Ashland",
            ),
            1.0,
        )

    def test_care_vocabularies_are_mapped_not_diffed(self):
        self.assertEqual(
            normalize.map_care_types(["Short-Term Rehabilitation & Nursing"]),
            ["Skilled Nursing"],
        )
        self.assertEqual(normalize.map_care_types(["Memory Support"]), ["Memory Care"])


class Matching(unittest.TestCase):
    def test_survivor_is_the_account_holding_the_money(self):
        cluster = [
            account("A1", "Twin One", "1 Main St", "Akron", "OH", "44301"),
            account("A2", "Twin Two", "1 Main St", "Akron", "OH", "44301",
                    revenue=50000, receivable=100),
        ]
        chosen = match.pick_survivor(cluster, community("Twin", "1 Main St", "Akron", "OH", "44301"))
        self.assertEqual(chosen["account_id"], "A2")

    def test_po_box_account_is_rescued_by_postcode_and_name(self):
        accounts = [account("A1", "Bellhaven of Ashtabula", "PO Box 517",
                            "Ashtabula", "OH", "44004")]
        site = [community("Bellhaven of Ashtabula", "3156 W Prospect Rd",
                          "Ashtabula", "OH", "44004")]
        matches, _, _ = match.match_all(accounts, site)
        self.assertEqual(matches[0].tier, match.TIER_ZIP_NAME)
        self.assertTrue(matches[0].confident)

    def test_wrong_postcode_is_rescued_by_street_and_town(self):
        accounts = [account("A1", "Bellhaven of Portsmouth", "2222 Gallia St",
                            "Portsmouth", "OH", "45626")]
        site = [community("Bellhaven of Portsmouth", "2222 Gallia St",
                          "Portsmouth", "OH", "45662")]
        matches, _, _ = match.match_all(accounts, site)
        self.assertEqual(matches[0].tier, match.TIER_STREET_CITY)

    def test_identical_name_in_another_state_is_not_a_match(self):
        accounts = [account("A1", "Amberly Manor", "918 S Nevada Ave",
                            "Colorado Springs", "CO", "80903", parent=JUNIPER)]
        site = [community("Amberly Manor", "4390 Darrow Rd", "Hudson", "OH", "44236")]
        matches, _, _ = match.match_all(accounts, site)
        self.assertIsNone(matches[0].tier)

    def test_similar_name_in_another_town_is_not_a_match(self):
        # 0.90 name similarity, and the CRM account carries real revenue.
        accounts = [account("A1", "Bellhaven of New Carlisle", "875 Elm St",
                            "New Carlisle", "OH", "45344", revenue=156000)]
        site = [community("Bellhaven of Carlisle", "640 Walnut Bottom Rd",
                          "Carlisle", "PA", "17015")]
        matches, _, _ = match.match_all(accounts, site)
        self.assertIsNone(matches[0].tier)

    def test_retired_records_leave_the_index(self):
        accounts = [
            account("OLD", "Old Account", "1 Main St", "Akron", "OH", "44301",
                    parent=CEDAR, revenue=8000, receivable=400, chow="NEW"),
            account("NEW", "New Account", "1 Main St", "Akron", "OH", "44301"),
        ]
        site = [community("New Account", "1 Main St", "Akron", "OH", "44301")]
        matches, _, index = match.match_all(accounts, site)
        self.assertEqual([a["account_id"] for a in index.facilities], ["NEW"])
        self.assertEqual(matches[0].survivor["account_id"], "NEW")
        self.assertEqual(matches[0].duplicates, [])


class Classification(unittest.TestCase):
    def test_revenue_with_open_ar_creates_a_new_account(self):
        accounts = [account("OLD", "Bellhaven of Tiffin", "45 St Lawrence Dr",
                            "Tiffin", "OH", "44883", parent=CEDAR,
                            revenue=84000, receivable=12400)]
        site = [community("Bellhaven of Tiffin", "45 St Lawrence Dr",
                          "Tiffin", "OH", "44883")]
        proposals, _, _ = classify.build(accounts, site)
        chow = [p for p in proposals if p["kind"] == "chow"]
        self.assertEqual(len(chow), 1)
        ops = chow[0]["ops"]
        self.assertEqual(ops[0]["op"], "create")
        self.assertEqual(ops[0]["fields"]["parent_id"], BELL)
        # The preserved account keeps its parent and gains only the pointer.
        self.assertEqual(ops[1]["account_id"], "OLD")
        self.assertEqual(list(ops[1]["fields"]), ["chow_current_account"])

    def test_revenue_without_open_ar_reparents_in_place(self):
        accounts = [account("A1", "Bellhaven Crossings of Lima", "3115 N Cole St",
                            "Lima", "OH", "45801", parent=HARBORVIEW,
                            revenue=47000, receivable=0)]
        site = [community("Bellhaven Crossings of Lima", "3115 N Cole St",
                          "Lima", "OH", "45801")]
        proposals, _, _ = classify.build(accounts, site)
        kinds = [p["kind"] for p in proposals]
        self.assertIn("reparent", kinds)
        self.assertNotIn("chow", kinds)

    def test_duplicate_points_at_the_survivor_and_goes_inactive(self):
        # Genuine twins: same name, same money, same parent. Nothing
        # distinguishes them, so the lowest account_id wins and the choice is
        # the same on every run.
        accounts = [
            account("A0001", "Bellhaven of Owosso", "1120 W Main St",
                    "Owosso", "MI", "48867", care="Assisted Living"),
            account("B0002", "Bellhaven of Owosso", "1120 West Main Street",
                    "Owosso", "MI", "48867", care="Assisted Living"),
        ]
        site = [community("Bellhaven of Owosso", "1120 W Main St",
                          "Owosso", "MI", "48867", care=["Assisted Living"])]
        proposals, _, _ = classify.build(accounts, site)
        dupes = [p for p in proposals if p["kind"] == "duplicate"]
        self.assertEqual(len(dupes), 1)
        fields = dupes[0]["ops"][0]["fields"]
        self.assertEqual(dupes[0]["account_id"], "B0002")
        self.assertEqual(fields["duplicate_of_account"], "A0001")
        self.assertEqual(fields["status"], "Inactive")

    def test_fuller_record_beats_a_sparser_twin(self):
        accounts = [
            account("A0001", "Twin", "1 Main St", "Akron", "OH", "44301",
                    care=""),
            account("B0002", "Twin", "1 Main St", "Akron", "OH", "44301",
                    care="Assisted Living"),
        ]
        accounts[1]["phone"] = "(216) 555-0100"
        site = [community("Twin", "1 Main St", "Akron", "OH", "44301",
                          care=["Assisted Living"])]
        chosen = match.pick_survivor(accounts, site[0])
        self.assertEqual(chosen["account_id"], "B0002")

    def test_matching_care_vocabulary_produces_no_proposal(self):
        accounts = [account("A1", "Bellhaven of Marion", "1 Main St", "Marion",
                            "OH", "43302", care="Skilled Nursing",
                            revenue=0, receivable=0)]
        site = [community("Bellhaven of Marion", "1 Main St", "Marion", "OH",
                          "43302", care=["Short-Term Rehabilitation & Nursing"])]
        proposals, _, _ = classify.build(accounts, site)
        self.assertEqual(proposals, [])

    def test_account_with_open_ar_is_flagged_not_deactivated(self):
        accounts = [
            account("SOLD", "Bellhaven of Sandusky", "2715 Columbus Ave",
                    "Sandusky", "OH", "44870", revenue=130000, receivable=5200),
            account("BUYER", "Millstone Care of Sandusky", "2715 Columbus Ave",
                    "Sandusky", "OH", "44870", parent=JUNIPER),
        ]
        proposals, _, _ = classify.build(accounts, [])
        divested = [p for p in proposals if p["kind"] == "divested"]
        self.assertEqual(len(divested), 1)
        fields = divested[0]["ops"][0]["fields"]
        self.assertEqual(fields["status"], "Needs Review")
        self.assertNotEqual(fields["status"], "Inactive")
        self.assertIn("Millstone", fields["note"])
        self.assertIn("AR", fields["note"])

    def test_keys_are_stable_across_runs(self):
        accounts = [account("A1", "Old Name", "1 Main St", "Akron", "OH", "44301")]
        site = [community("New Name", "1 Main St", "Akron", "OH", "44301")]
        first, _, _ = classify.build(accounts, site)
        second, _, _ = classify.build(accounts, site)
        self.assertEqual(
            [p["key"] for p in first], [p["key"] for p in second]
        )


if __name__ == "__main__":
    unittest.main()
