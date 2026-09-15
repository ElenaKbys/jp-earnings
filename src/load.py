import glob
import gzip
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "raw"
DB = REPO / "data" / "jp.duckdb"

# ---- FILL THESE IN from discovery_output.txt -------------------------
F_DATE   = "Date"
F_CODE   = "Code"
F_CLOSE  = "AdjC"         
F_VOLUME = "AdjVo"
F_TURNOVER = "Va"
F_DISC_DATE = "DiscDate"
F_DISC_TIME = "DiscTime"
F_DOC_TYPE  = "DocType"
F_PERIOD_END = "CurPerEn"
# ----------------------------------------------------------------------


def read_all(subdir: str) -> list[dict]:
    rows = []
    for path in sorted(glob.glob(str(RAW / subdir / "*.json.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            rows.extend(json.load(fh))
    return rows


def main() -> int:
    con = duckdb.connect(str(DB))
    con.execute((REPO / "sql" / "schema.sql").read_text())

    bars = pd.DataFrame(read_all("equities_bars_daily"))
    print(f"bars: {len(bars):,} rows, columns: {list(bars.columns)[:12]}")
    prices_df = pd.DataFrame({
        "code":     bars[F_CODE].astype(str),
        "date":     pd.to_datetime(bars[F_DATE]),
        "close":    pd.to_numeric(bars[F_CLOSE], errors="coerce"),
        "volume":   pd.to_numeric(bars[F_VOLUME], errors="coerce"),
        "turnover": pd.to_numeric(bars.get(F_TURNOVER), errors="coerce"),
    }).dropna(subset=["close"])
    con.execute("DELETE FROM prices")
    con.execute("INSERT INTO prices SELECT * FROM prices_df")

    fins = pd.DataFrame(read_all("fins_summary"))
    print(f"fins: {len(fins):,} rows, columns: {list(fins.columns)[:12]}")
    disc_df = pd.DataFrame({
        "code":           fins[F_CODE].astype(str),
        "disclosed_date": pd.to_datetime(fins[F_DISC_DATE]),
        "disclosed_time": fins.get(F_DISC_TIME, "").astype(str),
        "doc_type":       fins.get(F_DOC_TYPE, "").astype(str),
        "period_end":     fins.get(F_PERIOD_END, "").astype(str),
    })
    con.execute("DELETE FROM disclosures")
    con.execute("INSERT INTO disclosures SELECT * FROM disc_df")

    con.execute("DELETE FROM trading_days")
    con.execute("""
        INSERT INTO trading_days
        SELECT date, ROW_NUMBER() OVER (ORDER BY date) - 1 AS day_index
        FROM (SELECT DISTINCT date FROM prices)
    """)

    for t in ("prices", "disclosures", "trading_days"):
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:14} {n:>10,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())