"""Render Traditional Chinese markdown for the daily watch report."""

from __future__ import annotations

from typing import Any


def wan(value: Any) -> str:
    if value is None:
        return "—"
    return f"{int(value)}"


def signed(value: Any) -> str:
    if value is None:
        return "—"
    number = int(value)
    if number > 0:
        return f"+{number}"
    return str(number)


def unit_link(unit: dict[str, Any]) -> str:
    ads = unit.get("ads") or [{"house_id": unit["house_id"], "url": unit["url"]}]
    if len(ads) == 1:
        return f"[{ads[0]['house_id']}]({ads[0]['url']})"
    return "、".join(f"[{ad['house_id']}]({ad['url']})" for ad in ads[:6])


def format_unit_line(unit: dict[str, Any], community_name: str = "") -> str:
    note = unit.get("value_note") or ""
    extra = f"（{note}）" if note else ""
    prefix = f"**{community_name}**　" if community_name else ""
    return (
        f"- {prefix}**{unit['floor_label']}／{unit['layout']}／{float(unit['area']):.2f}坪** "
        f"開價 **{wan(unit['ask'])}萬**，合理價 {wan(unit['fair'])}萬，平價 {wan(unit['par'])}萬"
        f"{extra}　{unit_link(unit)}"
    )


def _fair_units(community: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    units = community.get("units") or []
    return {
        "entered": [u for u in units if u.get("entered_fair")],
        "new_in": [u for u in units if u.get("new_in_fair")],
        "already": [u for u in units if u.get("already_fair")],
        "in_fair": [u for u in units if u.get("in_fair")],
        "dropped": [u for u in units if u.get("drop_amount")],
    }


def fair_section(communities: list[dict[str, Any]]) -> str:
    lines = ["## 一、有沒有掉入合理價", ""]
    any_fair = False
    for community in communities:
        groups = _fair_units(community)
        if not groups["in_fair"]:
            continue
        any_fair = True
        lines.append(f"### {community['name']}")
        lines.append("")
        if groups["entered"]:
            lines.append("今日新掉入合理價：")
            lines.append("")
            lines.extend(format_unit_line(u) for u in groups["entered"])
            lines.append("")
        if groups["new_in"]:
            lines.append("新出現且已在合理價內：")
            lines.append("")
            lines.extend(format_unit_line(u) for u in groups["new_in"])
            lines.append("")
        if groups["already"]:
            lines.append("原本就在合理價內：")
            lines.append("")
            lines.extend(format_unit_line(u) for u in groups["already"])
            lines.append("")
        leftover = [
            u
            for u in groups["in_fair"]
            if u not in groups["entered"] and u not in groups["new_in"] and u not in groups["already"]
        ]
        if leftover:
            lines.extend(format_unit_line(u) for u in leftover)
            lines.append("")
    if not any_fair:
        lines.append("今日**沒有**物件開價掉到合理價（開價仍高於合理價）。")
        lines.append("")
    return "\n".join(lines)


def drop_section(communities: list[dict[str, Any]]) -> str:
    lines = ["## 二、今日降價", ""]
    any_drop = False
    for community in communities:
        dropped = [u for u in community.get("units") or [] if u.get("drop_amount")]
        if not dropped:
            continue
        any_drop = True
        lines.append(f"### {community['name']}")
        lines.append("")
        for unit in dropped:
            lines.append(
                f"- **{unit['floor_label']}／{unit['layout']}／{float(unit['area']):.2f}坪** "
                f"開價 **{wan(unit['ask'])}萬**　{unit.get('drop_note')}　{unit_link(unit)}"
            )
        lines.append("")
    if not any_drop:
        lines.append("今日沒有偵測到降價（含 591 已降價、或比 GitHub 上一次紀錄更低）。")
        lines.append("")
    return "\n".join(lines)


def table_section(community: dict[str, Any], heading: str) -> str:
    units = community.get("units") or []
    sale_url = community.get("sale_url") or ""
    lines = [
        heading,
        "",
        f"{community['name']}：在售 {community.get('ad_count', 0)} 則，去重後 **{community.get('unit_count', 0)}** 戶。2 房與 3 房同一張表。",
    ]
    if sale_url:
        lines.append(f"來源：[{sale_url}]({sale_url})")
    if not units:
        note = community.get("empty_note") or "目前沒有 591 中古屋在售，之後出現會自動進表。"
        lines.extend(["", note, ""])
        return "\n".join(lines)
    lines.extend(
        [
            "",
            "| 戶 | 格局 | 樓層 | 坪數 | 開價 | 便宜價 | 合理價 | 平價 | 超出合理 | 降價 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for unit in units:
        drop = unit.get("drop_note") or "未見"
        lines.append(
            f"| {unit['uid']} | {unit['layout']} | {unit['floor_label']} | {float(unit['area']):.2f} | "
            f"{wan(unit['ask'])} | {wan(unit.get('cheap'))} | {wan(unit.get('fair'))} | {wan(unit.get('par'))} | "
            f"{signed(unit.get('over_fair'))} | {drop} |"
        )
    lines.append("")
    lines.append("單位：萬、含車（若該則標含車位）。超出合理 = 開價 − 合理價。")
    lines.append("")
    return "\n".join(lines)


def footnote() -> str:
    return "\n".join(
        [
            "## 說明",
            "",
            "- **便宜價**：買方優勢價，要有讓價空間才談得下來。",
            "- **合理價**：依近期實價回推，開價掉到這條線以下才值得認真看。",
            "- **平價**：接近市場成交的持平價；再高就偏貴。",
            "- 第一區塊只看「開價 ≤ 合理價」。這不是成交保證，也不是自動出價。",
            "- 每日開價寫在 `data/daily/` 與 `data/price-history.json`，用來比對有沒有降價。",
            "- 同一戶多個房仲刊登會合併，連結保留前幾則供核對。",
            "- 西門大院多為新成屋／換約，合理價先用現況開價帶往下修，之後有更新實價再調。",
            "- 遠雄新源邸約 6 年，合理價對過 115 年同社區實價（小兩房約 36–41 萬／坪、49 坪三房約 37.8 萬／坪）。",
            "- 國泰文海硯約 9 年、大坪數為主。近一年同社區大戶實價約 33–43 萬／坪，開價若到 45 萬／坪以上通常偏貴。",
            "- 國泰磐耘是東區預售、591 標已完銷，交屋約 2026 下半年。牌價約 47–53 萬／坪；換約／新成屋先用 42／45／48 萬／坪當便宜／合理／平價。",
            "- 允將海安約 1 年新成屋。111 年同社區 53 坪預售成交約 33–35 萬／坪；低樓未住若開到這個帶可以認真看，高樓景觀另加。",
            "- 國泰文林硯約 8 年，與文海硯同帶。近半年同社區大戶實價約 38–43 萬／坪；高樓若開到 50 萬／坪以上通常偏貴。",
            "- 藏美表參道是北區西門／文成預售已完銷，交屋約 2025。113 年同社區兩房成交約 41–44 萬／坪；換約開價低於這條線可以認真看。",
            "- 遠雄頂美約 3 年、中西區中華西路。近半年同社區成交約 36–37 萬／坪；15F 三房若開在 1730 附近已接近實價。",
            "- 富立真邦約 7 年、東區崇賢三路（南台南站重劃區）。近半年同社區成交約 46–48 萬／坪；低樓三房若開在 3060 附近、高樓大戶若開在 3300 附近可以認真看。",
            "",
        ]
    )


def render_report(result: dict[str, Any], generated_at: str) -> str:
    communities = result.get("communities") or []
    names = "、".join(c.get("name") or "" for c in communities) or "社區盯盤"
    header = [
        f"# {names} 每日盯盤",
        "",
        f"- 產出時間（台灣）：**{generated_at}**",
        f"- 社區數：**{len(communities)}**",
        "",
    ]
    parts = ["\n".join(header), fair_section(communities), drop_section(communities)]
    for index, community in enumerate(communities, start=3):
        parts.append(table_section(community, f"## { _cjk_index(index) }、{community['name']}｜開價／便宜價／合理價／平價"))
    parts.append(footnote())
    return "\n".join(parts).rstrip() + "\n"


def _cjk_index(number: int) -> str:
    mapping = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十", 11: "十一", 12: "十二"}
    return mapping.get(number, str(number))
