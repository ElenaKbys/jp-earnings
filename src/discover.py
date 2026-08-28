"""
Run this FIRST, right after you get your API key.

It answers the four questions that decide how the rest of the project is built:
  1. Does my key work?
  2. What date range does the free plan actually give me?
  3. What are the real response field names? (docs and reality drift)
  4. Can I get TOPIX, or do I need to build my own market index?

Costs about 6 API requests, so ~90 seconds on the free plan's 5/min limit.

    python src/discover.py
"""

import sys
from collections import Counter

import jquants as jq


def show(title: str, rows: list[dict], sample_keys: int = 40) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
    if not rows:
        print("  (no rows returned)")
        return
    print(f"  rows: {len(rows)}")
    print(f"  fields ({len(rows[0])}):")
    for key in list(rows[0].keys())[:sample_keys]:
        value = rows[0][key]
        preview = str(value)[:45]
        print(f"    {key:<28} = {preview}")


def main() -> int:
    try:
        key = jq.load_api_key()
    except RuntimeError as exc:
        print(exc)
        return 1
    print(f"API key loaded (ends ...{key[-4:]})")

    # 1. Trading calendar — also tells us the available date range.
    cal = jq.trading_calendar()
    show("1. /markets/calendar", cal)
    business_days = sorted(
        r.get("Date", "") for r in cal
        if str(r.get("HolidayDivision", r.get("HolDiv", ""))) == "1"
    )
    if business_days:
        print(f"\n  business days: {len(business_days)}")
        print(f"  range: {business_days[0]} .. {business_days[-1]}")

    # 2. Listed master.
    show("2. /equities/master", jq.listed_master())

    # 3. Daily bars. Probe recent business days until one returns data —
    #    this finds the edge of the 12-week delay empirically.
    print(f"\n{'=' * 70}\n3. /equities/bars/daily — probing for latest available date\n{'=' * 70}")
    bars, bars_date = [], None
    for day in reversed(business_days[-120:]):
        try:
            bars = jq.daily_bars(day)
        except RuntimeError as exc:
            print(f"  {day}: {exc}")
            break
        print(f"  {day}: {len(bars)} rows")
        if bars:
            bars_date = day
            break
    show(f"   fields at {bars_date}", bars)

    # 4. Financial disclosures. Probe backwards from the latest price date.
    print(f"\n{'=' * 70}\n4. /fins/summary — probing for a day with disclosures\n{'=' * 70}")
    fins = []
    if bars_date:
        start = business_days.index(bars_date)
        for day in reversed(business_days[max(0, start - 30):start + 1]):
            fins = jq.fin_summary(day)
            print(f"  {day}: {len(fins)} disclosures")
            if fins:
                break
    show("   fields", fins)

    # 5. Is TOPIX available on this plan?
    print(f"\n{'=' * 70}\n5. /indices/bars/daily/topix — plan check\n{'=' * 70}")
    try:
        topix = jq.topix_bars()
        print(f"  AVAILABLE: {len(topix)} rows. Use TOPIX as the market index.")
        if topix:
            print(f"  fields: {list(topix[0].keys())}")
    except RuntimeError as exc:
        print(f"  NOT AVAILABLE ({str(exc)[:120]})")
        print("  -> Build an equal-weighted market index from the cross-section.")

    if fins:
        std = Counter(str(r.get("AcctStd", r.get("AccountingStandard", "?")))
                      for r in fins)
        print(f"\n  accounting standards in that sample: {dict(std)}")

    print("\nDone. Use this output to build the loader.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
