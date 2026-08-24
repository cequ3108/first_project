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
from emailer import markdown_to_html  # noqa: E402
from fetch_591 import parse_jina_body, parse_sale_list_payload  # noqa: E402
from history import match_previous, upsert_history  # noqa: E402
from render import render_report  # noqa: E402


def load_config():
    return json.loads((ROOT / "watch" / "communities.json").read_text(encoding="utf-8"))


def load_fixture():
    return json.loads((ROOT / "tests" / "fixtures" / "sale_list_sample.json").read_text(encoding="utf-8"))["items"]


class FetchParseTests(unittest.TestCase):
    def test_empty_items_ok(self):
        self.assertEqual(parse_sale_list_payload({"status": 1, "data": {"items": []}}), [])

    def test_rejects_failed_status(self):
        with self.assertRaises(RuntimeError):
            parse_sale_list_payload({"status": 0, "msg": "forbidden"})

    def test_jina_markdown_wrapper(self):
        wrapped = (
            "Title: 591\n\nURL Source: https://example.com\n\n"
            'Markdown Content:\n{"status":1,"data":{"items":[{"houseid":"1"}]}}\n'
        )
        payload = parse_jina_body(wrapped)
        self.assertEqual(parse_sale_list_payload(payload)[0]["houseid"], "1")


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
        self.assertIn("開價／便宜價／合理價／平價", markdown)
        self.assertIn("便宜價", markdown)
        self.assertIn("平價", markdown)
        self.assertIn("591已降", markdown)
        self.assertIn("今日降價", markdown)
        small = [u for u in analyzed["units"] if u["floor"] == 10][0]
        self.assertEqual(small["fair"], 1380)
        bargain = [u for u in analyzed["units"] if u["floor"] == 8][0]
        self.assertTrue(bargain["entered_fair"])


class HistoryTests(unittest.TestCase):
    def test_match_by_house_id_when_uid_changes(self):
        previous = {
            "units": [
                {"uid": "10F-34.84-2房", "ask": 1498, "house_ids": ["20167173", "20506693"]},
            ]
        }
        current = {"uid": "10F-35.05-2房", "ask": 1460, "ads": [{"house_id": "20167173"}]}
        prev = match_previous(current, previous)
        self.assertEqual(prev["ask"], 1498)

    def test_upsert_keeps_two_days(self):
        history = {"units": {}}
        day1 = {
            "generated_at": "2026-08-24 17:00",
            "communities": [
                {
                    "community_id": "ximen-dayuan",
                    "name": "西門大院",
                    "units": [
                        {
                            "uid": "17F-31.70-2房",
                            "ask": 1220,
                            "cheap": 1140,
                            "fair": 1220,
                            "par": 1280,
                            "over_fair": 0,
                            "drop_note": "未見",
                            "house_ids": ["20325148"],
                            "layout": "2房",
                            "floor_label": "17F/24F",
                            "area": 31.7,
                        }
                    ],
                }
            ],
        }
        upsert_history(history, day1)
        day2 = {
            "generated_at": "2026-08-25 17:00",
            "communities": [
                {
                    "community_id": "ximen-dayuan",
                    "name": "西門大院",
                    "units": [
                        {
                            "uid": "17F-31.70-2房",
                            "ask": 1190,
                            "cheap": 1140,
                            "fair": 1220,
                            "par": 1280,
                            "over_fair": -30,
                            "drop_note": "較昨日降30萬（1220→1190）",
                            "house_ids": ["20325148"],
                            "layout": "2房",
                            "floor_label": "17F/24F",
                            "area": 31.7,
                        }
                    ],
                }
            ],
        }
        upsert_history(history, day2)
        series = history["units"]["ximen-dayuan|17F-31.70-2房"]["history"]
        self.assertEqual([x["date"] for x in series], ["2026-08-24", "2026-08-25"])
        self.assertEqual(series[-1]["ask"], 1190)


class EmailTests(unittest.TestCase):
    def test_markdown_table_to_html(self):
        html = markdown_to_html("# 標題\n\n| 戶 | 開價 |\n|---|---:|\n| A | 100 |\n")
        self.assertIn("<h1>", html)
        self.assertIn("<table", html)
        self.assertIn("<th>", html)
        self.assertIn("100", html)


class XimenTests(unittest.TestCase):
    def test_override_self_sale_two_bed(self):
        community = load_config()["communities"][1]
        self.assertEqual(community["id"], "ximen-dayuan")
        valued = apply_valuation(
            {
                "floor": 17,
                "area": 31.7,
                "ask": 1220,
                "layout": "2房",
                "house_id": "20325148",
                "url": "https://example.com",
            },
            community,
        )
        self.assertEqual(valued["fair"], 1220)
        self.assertTrue(valued["in_fair"])

    def test_sold_unit_excluded(self):
        community = load_config()["communities"][1]
        items = [
            {
                "houseid": "20325148",
                "price_v": {"price": "1,220"},
                "area_v": {"area": "31.70"},
                "floor_en": "17F/24F",
                "room": "2房2廳",
                "title": "西門大院兩房",
            },
            {
                "houseid": "24909466",
                "price_v": {"price": "1,220"},
                "area_v": {"area": "31.70"},
                "floor_en": "17F/24F",
                "room": "2房2廳",
                "title": "西門大院兩房重複刊登",
            },
            {
                "houseid": "99900001",
                "price_v": {"price": "1,220"},
                "area_v": {"area": "31.68"},
                "floor_en": "17F/24F",
                "room": "2房2廳",
                "title": "同戶新刊登也要剔除",
            },
            {
                "houseid": "20325199",
                "price_v": {"price": "1,388"},
                "area_v": {"area": "33.87"},
                "floor_en": "12F/24F",
                "room": "2房2廳",
                "title": "西門大院另一戶",
            },
        ]
        result = analyze_community(items, community)
        uids = [unit["uid"] for unit in result["units"]]
        self.assertNotIn("17F-31.70-2房", uids)
        self.assertEqual(result["ad_count"], 1)
        self.assertEqual(result["unit_count"], 1)
        self.assertEqual(result["units"][0]["house_id"], "20325199")


class XinyuanTests(unittest.TestCase):
    def test_small_two_bed_near_comp(self):
        community = load_config()["communities"][2]
        self.assertEqual(community["id"], "xinyuan-di")
        valued = apply_valuation(
            {
                "floor": 6,
                "area": 28.96,
                "ask": 1198,
                "layout": "2房",
                "house_id": "20109397",
                "url": "https://example.com",
            },
            community,
        )
        self.assertEqual(valued["cheap"], 1080)
        self.assertEqual(valued["fair"], 1160)
        self.assertEqual(valued["par"], 1200)
        self.assertFalse(valued["in_fair"])
        self.assertTrue(valued["in_par"])


class WenhaiyanTests(unittest.TestCase):
    def test_large_three_bed_below_ask(self):
        community = load_config()["communities"][3]
        self.assertEqual(community["id"], "wenhaiyan")
        valued = apply_valuation(
            {
                "floor": 7,
                "area": 76.15,
                "ask": 3488,
                "layout": "3房",
                "house_id": "20723570",
                "url": "https://example.com",
            },
            community,
        )
        self.assertEqual(valued["fair"], 3010)
        self.assertEqual(valued["par"], 3200)
        self.assertFalse(valued["in_fair"])
        self.assertGreater(valued["over_fair"], 400)


class PanyunTests(unittest.TestCase):
    def test_presale_band_and_empty_table(self):
        community = load_config()["communities"][4]
        self.assertEqual(community["id"], "panyun")
        valued = apply_valuation(
            {
                "floor": 10,
                "area": 60.0,
                "ask": 3800,
                "layout": "3房",
                "house_id": "x",
                "url": "https://example.com",
            },
            community,
        )
        self.assertEqual(valued["cheap"], 2520)
        self.assertEqual(valued["fair"], 2700)
        self.assertEqual(valued["par"], 2880)
        analyzed = analyze_community([], community)
        markdown = render_report({"communities": [analyzed]}, "2026-08-24 17:00")
        self.assertIn("目前沒有中古屋", markdown)
        self.assertIn("已完銷", markdown)


class YunjiangTests(unittest.TestCase):
    def test_low_floor_at_fair(self):
        community = load_config()["communities"][5]
        self.assertEqual(community["id"], "yunjiang-haian")
        valued = apply_valuation(
            {
                "floor": 3,
                "area": 54.0,
                "ask": 1780,
                "layout": "3房",
                "house_id": "20468817",
                "url": "https://example.com",
            },
            community,
        )
        self.assertEqual(valued["fair"], 1780)
        self.assertTrue(valued["in_fair"])


class WenlinyanTests(unittest.TestCase):
    def test_dual_parking_three_bed(self):
        community = load_config()["communities"][6]
        self.assertEqual(community["id"], "wenlinyan")
        valued = apply_valuation(
            {
                "floor": 11,
                "area": 86.76,
                "ask": 3688,
                "layout": "3房",
                "house_id": "20639198",
                "url": "https://example.com",
            },
            community,
        )
        self.assertEqual(valued["fair"], 3510)
        self.assertEqual(valued["par"], 3650)
        self.assertFalse(valued["in_fair"])


class ZangmeiTests(unittest.TestCase):
    def test_top_floor_transfer_in_fair(self):
        community = load_config()["communities"][7]
        self.assertEqual(community["id"], "zangmei-omotesando")
        valued = apply_valuation(
            {
                "floor": 20,
                "area": 38.74,
                "ask": 1530,
                "layout": "2房",
                "house_id": "20546471",
                "url": "https://example.com",
            },
            community,
        )
        self.assertEqual(valued["fair"], 1580)
        self.assertTrue(valued["in_fair"])


class DingmeiTests(unittest.TestCase):
    def test_fifteen_floor_near_comp(self):
        community = load_config()["communities"][8]
        self.assertEqual(community["id"], "dingmei")
        valued = apply_valuation(
            {
                "floor": 15,
                "area": 47.2,
                "ask": 1738,
                "layout": "3房",
                "house_id": "20485939",
                "url": "https://example.com",
            },
            community,
        )
        self.assertEqual(valued["fair"], 1740)
        self.assertTrue(valued["in_fair"])


class FuliZhenbangTests(unittest.TestCase):
    def test_high_floor_large_unit_in_fair(self):
        community = load_config()["communities"][9]
        self.assertEqual(community["id"], "fuli-zhenbang")
        valued = apply_valuation(
            {
                "floor": 13,
                "area": 67.94,
                "ask": 3268,
                "layout": "3房",
                "house_id": "20647076",
                "url": "https://example.com",
            },
            community,
        )
        self.assertEqual(valued["fair"], 3300)
        self.assertTrue(valued["in_fair"])


class FuliHezhuTests(unittest.TestCase):
    def test_six_floor_three_bed_in_fair(self):
        community = load_config()["communities"][10]
        self.assertEqual(community["id"], "fuli-hezhu")
        valued = apply_valuation(
            {
                "floor": 6,
                "area": 55.65,
                "ask": 2100,
                "layout": "3房",
                "house_id": "20605562",
                "url": "https://example.com",
            },
            community,
        )
        self.assertEqual(valued["fair"], 2140)
        self.assertTrue(valued["in_fair"])


if __name__ == "__main__":
    unittest.main()
