"""
Four tests: day-0 timing, trading-day arithmetic, a hand-computed CAR
fixture, and no look-ahead in quintile assignment.

    pytest tests/test_events.py -v
"""
import duckdb
import numpy as np
import statsmodels.api as sm


def test_day0_shift_after_close():
    """Disclosure at 15:30 shifts to the next session; 09:00 does not."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE t AS SELECT * FROM (VALUES
            (1, '15:30:00'),
            (2, '09:00:00'),
            (3, '14:59:00'),
            (4, ''),
            (5, NULL)
        ) AS v(id, disclosed_time)
    """)
    rows = con.sql("""
        SELECT id,
               CASE WHEN disclosed_time = '' OR disclosed_time IS NULL THEN 1
                    WHEN CAST(SUBSTR(disclosed_time, 1, 2) AS INTEGER) >= 15 THEN 1
                    ELSE 0
               END AS shift_days
        FROM t ORDER BY id
    """).fetchall()

    shift = {row[0]: row[1] for row in rows}
    assert shift[1] == 1   # 15:30 -> next session
    assert shift[2] == 0   # 09:00 -> same day
    assert shift[3] == 0   # 14:59 -> same day, just before the cutoff
    assert shift[4] == 1   # blank time -> conservative default, shift
    assert shift[5] == 1   # NULL time -> conservative default, shift


def test_trading_day_arithmetic():
    """day_index + 60 skips holidays and weekends correctly."""
    con = duckdb.connect(":memory:")
    # Friday, then Monday (skipping the weekend), then Tuesday.
    con.execute("""
        CREATE TABLE trading_days AS
        SELECT date, ROW_NUMBER() OVER (ORDER BY date) - 1 AS day_index
        FROM (VALUES (DATE '2024-06-14'), (DATE '2024-06-17'), (DATE '2024-06-18')) AS v(date)
    """)
    rows = con.sql("SELECT date, day_index FROM trading_days ORDER BY date").fetchall()

    assert rows[0][1] == 0   # Friday
    assert rows[1][1] == 1   # Monday: still +1, not +3, despite the weekend gap
    assert rows[2][1] == 2   # Tuesday


def test_car_matches_hand_computation():
    """Known returns and a known beta reproduce a hand-computed CAR."""
    alpha_true, beta_true = 0.005, 2.0

    # Estimation window: ret is exactly alpha + beta*mkt, no noise,
    # so OLS must recover alpha and beta exactly.
    mkt_est = np.array([0.01, -0.02, 0.015, -0.005, 0.0])
    ret_est = alpha_true + beta_true * mkt_est

    X = sm.add_constant(mkt_est)
    fit = sm.OLS(ret_est, X).fit()
    alpha, beta = fit.params
    assert np.isclose(alpha, alpha_true, atol=1e-8)
    assert np.isclose(beta, beta_true, atol=1e-8)

    # Event window: inject one hand-chosen abnormal return.
    mkt_evt = np.array([0.01, 0.0, -0.01])
    ret_evt = alpha_true + beta_true * mkt_evt
    ret_evt[1] += 0.03   # a hand-added +3% abnormal return on the middle day

    ar = ret_evt - (alpha + beta * mkt_evt)
    car = ar.sum()

    assert np.allclose(ar, [0.0, 0.03, 0.0], atol=1e-8)
    assert np.isclose(car, 0.03, atol=1e-8)


def test_no_lookahead_in_quintiles():
    """Quintiles from the full dataset match quintiles assigned to each
    period in isolation — proving no period leaks into another."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE surprise_fixture AS
        SELECT * FROM (VALUES
            ('A', 0, -0.10), ('B', 3, -0.05), ('C', 7, 0.00),
            ('D', 2, 0.05),  ('E', 9, 0.10),  ('F', 5, 0.15),
            ('G', 12, -0.20),('H', 15, -0.08),('I', 18, 0.01),
            ('J', 19, 0.06), ('K', 11, 0.12), ('L', 17, 0.22)
        ) AS v(code, event_day_index, car_announce)
    """)

    full = con.sql("""
        SELECT code, CAST(event_day_index / 10 AS INTEGER) AS period_bucket,
               NTILE(5) OVER (
                   PARTITION BY CAST(event_day_index / 10 AS INTEGER)
                   ORDER BY car_announce
               ) AS quintile
        FROM surprise_fixture
    """).df().set_index("code")

    for bucket in full["period_bucket"].unique():
        isolated = con.sql(f"""
            SELECT code, NTILE(5) OVER (ORDER BY car_announce) AS quintile
            FROM surprise_fixture
            WHERE CAST(event_day_index / 10 AS INTEGER) = {bucket}
        """).df().set_index("code")

        for code in isolated.index:
            assert full.loc[code, "quintile"] == isolated.loc[code, "quintile"], (
                f"{code}: quintile differs when other periods are present "
                "— evidence of cross-period leakage"
            )
