"""
Build the event panel: one row per (event, day) for the estimation and
event windows, then flag which events have enough data to use.

    python src/build_panel.py
"""
import sys
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "jp.duckdb"


def main() -> int:
    con = duckdb.connect(str(DB))

    con.execute("""
        CREATE OR REPLACE TABLE panel AS
        SELECT
            e.code,
            e.period_end,
            e.event_day_index,
            r.day_index,
            r.day_index - e.event_day_index AS rel_day,
            r.ret,
            m.mkt_ret
        FROM events e
        JOIN returns r
          ON r.code = e.code
         AND r.day_index BETWEEN e.event_day_index - 150 AND e.event_day_index + 60
        JOIN market m ON m.day_index = r.day_index
        WHERE r.ret IS NOT NULL
    """)

    con.execute("""
        CREATE OR REPLACE TABLE usable_events AS
        SELECT code, period_end, event_day_index
        FROM panel
        GROUP BY 1,2,3
        HAVING SUM(CASE WHEN rel_day BETWEEN -150 AND -30 THEN 1 ELSE 0 END) >= 100
           AND SUM(CASE WHEN rel_day BETWEEN   -1 AND  60 THEN 1 ELSE 0 END) >= 55
    """)

    before = con.sql("SELECT COUNT(*) FROM events").fetchone()[0]
    after = con.sql("SELECT COUNT(*) FROM usable_events").fetchone()[0]
    print(f"{before} events -> {after} usable ({after/before:.0%})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
