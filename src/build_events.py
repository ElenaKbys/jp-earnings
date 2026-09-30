"""
Build the events table: real earnings disclosures, first release only,
with the day-0 timing rule applied.

    python src/build_events.py
"""
import sys
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "jp.duckdb"


def main() -> int:
    con = duckdb.connect(str(DB))

    con.execute("""
        CREATE OR REPLACE TABLE events AS
        WITH earnings AS (
            SELECT code, disclosed_date, disclosed_time, period_end
            FROM disclosures
            WHERE doc_type LIKE '%FinancialStatements%'
        ),
        first_only AS (
            SELECT *, ROW_NUMBER() OVER (
                       PARTITION BY code, period_end
                       ORDER BY disclosed_date, disclosed_time
                   ) AS rn
            FROM earnings
        ),
        timed AS (
            SELECT
                code,
                disclosed_date,
                disclosed_time,
                period_end,
                CASE WHEN disclosed_time = '' OR disclosed_time IS NULL THEN 1
                     WHEN CAST(SUBSTR(disclosed_time, 1, 2) AS INTEGER) >= 15 THEN 1
                     ELSE 0
                END AS shift_days
            FROM first_only WHERE rn = 1
        )
        SELECT
            t.code,
            t.disclosed_date,
            t.disclosed_time,
            t.period_end,
            t.shift_days,
            d.day_index + t.shift_days AS event_day_index
        FROM timed t
        JOIN trading_days d ON d.date = t.disclosed_date
    """)

    print("--- total events ---")
    con.sql("SELECT COUNT(*) FROM events").show()

    print("--- shift_days breakdown ---")
    con.sql("SELECT shift_days, COUNT(*) FROM events GROUP BY 1").show()

    print("--- events by calendar month (should be spiky: Feb/May/Aug/Nov) ---")
    con.sql("""
        SELECT MONTH(disclosed_date) m, COUNT(*) n
        FROM events GROUP BY 1 ORDER BY 1
    """).show()

    return 0


if __name__ == "__main__":
    sys.exit(main())
