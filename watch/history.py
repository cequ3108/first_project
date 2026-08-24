"""Persist daily asking prices on GitHub so later runs can detect drops."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_history(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"units": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("units", {})
    return data


def _house_ids(unit: dict[str, Any]) -> list[str]:
    ads = unit.get("ads") or []
    ids = [str(ad.get("house_id")) for ad in ads if ad.get("house_id")]
    if not ids and unit.get("house_ids"):
        ids = [str(x) for x in unit["house_ids"]]
    if not ids and unit.get("house_id"):
        ids = [str(unit["house_id"])]
    return ids


def _find_entry(history: dict[str, Any], community_id: str, unit: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    uid_key = f"{community_id}|{unit['uid']}"
    units = history.get("units") or {}
    if uid_key in units:
        return uid_key, units[uid_key]
    incoming = set(_house_ids(unit))
    if not incoming:
        return None
    for key, entry in units.items():
        if entry.get("community_id") != community_id:
            continue
        if incoming & set(entry.get("house_ids") or []):
            return key, entry
    return None


def previous_units(history: dict[str, Any], community_id: str) -> dict[str, Any] | None:
    """Rebuild the latest recorded day for one community, used as yesterday."""
    units = []
    for entry in (history.get("units") or {}).values():
        if entry.get("community_id") != community_id:
            continue
        series = entry.get("history") or []
        if not series:
            continue
        last = series[-1]
        units.append(
            {
                "uid": entry.get("uid"),
                "ask": last.get("ask"),
                "fair": last.get("fair"),
                "par": last.get("par"),
                "house_ids": entry.get("house_ids") or [],
            }
        )
    return {"units": units} if units else None


def match_previous(unit: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any] | None:
    if not previous:
        return None
    by_uid = {item["uid"]: item for item in previous.get("units") or [] if item.get("uid")}
    if unit.get("uid") in by_uid:
        return by_uid[unit["uid"]]
    incoming = set(_house_ids(unit))
    if not incoming:
        return None
    for item in previous.get("units") or []:
        if incoming & set(item.get("house_ids") or []):
            return item
    return None


def upsert_history(history: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    day = result["generated_at"][:10]
    units_map = history.setdefault("units", {})
    for community in result.get("communities") or []:
        cid = community["community_id"]
        for unit in community.get("units") or []:
            found = _find_entry(history, cid, unit)
            house_ids = _house_ids(unit)
            record = {
                "date": day,
                "ask": unit["ask"],
                "cheap": unit.get("cheap"),
                "fair": unit.get("fair"),
                "par": unit.get("par"),
                "over_fair": unit.get("over_fair"),
                "drop_note": unit.get("drop_note"),
            }
            if found:
                key, entry = found
                if entry.get("uid") != unit["uid"] and key != f"{cid}|{unit['uid']}":
                    units_map.pop(key, None)
                    key = f"{cid}|{unit['uid']}"
                    units_map[key] = entry
                entry["uid"] = unit["uid"]
                entry["name"] = community.get("name")
                entry["community_id"] = cid
                entry["layout"] = unit.get("layout")
                entry["floor_label"] = unit.get("floor_label")
                entry["area"] = unit.get("area")
                merged_ids = list(dict.fromkeys((entry.get("house_ids") or []) + house_ids))
                entry["house_ids"] = merged_ids
                series = entry.setdefault("history", [])
                replaced = False
                for i, old in enumerate(series):
                    if old.get("date") == day:
                        series[i] = record
                        replaced = True
                        break
                if not replaced:
                    series.append(record)
                series.sort(key=lambda x: x.get("date") or "")
            else:
                units_map[f"{cid}|{unit['uid']}"] = {
                    "community_id": cid,
                    "name": community.get("name"),
                    "uid": unit["uid"],
                    "layout": unit.get("layout"),
                    "floor_label": unit.get("floor_label"),
                    "area": unit.get("area"),
                    "house_ids": house_ids,
                    "history": [record],
                }
    history["updated_at"] = result.get("generated_at")
    return history


def daily_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    communities = []
    for community in result.get("communities") or []:
        communities.append(
            {
                "community_id": community["community_id"],
                "name": community["name"],
                "ad_count": community.get("ad_count"),
                "unit_count": community.get("unit_count"),
                "units": [
                    {
                        "uid": unit["uid"],
                        "layout": unit.get("layout"),
                        "floor_label": unit.get("floor_label"),
                        "area": unit.get("area"),
                        "ask": unit["ask"],
                        "cheap": unit.get("cheap"),
                        "fair": unit.get("fair"),
                        "par": unit.get("par"),
                        "over_fair": unit.get("over_fair"),
                        "drop_note": unit.get("drop_note"),
                        "house_ids": _house_ids(unit),
                    }
                    for unit in community.get("units") or []
                ],
            }
        )
    return {"generated_at": result.get("generated_at"), "communities": communities}
