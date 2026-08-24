"""Parse 591 listings, merge duplicate ads, and apply valuation bands."""

from __future__ import annotations

import re
from typing import Any


def parse_wan(value: Any) -> int | None:
    """Parse a 591 price into 萬. Return None if missing or unusable."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = int(round(float(value)))
        return number if number > 0 else None
    text = str(value).strip()
    if not text or text in {"萬", "0", "0萬"}:
        return None
    text = text.replace(",", "").replace("萬", "").replace("元", "")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    number = int(round(float(match.group(1))))
    return number if number > 0 else None


def parse_area(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return parse_area(value.get("area"))
    try:
        area = float(str(value).replace(",", "").replace("坪", "").strip())
    except ValueError:
        return None
    return area if area > 0 else None


def parse_floor(value: Any) -> tuple[int | None, int | None, str]:
    """Return (floor, total_floors, display)."""
    text = ""
    if isinstance(value, dict):
        text = str(value.get("floor_en") or value.get("floor") or "")
    else:
        text = str(value or "")
    floor_en_match = re.search(r"(\d+)\s*F\s*/\s*(\d+)\s*F", text, re.I)
    if floor_en_match:
        return int(floor_en_match.group(1)), int(floor_en_match.group(2)), text.replace(" ", "")
    floor_zh_match = re.search(r"(\d+)\s*樓\s*/\s*(\d+)", text)
    if floor_zh_match:
        floor, total = int(floor_zh_match.group(1)), int(floor_zh_match.group(2))
        return floor, total, f"{floor}F/{total}F"
    only_floor = re.search(r"(\d+)\s*(?:F|樓)", text, re.I)
    if only_floor:
        floor = int(only_floor.group(1))
        return floor, None, f"{floor}F"
    return None, None, text or "?"


def parse_rooms(room: Any, title: str = "") -> tuple[int, str]:
    text = f"{room or ''} {title or ''}"
    match = re.search(r"(\d)\s*房", text)
    rooms = int(match.group(1)) if match else 0
    if re.search(r"2\s*\+\s*1|2加1|可隔三房", text):
        return 2, "2+1房"
    if rooms >= 3:
        return rooms, f"{rooms}房"
    if rooms == 2:
        return 2, "2房"
    if rooms == 1:
        return 1, "1房"
    return rooms, (str(room).strip() if room else "格局未標")


def sane_original(ask: int | None, original: int | None) -> int | None:
    """Drop 591 original prices that are clearly wrong (e.g. 3580 vs 1498)."""
    if ask is None or original is None:
        return None
    if original <= ask:
        return None
    if original > int(ask * 1.35):
        return None
    return original


def listing_from_raw(raw: dict[str, Any]) -> dict[str, Any] | None:
    house_id = str(raw.get("houseid") or raw.get("id") or "").strip()
    if not house_id:
        return None
    ask = parse_wan((raw.get("price_v") or {}).get("price") if isinstance(raw.get("price_v"), dict) else raw.get("price"))
    if ask is None:
        return None
    area = parse_area(raw.get("area_v") or raw.get("area"))
    if area is None:
        return None
    floor, total, floor_label = parse_floor(raw.get("floor_en") or raw.get("floor"))
    title = str(raw.get("title") or "")
    rooms, layout = parse_rooms(raw.get("room"), title)
    original = sane_original(ask, parse_wan(raw.get("original_price")))
    discounted = str(raw.get("is_discounted") or "") in {"1", "true", "True"}
    labels = raw.get("label") or []
    return {
        "house_id": house_id,
        "title": title,
        "ask": ask,
        "original": original,
        "discounted": bool(discounted and original),
        "area": round(area, 2),
        "floor": floor,
        "total_floors": total,
        "floor_label": floor_label,
        "rooms": rooms,
        "layout": layout,
        "address": str(raw.get("address") or ""),
        "labels": [str(x) for x in labels] if isinstance(labels, list) else [],
        "url": f"https://sale.591.com.tw/home/house/detail/2/{house_id}.html",
    }


def same_unit(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("floor") is None or a.get("floor") != b.get("floor"):
        return False
    area_gap = abs(float(a["area"]) - float(b["area"]))
    ask_gap = abs(int(a["ask"]) - int(b["ask"]))
    if area_gap <= 0.3:
        return True
    if ask_gap <= 20 and area_gap <= 5.5:
        return True
    return False


def merge_listings(listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Union-find merge of ads that look like the same physical unit."""
    parent = list(range(len(listings)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, left in enumerate(listings):
        for j in range(i + 1, len(listings)):
            if same_unit(left, listings[j]):
                parent[find(j)] = find(i)

    groups: dict[int, list[dict[str, Any]]] = {}
    for i, item in enumerate(listings):
        groups.setdefault(find(i), []).append(item)

    units = []
    for group in groups.values():
        group = sorted(group, key=lambda x: (x["ask"], x["house_id"]))
        best = dict(group[0])
        originals = [x["original"] for x in group if x.get("original")]
        best["original"] = min(originals) if originals else None
        if best["original"] and best["original"] <= best["ask"]:
            best["original"] = None
        best["discounted"] = any(x.get("discounted") for x in group) and bool(best["original"])
        plus_one = next((x for x in group if x.get("layout") == "2+1房"), None)
        if plus_one:
            best["layout"] = "2+1房"
            best["rooms"] = plus_one.get("rooms") or 2
        areas = sorted(x["area"] for x in group)
        best["area"] = areas[len(areas) // 2]
        best["ads"] = [
            {"house_id": x["house_id"], "ask": x["ask"], "url": x["url"], "title": x["title"]}
            for x in group
        ]
        best["ad_count"] = len(group)
        units.append(best)
    units.sort(key=lambda x: (x["ask"], x["area"], x["floor"] or 0))
    return units


def match_override(unit: dict[str, Any], overrides: list[dict[str, Any]]) -> dict[str, Any] | None:
    for rule in overrides:
        match = rule.get("match") or {}
        if unit.get("floor") != match.get("floor"):
            continue
        if abs(float(unit["area"]) - float(match["area"])) <= float(match.get("area_tol") or 0.25):
            return rule
    return None


def match_band(unit: dict[str, Any], bands: list[dict[str, Any]]) -> dict[str, Any] | None:
    area = float(unit["area"])
    for band in bands:
        if float(band["min_area"]) <= area < float(band["max_area"]):
            return band
    return None


def apply_valuation(unit: dict[str, Any], community: dict[str, Any]) -> dict[str, Any]:
    valued = dict(unit)
    override = match_override(unit, community.get("overrides") or [])
    if override:
        valued["cheap"] = int(override["cheap"])
        valued["fair"] = int(override["fair"])
        valued["par"] = int(override["par"])
        valued["value_note"] = override.get("note") or "指定估價"
        valued["value_source"] = "override"
    else:
        band = match_band(unit, community.get("bands") or [])
        if not band:
            valued["cheap"] = valued["fair"] = valued["par"] = None
            valued["value_note"] = "尚無估價帶，需人工補"
            valued["value_source"] = "none"
        else:
            area = float(unit["area"])
            valued["cheap"] = int(round(area * float(band["cheap_ping"])))
            valued["fair"] = int(round(area * float(band["fair_ping"])))
            valued["par"] = int(round(area * float(band["par_ping"])))
            valued["value_note"] = f"帶狀估價（{band['id']}）"
            valued["value_source"] = "band"
    fair = valued.get("fair")
    par = valued.get("par")
    ask = valued["ask"]
    valued["over_fair"] = None if fair is None else ask - fair
    valued["over_par"] = None if par is None else ask - par
    valued["in_fair"] = fair is not None and ask <= fair
    valued["in_par"] = par is not None and ask <= par
    valued["uid"] = unit_id(valued)
    return valued


def unit_id(unit: dict[str, Any]) -> str:
    floor = unit.get("floor") if unit.get("floor") is not None else "?"
    layout = unit.get("layout") or "na"
    return f"{floor}F-{float(unit['area']):.2f}-{layout}"


def attach_history(units: list[dict[str, Any]], previous: dict[str, Any] | None) -> list[dict[str, Any]]:
    prev_units = {item["uid"]: item for item in (previous or {}).get("units") or []}
    enriched = []
    for unit in units:
        prev = prev_units.get(unit["uid"])
        prev_ask = prev.get("ask") if prev else None
        dropped = 0
        drop_notes: list[str] = []
        if unit.get("original") and unit["original"] > unit["ask"]:
            dropped = unit["original"] - unit["ask"]
            drop_notes.append(f"591已降{dropped}萬（{unit['original']}→{unit['ask']}）")
        if prev_ask and prev_ask > unit["ask"]:
            day_drop = prev_ask - unit["ask"]
            dropped = max(dropped, day_drop)
            drop_notes.append(f"較昨日降{day_drop}萬（{prev_ask}→{unit['ask']}）")
        entered_fair = bool(
            unit.get("in_fair")
            and (prev_ask is None or (unit.get("fair") is not None and prev_ask > unit["fair"]))
        )
        already_fair = bool(unit.get("in_fair") and prev_ask is not None and unit.get("fair") is not None and prev_ask <= unit["fair"])
        copied = dict(unit)
        copied["prev_ask"] = prev_ask
        copied["drop_amount"] = dropped or None
        copied["drop_note"] = "；".join(drop_notes) if drop_notes else "未見"
        copied["entered_fair"] = entered_fair and prev is not None
        copied["new_in_fair"] = entered_fair and prev is None
        copied["already_fair"] = already_fair
        copied["is_new"] = prev is None
        enriched.append(copied)
    return enriched


def analyze_community(
    raw_items: list[dict[str, Any]],
    community: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    listings = []
    for raw in raw_items:
        item = listing_from_raw(raw)
        if item:
            listings.append(item)
    units = [apply_valuation(unit, community) for unit in merge_listings(listings)]
    units = attach_history(units, previous)
    return {
        "community_id": community["id"],
        "name": community["name"],
        "sale_url": community.get("sale_url"),
        "ad_count": len(listings),
        "unit_count": len(units),
        "units": units,
    }
