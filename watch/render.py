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


def format_unit_line(unit: dict[str, Any]) -> str:
    note = unit.get("value_note") or ""
    extra = f"（{note}）" if note else ""
    return (
        f"- **{unit['floor_label']}／{unit['layout']}／{float(unit['area']):.2f}坪** "
        f"開價 **{wan(unit['ask'])}萬**，合理價 {wan(unit['fair'])}萬，平價 {wan(unit['par'])}萬"
        f"{extra}　{unit_link(unit)}"
    )


def fair_section(units: list[dict[str, Any]]) -> str:
    entered = [u for u in units if u.get("entered_fair")]
    new_in = [u for u in units if u.get("new_in_fair")]
    already = [u for u in units if u.get("already_fair")]
    in_fair = [u for u in units if u.get("in_fair")]
    lines = ["## 一、有沒有掉入合理價", ""]
    if not in_fair:
        lines.append("今日**沒有**物件開價掉到合理價（開價仍高於合理價）。")
        lines.append("")
        return "\n".join(lines)

    if entered:
        lines.append("### 今日新掉入合理價")
        lines.append("")
        lines.extend(format_unit_line(u) for u in entered)
        lines.append("")
    if new_in:
        lines.append("### 新出現且已在合理價內")
        lines.append("")
        lines.extend(format_unit_line(u) for u in new_in)
        lines.append("")
    if already:
        lines.append("### 原本就在合理價內")
        lines.append("")
        lines.extend(format_unit_line(u) for u in already)
        lines.append("")
    if in_fair and not (entered or new_in or already):
        lines.append("以下物件開價已 ≤ 合理價：")
        lines.append("")
        lines.extend(format_unit_line(u) for u in in_fair)
        lines.append("")
    return "\n".join(lines)


def table_section(units: list[dict[str, Any]]) -> str:
    lines = [
        "## 二、開價／便宜價／合理價／平價",
        "",
        "2 房與 3 房同一張表，已把同一戶的重複刊登合併。",
        "",
        "| 戶 | 格局 | 樓層 | 坪數 | 開價 | 便宜價 | 合理價 | 平價 | 超出合理 | 降價 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for unit in units:
        drop = unit.get("drop_note") or "未見"
        row = (
            f"| {unit['uid']} | {unit['layout']} | {unit['floor_label']} | {float(unit['area']):.2f} | "
            f"{wan(unit['ask'])} | {wan(unit.get('cheap'))} | {wan(unit.get('fair'))} | {wan(unit.get('par'))} | "
            f"{signed(unit.get('over_fair'))} | {drop} |"
        )
        lines.append(row)
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
            "- 同一戶多個房仲刊登會合併，連結保留前幾則供核對。",
            "",
        ]
    )


def render_report(result: dict[str, Any], generated_at: str) -> str:
    community = result["communities"][0] if result.get("communities") else {}
    units = community.get("units") or []
    name = community.get("name") or "社區盯盤"
    sale_url = community.get("sale_url") or ""
    header = [
        f"# {name} 每日盯盤",
        "",
        f"- 產出時間（台灣）：**{generated_at}**",
        f"- 在售刊登：{community.get('ad_count', 0)} 則，去重後 **{community.get('unit_count', 0)}** 戶",
    ]
    if sale_url:
        header.append(f"- 來源：[{sale_url}]({sale_url})")
    header.append("")
    parts = [
        "\n".join(header),
        fair_section(units),
        table_section(units),
        footnote(),
    ]
    return "\n".join(parts).rstrip() + "\n"
