#!/usr/bin/env python3
"""Build the daily community watch report, store prices on GitHub, and email it."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze import analyze_community  # noqa: E402
from emailer import send_report  # noqa: E402
from fetch_591 import fetch_sale_list  # noqa: E402
from history import daily_snapshot, load_history, previous_units, upsert_history  # noqa: E402
from render import render_report  # noqa: E402

TAIPEI = timezone(timedelta(hours=8))
ISSUE_TITLE = "社區每日盯盤"
ISSUE_LABEL = "daily-watch"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def now_taipei() -> datetime:
    return datetime.now(TAIPEI)


def snapshot_from_result(result: dict[str, Any]) -> dict[str, Any]:
    return daily_snapshot(result)


def previous_for(community_id: str, snapshot: dict[str, Any] | None, history: dict[str, Any] | None) -> dict[str, Any] | None:
    from_history = previous_units(history or {}, community_id)
    if from_history:
        return from_history
    for item in (snapshot or {}).get("communities") or []:
        if item.get("community_id") == community_id:
            return item
    return None


def run_watch(
    config: dict[str, Any],
    snapshot: dict[str, Any] | None,
    history: dict[str, Any] | None,
    fixture_items: list | None = None,
    fixture_community: str | None = None,
) -> dict[str, Any]:
    generated_at = now_taipei().strftime("%Y-%m-%d %H:%M")
    communities = []
    listed = config.get("communities") or []
    for index, community in enumerate(listed):
        use_fixture = fixture_items is not None and (
            fixture_community == community["id"] or (fixture_community is None and len(listed) == 1)
        )
        if use_fixture:
            items = fixture_items
        else:
            if index > 0:
                time.sleep(1)
            items = fetch_sale_list(community["market_id"])
        analyzed = analyze_community(items, community, previous_for(community["id"], snapshot, history))
        communities.append(analyzed)
    return {"generated_at": generated_at, "communities": communities}


def write_outputs(
    result: dict[str, Any],
    report_md: str,
    history: dict[str, Any],
    data_dir: Path,
    reports_dir: Path,
) -> list[Path]:
    data_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    daily_dir = data_dir / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    day = result["generated_at"][:10]
    updated_history = upsert_history(history, result)
    paths = {
        data_dir / "snapshot.json": daily_snapshot(result),
        data_dir / "price-history.json": updated_history,
        daily_dir / f"{day}.json": daily_snapshot(result),
    }
    written = []
    for path, payload in paths.items():
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    latest_path = reports_dir / "latest.md"
    dated_path = reports_dir / f"{day}.md"
    latest_path.write_text(report_md, encoding="utf-8")
    dated_path.write_text(report_md, encoding="utf-8")
    written.extend([latest_path, dated_path])
    return written


def github_request(method: str, path: str, token: str, payload: dict | None = None) -> Any:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("缺少 GITHUB_REPOSITORY")
    url = f"https://api.github.com/repos/{repo}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "community-daily-watch",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"GitHub API {exc.code} {path}: {body}") from exc


def ensure_label(token: str) -> None:
    try:
        github_request(
            "POST",
            "/labels",
            token,
            {"name": ISSUE_LABEL, "color": "1d76db", "description": "每日社區盯盤"},
        )
    except RuntimeError as exc:
        if "already_exists" not in str(exc) and "422" not in str(exc):
            raise


def find_or_create_issue(token: str) -> int:
    from urllib.parse import quote

    ensure_label(token)
    search = github_request(
        "GET",
        f"/issues?state=open&labels={quote(ISSUE_LABEL)}&per_page=10",
        token,
    )
    for issue in search or []:
        if issue.get("title") == ISSUE_TITLE:
            return int(issue["number"])
    created = github_request(
        "POST",
        "/issues",
        token,
        {
            "title": ISSUE_TITLE,
            "labels": [ISSUE_LABEL],
            "body": (
                "這則 Issue 收遠雄北府苑、西門大院、遠雄新源邸、國泰文海硯、國泰磐耘的每日盯盤備份。\n\n"
                "正式報告會寄到信箱；這裡方便在 GitHub 上回看。"
            ),
        },
    )
    return int(created["number"])


def publish_issue(report_md: str, token: str) -> int:
    number = find_or_create_issue(token)
    github_request("POST", f"/issues/{number}/comments", token, {"body": report_md})
    return number


def write_step_summary(report_md: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    Path(path).write_text(report_md, encoding="utf-8")


def commit_outputs(paths: list[Path], message: str) -> bool:
    if os.environ.get("SKIP_GIT_COMMIT") == "1":
        return False
    subprocess.run(["git", "add", *[str(p) for p in paths]], check=True, cwd=ROOT)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if staged.returncode == 0:
        return False
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=github-actions[bot]",
            "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit",
            "-m",
            message,
        ],
        check=True,
        cwd=ROOT,
    )
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="社區每日盯盤")
    parser.add_argument("--config", type=Path, default=ROOT / "watch" / "communities.json")
    parser.add_argument("--snapshot", type=Path, default=ROOT / "data" / "snapshot.json")
    parser.add_argument("--history", type=Path, default=ROOT / "data" / "price-history.json")
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--fixture", type=Path, help="用本地 JSON 測試，不打 591")
    parser.add_argument("--fixture-community", help="fixture 只套用這個社區 id")
    parser.add_argument("--publish-issue", action="store_true")
    parser.add_argument("--send-email", action="store_true")
    parser.add_argument("--commit", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config, {})
    snapshot = load_json(args.snapshot, None)
    history = load_history(args.history)
    fixture_items = None
    if args.fixture:
        fixture_payload = load_json(args.fixture, {})
        fixture_items = fixture_payload.get("items") if isinstance(fixture_payload, dict) else fixture_payload
    try:
        result = run_watch(config, snapshot, history, fixture_items, args.fixture_community)
    except Exception as exc:  # noqa: BLE001 — report fetch failures
        fail_md = (
            f"# 每日盯盤失敗\n\n"
            f"- 時間（台灣）：**{now_taipei().strftime('%Y-%m-%d %H:%M')}**\n"
            f"- 原因：`{exc}`\n"
        )
        print(fail_md, file=sys.stderr)
        write_step_summary(fail_md)
        token = os.environ.get("GITHUB_TOKEN")
        if args.publish_issue and token:
            publish_issue(fail_md, token)
        if args.send_email:
            try:
                send_report("【盯盤失敗】社區每日報告", fail_md, config.get("mail_to") or "")
            except Exception as mail_exc:  # noqa: BLE001
                print(f"寄信失敗: {mail_exc}", file=sys.stderr)
        return 1

    report_md = render_report(result, result["generated_at"])
    written = write_outputs(result, report_md, history, args.data_dir, args.reports_dir)
    print(report_md)
    write_step_summary(report_md)

    token = os.environ.get("GITHUB_TOKEN")
    if args.publish_issue:
        if not token:
            print("未設定 GITHUB_TOKEN，略過 Issue 發佈", file=sys.stderr)
        else:
            number = publish_issue(report_md, token)
            print(f"已回覆 Issue #{number}", file=sys.stderr)

    if args.send_email:
        names = "、".join(c["name"] for c in result.get("communities") or [])
        subject = f"【每日盯盤】{names} {result['generated_at'][:10]}"
        to_addr = send_report(subject, report_md, config.get("mail_to") or "")
        print(f"已寄信到 {to_addr}", file=sys.stderr)

    if args.commit:
        day = result["generated_at"][:10]
        if commit_outputs(written, f"chore: 更新 {day} 社區盯盤與開價紀錄"):
            print("已提交 snapshot、價格歷史與報告", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
