"""Market model per event -> abnormal returns. python src/events.py"""
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "jp.duckdb"


def main() -> int:
    con = duckdb.connect(str(DB))
    panel = con.sql("""
        SELECT p.* FROM panel p
        JOIN usable_events u USING (code, period_end, event_day_index)
    """).df()
    print(f"panel: {len(panel):,} rows, {panel.groupby(['code','period_end']).ngroups:,} events")

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
            "code": code,
            "period_end": period,
            "event_day_index": evt["event_day_index"].values,
            "rel_day": evt["rel_day"].values,
            "ar": ar,
            "beta": beta,
        }))

    ar_df = pd.concat(out, ignore_index=True)
    con.execute("CREATE OR REPLACE TABLE abnormal AS SELECT * FROM ar_df")
    print(f"abnormal: {len(ar_df):,} rows, {ar_df.groupby(['code','period_end']).ngroups:,} events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
