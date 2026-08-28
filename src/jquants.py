"""
J-Quants API v2 client: authentication, rate limiting, pagination, disk cache.

Design notes (these are interview answers, not just comments):

1. AUTH. The v2 API uses a single API key in an `x-api-key` header. Older
   tutorials describe an email/password -> refreshToken -> idToken flow; that
   was v1 and no longer applies.

2. RATE LIMIT. The free plan allows 5 requests/minute. That is the single
   biggest constraint on this project's design. It is why we fetch BY DATE
   rather than BY CODE: `/equities/bars/daily?date=2025-06-02` returns every
   listed stock for that day in one request. Fetching ~490 trading days costs
   ~490 requests (~100 min). Fetching ~4,000 stocks one at a time would cost
   ~4,000 requests (~13 hours).

3. CACHE. Every response is written to data/raw/ as gzipped JSON before it is
   parsed. The analysis gets re-run dozens of times; the API gets hit once.
"""

from __future__ import annotations

import gzip
import json
import os
import time
from pathlib import Path

import requests

API_URL = "https://api.jquants.com/v2"
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"

# Free plan = 5 req/min. Space requests 13s apart for a safety margin.
MIN_SECONDS_BETWEEN_REQUESTS = 13.0

_last_request_time = 0.0


def load_api_key() -> str:
    """Read JQUANTS_API_KEY from the environment or from the .env file."""
    key = os.environ.get("JQUANTS_API_KEY")
    if key:
        return key.strip()

    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == "JQUANTS_API_KEY":
                return value.strip().strip('"').strip("'")

    raise RuntimeError(
        "No API key found.\n"
        "  1. Register at https://jpx-jquants.com/ (free plan)\n"
        "  2. Copy your key from the dashboard\n"
        "  3. cp .env.example .env  and paste it into .env"
    )


def _throttle() -> None:
    """Block until enough time has passed since the previous request."""
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    wait = MIN_SECONDS_BETWEEN_REQUESTS - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_time = time.monotonic()


def _cache_path(endpoint: str, params: dict) -> Path:
    """Stable, human-readable path for a cached response."""
    slug = endpoint.strip("/").replace("/", "_")
    if params:
        tag = "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
    else:
        tag = "all"
    return RAW_DIR / slug / f"{tag}.json.gz"


def fetch(endpoint: str, params: dict | None = None, *, use_cache: bool = True) -> list[dict]:
    """
    GET one endpoint, following pagination, and return the combined `data` list.

    Responses look like {"data": [...], "pagination_key": "..."}. When
    pagination_key is present there is more data; pass it back to get the
    next page.
    """
    params = dict(params or {})
    path = _cache_path(endpoint, params)

    if use_cache and path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)

    headers = {"x-api-key": load_api_key()}
    rows: list[dict] = []
    page_params = dict(params)

    while True:
        _throttle()
        response = requests.get(f"{API_URL}{endpoint}", params=page_params, headers=headers, timeout=60)

        if response.status_code == 429:
            # Rate limited. Back off hard and retry the same page.
            print("  429 rate limited, sleeping 60s...")
            time.sleep(60)
            continue

        if response.status_code != 200:
            raise RuntimeError(
                f"{endpoint} returned HTTP {response.status_code}: {response.text[:300]}"
            )

        payload = response.json()
        rows.extend(payload.get("data", []))

        if "pagination_key" in payload and payload["pagination_key"]:
            page_params["pagination_key"] = payload["pagination_key"]
        else:
            break

    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False)

    return rows


# --- Endpoint wrappers -------------------------------------------------
# Paths verified against the official v2 quickstart notebook (Aug 2026).
# /indices/bars/daily/topix is NOT on the free plan.


def trading_calendar(from_date: str = "", to_date: str = "") -> list[dict]:
    """Official TSE/OSE business-day calendar. One request, no guessing."""
    params = {}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    return fetch("/markets/calendar", params)


def listed_master(date: str = "") -> list[dict]:
    """Listed issue master: code, name, sector, market segment."""
    return fetch("/equities/master", {"date": date} if date else {})


def daily_bars(date: str) -> list[dict]:
    """All stocks' OHLC for one date. Fetch by DATE — see module docstring."""
    return fetch("/equities/bars/daily", {"date": date})


def fin_summary(date: str) -> list[dict]:
    """All financial disclosures made on one date. This is the event spine."""
    return fetch("/fins/summary", {"date": date})


def topix_bars(from_date: str = "", to_date: str = "") -> list[dict]:
    """TOPIX OHLC. Requires the Light plan or above; raises on the free plan."""
    params = {}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    return fetch("/indices/bars/daily/topix", params)
