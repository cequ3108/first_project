"""Fetch public 591 community sale listings. Prefer the JSON API, fall back to the community page."""

from __future__ import annotations

import http.cookiejar
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
LIST_URL = "https://bff-market.591.com.tw/v2/web/sale/list"
MARKET_URL = "https://market.591.com.tw/{community_id}/sale"


def _opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _headers(community_id: int, accept: str = "application/json") -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Referer": MARKET_URL.format(community_id=community_id),
        "Origin": "https://market.591.com.tw",
    }


def _read(opener: urllib.request.OpenerDirector, url: str, headers: dict[str, str], timeout: int) -> bytes:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with opener.open(request, timeout=timeout) as response:
        return response.read()


def fetch_sale_list(community_id: int, timeout: int = 30) -> list[dict]:
    opener = _opener()
    try:
        _read(
            opener,
            MARKET_URL.format(community_id=community_id),
            _headers(community_id, "text/html,application/xhtml+xml"),
            timeout,
        )
    except urllib.error.URLError:
        pass

    try:
        return _fetch_api(opener, community_id, timeout)
    except Exception:
        return _fetch_pages(opener, community_id, timeout)


def _fetch_api(opener: urllib.request.OpenerDirector, community_id: int, timeout: int) -> list[dict]:
    query = urllib.parse.urlencode({"community_id": int(community_id), "page": 1, "limit": 50})
    url = f"{LIST_URL}?{query}"
    try:
        raw = _read(opener, url, _headers(community_id), timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"591 HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"591 連線失敗: {exc.reason}") from exc

    payload = json.loads(raw.decode("utf-8"))
    if not payload.get("status"):
        raise RuntimeError(f"591 回傳失敗: {payload.get('msg') or payload}")
    items = (payload.get("data") or {}).get("items") or []
    if not isinstance(items, list):
        raise RuntimeError("591 回傳格式異常：items 不是列表")
    return items


def _fetch_pages(opener: urllib.request.OpenerDirector, community_id: int, timeout: int) -> list[dict]:
    seen: dict[str, dict] = {}
    for page in range(1, 9):
        url = MARKET_URL.format(community_id=community_id)
        if page > 1:
            url = f"{url}?page={page}"
        try:
            html = _read(
                opener,
                url,
                _headers(community_id, "text/html,application/xhtml+xml"),
                timeout,
            ).decode("utf-8", "replace")
        except urllib.error.URLError as exc:
            if seen:
                break
            raise RuntimeError(f"591 社區頁連線失敗: {exc.reason}") from exc
        items = _items_from_html(html)
        if not items:
            break
        new = 0
        for item in items:
            hid = str(item.get("houseid") or "")
            if hid and hid not in seen:
                seen[hid] = item
                new += 1
        if new == 0:
            break
    if not seen:
        raise RuntimeError("591 社區頁解析不到在售物件")
    return list(seen.values())


def _items_from_html(html: str) -> list[dict]:
    match = re.search(r"<script>window\.__NUXT__=(.*?)</script>", html, re.S)
    if match:
        items = _items_from_nuxt(match.group(1))
        if items:
            return items
    return []


def _items_from_nuxt(script: str) -> list[dict]:
    try:
        raw = subprocess.check_output(
            [
                "node",
                "-e",
                "const src=require('fs').readFileSync(0,'utf8'); const d=eval(src); process.stdout.write(JSON.stringify((d.pinia&&d.pinia.onsaleList&&d.pinia.onsaleList.list)||[]));",
            ],
            input=script.encode("utf-8"),
            timeout=10,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []
    try:
        items = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return []
    return items if isinstance(items, list) else []
