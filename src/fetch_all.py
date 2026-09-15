"""
Bulk-fetch every trading day's bars and disclosures into data/raw/.

Resumable: jquants.fetch() caches to disk, so re-running skips anything
already downloaded. If it dies at day 300, just run it again.

    python src/fetch_all.py
"""
import sys

import requests

import jquants as jq


def business_days() -> list[str]:
    cal = jq.trading_calendar()
    days = [
        r["Date"] for r in cal
        if str(r.get("HolidayDivision", r.get("HolDiv", ""))) == "1"
    ]
    return sorted(days)


def main() -> int:
    days = business_days()
    print(f"{len(days)} business days: {days[0]} .. {days[-1]}")
    print(f"~{len(days) * 2} requests, ~{len(days) * 2 * 13 / 3600:.1f} hours if uncached\n")

    jq.listed_master()
    print("master cached")

    for i, day in enumerate(days, 1):
        try:
            bars = jq.daily_bars(day)
            fins = jq.fin_summary(day)
            print(f"  [{i:4}/{len(days)}] {day}  bars={len(bars):5}  fins={len(fins):4}", flush=True)
        except (RuntimeError, requests.exceptions.RequestException) as exc:
            print(f"  [{i:4}/{len(days)}] {day}  FAILED: {exc}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
