"""
Plot cumulative abnormal return by surprise quintile: the headline chart.

    python src/plot_caar.py
"""
import sys
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "jp.duckdb"
FIG = REPO / "figures" / "caar_by_quintile.png"


def main() -> int:
    con = duckdb.connect(str(DB))
    caar = con.sql("SELECT * FROM caar ORDER BY quintile, rel_day").df()
    caar["caar"] = caar.groupby("quintile")["aar"].cumsum()

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for q in sorted(caar.quintile.unique()):
        d = caar[caar.quintile == q]
        ax.plot(d.rel_day, d.caar * 100, label=f"Q{q}", linewidth=1.8)

    ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
    ax.axhline(0, color="black", linewidth=0.6)
    ax.set_xlabel("Trading days relative to announcement")
    ax.set_ylabel("Cumulative abnormal return (%)")
    ax.set_title("Post-earnings-announcement drift, TSE Prime\nby announcement-window surprise quintile")
    ax.legend(title="Surprise quintile")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(FIG), dpi=160)
    print(f"saved {FIG}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
