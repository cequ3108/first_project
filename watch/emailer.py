"""Send the daily report through Gmail SMTP. Password comes from env only."""

from __future__ import annotations

import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape


def mail_config(default_to: str = "") -> dict[str, str]:
    to_addr = (os.environ.get("MAIL_TO") or os.environ.get("UANALYZE_EMAIL") or default_to).strip()
    from_addr = (os.environ.get("MAIL_FROM") or os.environ.get("UANALYZE_EMAIL") or to_addr).strip()
    password = (os.environ.get("GMAIL_APP_PASSWORD") or os.environ.get("SMTP_PASS") or "").replace(" ", "")
    return {
        "to": to_addr,
        "from": from_addr,
        "password": password,
        "host": os.environ.get("SMTP_HOST") or "smtp.gmail.com",
        "port": os.environ.get("SMTP_PORT") or "587",
    }


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    parts = ['<div style="font-family:PingFang TC,Microsoft JhengHei,sans-serif;line-height:1.5;">']
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1]):
            table = [line]
            i += 1
            while i < len(lines) and lines[i].startswith("|"):
                table.append(lines[i])
                i += 1
            parts.append(_table_html(table))
            continue
        if line.startswith("# "):
            parts.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            parts.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("### "):
            parts.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("- "):
            parts.append(f"<p>{_inline(line[2:])}</p>")
        elif line.strip() == "":
            parts.append("")
        else:
            parts.append(f"<p>{_inline(line)}</p>")
        i += 1
    parts.append("</div>")
    return "\n".join(parts)


def _inline(text: str) -> str:
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def _table_html(rows: list[str]) -> str:
    body = ['<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">']
    for index, row in enumerate(rows):
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if index == 1 and all(re.fullmatch(r":?-{2,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        tag = "th" if index == 0 else "td"
        body.append("<tr>" + "".join(f"<{tag}>{_inline(cell)}</{tag}>" for cell in cells) + "</tr>")
    body.append("</table>")
    return "\n".join(body)


def require_email_ready(default_to: str = "") -> dict[str, str]:
    """Fail early with a phone-setup hint when Cursor secrets are missing."""
    cfg = mail_config(default_to)
    if not cfg["to"]:
        raise RuntimeError(
            "沒有收件信箱。請在 Cursor Secrets 設 MAIL_TO，或在 watch/communities.json 填 mail_to。"
        )
    if not cfg["password"]:
        raise RuntimeError(
            "缺少 GMAIL_APP_PASSWORD。請用手機打開 "
            "https://cursor.com/dashboard/cloud-agents → Secrets，"
            "新增 GMAIL_APP_PASSWORD（Gmail 應用程式密碼）。不要把密碼寫進倉庫或 GitHub。"
        )
    return cfg


def send_report(subject: str, markdown: str, default_to: str = "") -> str:
    cfg = require_email_ready(default_to)

    html = markdown_to_html(markdown)
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = cfg["from"]
    message["To"] = cfg["to"]
    message.attach(MIMEText(markdown, "plain", "utf-8"))
    message.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(cfg["host"], int(cfg["port"]), timeout=30) as smtp:
        smtp.starttls()
        smtp.login(cfg["from"], cfg["password"])
        smtp.sendmail(cfg["from"], [cfg["to"]], message.as_string())
    return cfg["to"]
