"""
Sort events into quintiles by announcement-window surprise (CAR[-1,+1]),
assigned within each announcement period, then compute CAAR by quintile.

    python src/quintiles.py
"""
import sys
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "jp.duckdb"


def main() -> int:
    con = duckdb.connect(str(DB))

    con.execute("""
        CREATE OR REPLACE TABLE surprise AS
        WITH s AS (
            SELECT code, period_end, event_day_index,
                   SUM(ar) AS car_announce
            FROM abnormal WHERE rel_day BETWEEN -1 AND 1
            GROUP BY 1,2,3
        )
        SELECT *,
               CAST(event_day_index / 10 AS INTEGER) AS period_bucket,
               NTILE(5) OVER (
                   PARTITION BY CAST(event_day_index / 10 AS INTEGER)
                   ORDER BY car_announce
               ) AS quintile
        FROM s
    """)

    con.execute("""
        CREATE OR REPLACE TABLE caar AS
        SELECT s.quintile, a.rel_day,
               AVG(a.ar) AS aar,
               COUNT(*)  AS n
        FROM abnormal a
        JOIN surprise s USING (code, period_end, event_day_index)
        GROUP BY 1,2
    """)

    print("--- quintile sizes and average surprise (should rise Q1->Q5) ---")
    con.sql("SELECT quintile, COUNT(*), AVG(car_announce) FROM surprise GROUP BY 1 ORDER BY 1").show()

    caar = con.sql("SELECT * FROM caar ORDER BY quintile, rel_day").df()
    caar["caar"] = caar.groupby("quintile")["aar"].cumsum()

    print("--- cumulative abnormal return at day +60, by quintile (sneak preview) ---")
    print(caar[caar.rel_day == 60][["quintile", "caar"]].to_string(index=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
