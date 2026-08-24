"""Fetch public 591 community sale listings.

GitHub-hosted runners are often blocked by 591/CloudFront when using Python
urllib (HTTP/1.1). Prefer curl_cffi Chrome TLS, then system curl, then urllib.
"""

from __future__ import annotations

import http.cookiejar
import json
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
LIST_URL = "https://bff-market.591.com.tw/v2/web/sale/list"
MARKET_URL = "https://market.591.com.tw/{community_id}/sale"
SALE_HOME = "https://sale.591.com.tw/"

BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


def market_url(community_id: int) -> str:
    return MARKET_URL.format(community_id=int(community_id))


def parse_sale_list_payload(payload: dict[str, Any]) -> list[dict]:
    if not payload.get("status"):
        raise RuntimeError(f"591 回傳失敗: {payload.get('msg') or payload}")
    items = (payload.get("data") or {}).get("items") or []
    if not isinstance(items, list):
        raise RuntimeError("591 回傳格式異常：items 不是列表")
    return items


_active_session = None


def fetch_sale_list(community_id: int, timeout: int = 30) -> list[dict]:
    global _active_session
    if _active_session is not None:
        return _active_session.sale_list(int(community_id))
    errors: list[str] = []
    for factory in (_curl_cffi_session, _curl_cli_session, _urllib_session):
        try:
            session = factory(timeout)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{factory.__name__} 無法啟動: {exc}")
            continue
        try:
            items = session.sale_list(int(community_id))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{session.name}: {exc}")
            continue
        _active_session = session
        return items
    raise RuntimeError("591 抓取失敗: " + " | ".join(errors))


class _CurlCffiSession:
    name = "curl_cffi"

    def __init__(self, timeout: int):
        from curl_cffi import requests as cf_requests  # type: ignore

        self.timeout = timeout
        self.http = cf_requests.Session(impersonate="chrome")
        self.http.headers.update(BROWSER_HEADERS)
        try:
            self._warm()
        except Exception:
            pass

    def _warm(self) -> None:
        self.http.get(SALE_HOME, timeout=self.timeout)

    def sale_list(self, community_id: int) -> list[dict]:
        page = market_url(community_id)
        try:
            self.http.get(page, timeout=self.timeout)
        except Exception:
            pass
        query = urllib.parse.urlencode({"community_id": community_id, "page": 1, "limit": 50})
        response = self.http.get(
            f"{LIST_URL}?{query}",
            headers={
                "Accept": "application/json",
                "Referer": page,
                "Origin": "https://market.591.com.tw",
                "device": "pc",
            },
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"API HTTP {response.status_code}: {response.text[:200]}")
        return parse_sale_list_payload(response.json())


class _CurlCliSession:
    name = "curl"

    def __init__(self, timeout: int):
        self.timeout = timeout
        self.cookie_file = tempfile.NamedTemporaryFile(prefix="591-cookies-", suffix=".txt", delete=False)
        self.cookie_file.close()
        self._curl([SALE_HOME], fail=False)

    def _curl(self, extra: list[str], fail: bool = True) -> bytes:
        cmd = [
            "curl",
            "-sS",
            "-L",
            "--compressed",
            "--http2",
            "--max-time",
            str(self.timeout),
            "-A",
            USER_AGENT,
            "-H",
            "Accept-Language: zh-TW,zh;q=0.9,en;q=0.8",
            "-c",
            self.cookie_file.name,
            "-b",
            self.cookie_file.name,
        ]
        if fail:
            cmd.append("-f")
        cmd.extend(extra)
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=self.timeout + 5, check=False)
        except FileNotFoundError as exc:
            raise RuntimeError("系統沒有 curl") from exc
        if result.returncode != 0:
            err = (result.stderr or result.stdout).decode("utf-8", "replace")[:240]
            raise RuntimeError(err or f"curl exit {result.returncode}")
        return result.stdout

    def sale_list(self, community_id: int) -> list[dict]:
        page = market_url(community_id)
        try:
            self._curl([page], fail=False)
        except Exception:
            pass
        raw = self._curl(
            [
                "-H",
                "Accept: application/json",
                "-H",
                f"Referer: {page}",
                "-H",
                "Origin: https://market.591.com.tw",
                "-H",
                "device: pc",
                f"{LIST_URL}?community_id={community_id}&page=1&limit=50",
            ]
        )
        return parse_sale_list_payload(json.loads(raw.decode("utf-8")))


class _UrllibSession:
    name = "urllib"

    def __init__(self, timeout: int):
        self.timeout = timeout
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        try:
            self._read(SALE_HOME, {"Accept": "text/html,application/xhtml+xml"})
        except Exception:
            pass

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = dict(BROWSER_HEADERS)
        if extra:
            headers.update(extra)
        return headers

    def _read(self, url: str, extra: dict[str, str] | None = None) -> bytes:
        request = urllib.request.Request(url, headers=self._headers(extra), method="GET")
        with self.opener.open(request, timeout=self.timeout) as response:
            return response.read()

    def sale_list(self, community_id: int) -> list[dict]:
        page = market_url(community_id)
        try:
            html = self._read(page, {"Accept": "text/html,application/xhtml+xml", "Referer": SALE_HOME})
        except urllib.error.HTTPError as exc:
            html = b""
            body = exc.read().decode("utf-8", "replace")[:200]
            html_error = f"社區頁 HTTP {exc.code}: {body or exc.reason}"
        except urllib.error.URLError as exc:
            html = b""
            html_error = f"社區頁連線失敗: {exc.reason}"
        else:
            html_error = ""
        query = urllib.parse.urlencode({"community_id": community_id, "page": 1, "limit": 50})
        try:
            raw = self._read(
                f"{LIST_URL}?{query}",
                {
                    "Accept": "application/json",
                    "Referer": page,
                    "Origin": "https://market.591.com.tw",
                    "device": "pc",
                },
            )
            return parse_sale_list_payload(json.loads(raw.decode("utf-8")))
        except Exception as api_exc:  # noqa: BLE001
            if html:
                items = _items_from_html(html.decode("utf-8", "replace"))
                if items:
                    return items
            detail = html_error or str(api_exc)
            raise RuntimeError(f"API 失敗 ({api_exc}); {detail}".strip("; ")) from api_exc


def _curl_cffi_session(timeout: int) -> _CurlCffiSession:
    return _CurlCffiSession(timeout)


def _curl_cli_session(timeout: int) -> _CurlCliSession:
    return _CurlCliSession(timeout)


def _urllib_session(timeout: int) -> _UrllibSession:
    return _UrllibSession(timeout)


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
