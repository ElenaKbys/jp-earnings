"""
Significance test on the Q5-Q1 drift spread: naive vs. clustered by
announcement date.

    python src/stats.py
"""
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "jp.duckdb"


def clustered_se(x, clusters):
    df = pd.DataFrame({"x": x, "c": clusters})
    means = df.groupby("c")["x"].mean()
    return means.std(ddof=1) / np.sqrt(len(means)), len(means)


def main() -> int:
    con = duckdb.connect(str(DB))

    drift = con.sql("""
        SELECT s.quintile, s.event_day_index, a.code, a.period_end,
               SUM(a.ar) AS car_drift
        FROM abnormal a
        JOIN surprise s USING (code, period_end, event_day_index)
        WHERE a.rel_day BETWEEN 2 AND 60
        GROUP BY 1,2,3,4
    """).df()

    top = drift[drift.quintile == 5].car_drift
    bot = drift[drift.quintile == 1].car_drift
    spread = top.mean() - bot.mean()

    t_naive, p_naive = stats.ttest_ind(top, bot, equal_var=False)

    se_top, n_top = clustered_se(top.values, drift[drift.quintile == 5].event_day_index.values)
    se_bot, n_bot = clustered_se(bot.values, drift[drift.quintile == 1].event_day_index.values)
    se_spread = np.sqrt(se_top**2 + se_bot**2)
    t_clustered = spread / se_spread

    print(f"Q5-Q1 drift [+2,+60]: {spread*100:+.2f}%")
    print(f"  naive      t = {t_naive:6.2f}  (n = {len(top)} + {len(bot)} events)")
    print(f"  clustered  t = {t_clustered:6.2f}  (n = {n_top} + {n_bot} dates)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
