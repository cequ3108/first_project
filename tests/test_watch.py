import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "watch"))

from analyze import (  # noqa: E402
    analyze_community,
    apply_valuation,
    listing_from_raw,
    merge_listings,
    parse_wan,
    sane_original,
)
from render import render_report  # noqa: E402


def load_config():
    return json.loads((ROOT / "watch" / "communities.json").read_text(encoding="utf-8"))


def load_fixture():
    return json.loads((ROOT / "tests" / "fixtures" / "sale_list_sample.json").read_text(encoding="utf-8"))["items"]


class ParseTests(unittest.TestCase):
    def test_parse_wan(self):
        self.assertEqual(parse_wan("2,098"), 2098)
        self.assertEqual(parse_wan("2200萬"), 2200)
        self.assertIsNone(parse_wan("萬"))
        self.assertIsNone(parse_wan(""))

    def test_sane_original_drops_garbage(self):
        self.assertEqual(sane_original(1498, 1576), 1576)
        self.assertIsNone(sane_original(1498, 3580))
        self.assertIsNone(sane_original(1498, 1498))


class DedupeTests(unittest.TestCase):
    def test_merge_same_floor_near_area(self):
        items = load_fixture()
        listings = [listing_from_raw(x) for x in items]
        listings = [x for x in listings if x]
        units = merge_listings(listings)
        uids = {(u["floor"], round(u["area"], 1)) for u in units}
        six = [u for u in units if u["floor"] == 6]
        ten = [u for u in units if u["floor"] == 10]
        four = [u for u in units if u["floor"] == 4]
        self.assertEqual(len(six), 1)
        self.assertEqual(six[0]["ad_count"], 2)
        self.assertEqual(len(four), 1)
        self.assertEqual(four[0]["ad_count"], 2)
        self.assertEqual(len(ten), 1, uids)
        self.assertGreaterEqual(ten[0]["ad_count"], 3)
        self.assertEqual(four[0]["original"], 2168)


class ValuationTests(unittest.TestCase):
    def test_override_small_two_bed(self):
        community = load_config()["communities"][0]
        unit = {
            "floor": 10,
            "area": 34.84,
            "ask": 1498,
            "layout": "2房",
            "house_id": "1",
            "url": "https://example.com",
        }
        valued = apply_valuation(unit, community)
        self.assertEqual(valued["cheap"], 1320)
        self.assertEqual(valued["fair"], 1380)
        self.assertEqual(valued["par"], 1420)
        self.assertFalse(valued["in_fair"])
        self.assertEqual(valued["over_fair"], 118)

    def test_band_bargain_enters_fair(self):
        community = load_config()["communities"][0]
        unit = {
            "floor": 8,
            "area": 34.80,
            "ask": 1350,
            "layout": "2房",
            "house_id": "2",
            "url": "https://example.com",
        }
        valued = apply_valuation(unit, community)
        self.assertTrue(valued["in_fair"])
        self.assertLessEqual(valued["ask"], valued["fair"])


class ReportTests(unittest.TestCase):
    def test_first_section_and_table(self):
        config = load_config()
        community = config["communities"][0]
        previous = {
            "units": [
                {"uid": "8F-34.80-2房", "ask": 1480, "fair": 1378},
                {"uid": "10F-34.84-2房", "ask": 1498, "fair": 1380},
            ]
        }
        analyzed = analyze_community(load_fixture(), community, previous)
        result = {"communities": [analyzed], "generated_at": "2026-08-24 17:00"}
        markdown = render_report(result, "2026-08-24 17:00")
        self.assertIn("一、有沒有掉入合理價", markdown)
        self.assertIn("今日新掉入合理價", markdown)
        self.assertIn("二、開價／便宜價／合理價／平價", markdown)
        self.assertIn("便宜價", markdown)
        self.assertIn("平價", markdown)
        self.assertIn("591已降", markdown)
        small = [u for u in analyzed["units"] if u["floor"] == 10][0]
        self.assertEqual(small["fair"], 1380)
        bargain = [u for u in analyzed["units"] if u["floor"] == 8][0]
        self.assertTrue(bargain["entered_fair"])


if __name__ == "__main__":
    unittest.main()
