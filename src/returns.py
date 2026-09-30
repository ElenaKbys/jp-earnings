"""
Compute daily returns per stock and an equal-weighted market index.

    python src/returns.py
"""
import sys
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "jp.duckdb"


def main() -> int:
    con = duckdb.connect(str(DB))

    con.execute("""
        CREATE OR REPLACE TABLE returns AS
        SELECT
            p.code,
            p.date,
            t.day_index,
            p.close,
            p.turnover,
            p.close / LAG(p.close) OVER (PARTITION BY p.code ORDER BY p.date) - 1 AS ret
        FROM prices p
        JOIN trading_days t USING (date)
    """)

    con.execute("""
        CREATE OR REPLACE TABLE market AS
        SELECT date, day_index, AVG(ret) AS mkt_ret, COUNT(*) AS n_stocks
        FROM returns
        WHERE ret IS NOT NULL
          AND ABS(ret) < 0.5          -- drop obvious data errors, not real moves
        GROUP BY date, day_index
    """)

    print("--- return distribution (should be mean~0, stdev~0.02) ---")
    con.sql("SELECT MIN(ret), MAX(ret), AVG(ret), STDDEV(ret) FROM returns WHERE ret IS NOT NULL").show()

    print("--- market's 10 biggest-move days ---")
    con.sql("SELECT * FROM market ORDER BY ABS(mkt_ret) DESC LIMIT 10").show()

    return 0


if __name__ == "__main__":
    sys.exit(main())
