"""
Robustness checks: market-adjusted returns, a "clean" index excluding
stocks mid-event, and a liquidity filter. Reported side by side with
the baseline from steps 7/8/10.

    python src/robustness.py
"""
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "jp.duckdb"


def clustered_se(x, clusters):
    df = pd.DataFrame({"x": x, "c": clusters})
    means = df.groupby("c")["x"].mean()
    return means.std(ddof=1) / np.sqrt(len(means)), len(means)


def evaluate(con, table: str):
    """Quintile sort + naive/clustered t-test on any (code, period_end,
    event_day_index, rel_day, ar) table. Mirrors steps 8 and 10."""
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE _surprise AS
        WITH s AS (
            SELECT code, period_end, event_day_index, SUM(ar) AS car_announce
            FROM {table} WHERE rel_day BETWEEN -1 AND 1
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

    drift = con.sql(f"""
        SELECT s.quintile, s.event_day_index, a.code, a.period_end,
               SUM(a.ar) AS car_drift
        FROM {table} a
        JOIN _surprise s USING (code, period_end, event_day_index)
        WHERE a.rel_day BETWEEN 2 AND 60
        GROUP BY 1,2,3,4
    """).df()

    top = drift[drift.quintile == 5].car_drift
    bot = drift[drift.quintile == 1].car_drift
    spread = top.mean() - bot.mean()

    t_naive, _ = stats.ttest_ind(top, bot, equal_var=False)
    se_top, n_top = clustered_se(top.values, drift[drift.quintile == 5].event_day_index.values)
    se_bot, n_bot = clustered_se(bot.values, drift[drift.quintile == 1].event_day_index.values)
    t_clustered = spread / np.sqrt(se_top**2 + se_bot**2)

    return spread, t_naive, t_clustered, len(top) + len(bot)


def fit_abnormal(con, panel_query: str, table_name: str) -> None:
    """Same per-event OLS loop as events.py, parameterized so it can run
    against any panel (used for the clean-index check)."""
    panel = con.sql(panel_query).df()
    out = []
    for (code, period), g in panel.groupby(["code", "period_end"], sort=False):
        est = g[(g.rel_day >= -150) & (g.rel_day <= -30)]
        evt = g[(g.rel_day >= -1) & (g.rel_day <= 60)].sort_values("rel_day")
        if len(est) < 100 or len(evt) < 55:
            continue
        X = sm.add_constant(est["mkt_ret"].values)
        fit = sm.OLS(est["ret"].values, X).fit()
        alpha, beta = fit.params
        ar = evt["ret"].values - (alpha + beta * evt["mkt_ret"].values)
        out.append(pd.DataFrame({
            "code": code, "period_end": period,
            "event_day_index": evt["event_day_index"].values,
            "rel_day": evt["rel_day"].values, "ar": ar,
        }))
    ar_df = pd.concat(out, ignore_index=True)
    con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM ar_df")


def main() -> int:
    con = duckdb.connect(str(DB))
    rows = []

    # Baseline (steps 7/8/10) — should reproduce +4.02% / t=3.14 exactly
    rows.append(("baseline (market model)", *evaluate(con, "abnormal")))

    # Check 1: market-adjusted returns, beta forced to 1
    con.execute("""
        CREATE OR REPLACE TABLE abnormal_madj AS
        SELECT p.code, p.period_end, p.event_day_index, p.rel_day,
               p.ret - p.mkt_ret AS ar
        FROM panel p
        JOIN usable_events u USING (code, period_end, event_day_index)
        WHERE p.rel_day BETWEEN -1 AND 60
    """)
    rows.append(("market-adjusted (beta=1)", *evaluate(con, "abnormal_madj")))

    # Check 2: clean index, excluding stocks mid-event
    con.execute("""
        CREATE OR REPLACE TABLE clean_market AS
        SELECT r.date, r.day_index, AVG(r.ret) AS mkt_ret
        FROM returns r
        WHERE r.ret IS NOT NULL AND ABS(r.ret) < 0.5
          AND NOT EXISTS (
              SELECT 1 FROM events e
              WHERE e.code = r.code
                AND r.day_index BETWEEN e.event_day_index - 1 AND e.event_day_index + 60
          )
        GROUP BY r.date, r.day_index
    """)
    fit_abnormal(con, """
        SELECT e.code, e.period_end, e.event_day_index,
               r.day_index, r.day_index - e.event_day_index AS rel_day,
               r.ret, cm.mkt_ret
        FROM events e
        JOIN usable_events u USING (code, period_end, event_day_index)
        JOIN returns r
          ON r.code = e.code
         AND r.day_index BETWEEN e.event_day_index - 150 AND e.event_day_index + 60
        JOIN clean_market cm ON cm.day_index = r.day_index
        WHERE r.ret IS NOT NULL
    """, "abnormal_clean")
    rows.append(("clean index (excl. mid-event stocks)", *evaluate(con, "abnormal_clean")))

    # Check 3: liquidity filter, drop bottom turnover decile
    con.execute("""
        CREATE OR REPLACE TEMP TABLE liquidity AS
        SELECT code, MEDIAN(turnover) AS med_turnover
        FROM prices GROUP BY code
    """)
    cutoff = con.sql("SELECT QUANTILE_CONT(med_turnover, 0.1) FROM liquidity").fetchone()[0]
    con.execute(f"""
        CREATE OR REPLACE TABLE abnormal_liquid AS
        SELECT a.* FROM abnormal a
        JOIN liquidity l USING (code)
        WHERE l.med_turnover > {cutoff}
    """)
    rows.append(("liquidity filter (drop bottom decile)", *evaluate(con, "abnormal_liquid")))

    print(f"{'specification':<38} {'Q5-Q1 drift':>12} {'clustered t':>12} {'N':>8}")
    for name, spread, t_naive, t_clustered, n in rows:
        print(f"{name:<38} {spread*100:>+11.2f}% {t_clustered:>12.2f} {n:>8}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
