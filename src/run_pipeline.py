"""
Run the entire pipeline end to end, from a fresh clone to the headline chart.

    python src/run_pipeline.py
"""
import sys

import build_events
import build_panel
import events
import fetch_all
import load
import plot_caar
import quintiles
import returns
import robustness
import stats


def main() -> int:
    steps = [
        ("fetching ~2 years of bars and disclosures", fetch_all.main),
        ("loading the raw cache into DuckDB", load.main),
        ("computing returns and the market index", returns.main),
        ("building the events table", build_events.main),
        ("building the event panel", build_panel.main),
        ("market model -> abnormal returns", events.main),
        ("surprise quintiles and CAAR", quintiles.main),
        ("plotting the headline chart", plot_caar.main),
        ("significance tests", stats.main),
        ("robustness checks", robustness.main),
    ]
    for label, step in steps:
        print(f"\n=== {label} ===")
        step()
    return 0


if __name__ == "__main__":
    sys.exit(main())
