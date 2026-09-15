CREATE TABLE IF NOT EXISTS prices (
    code        VARCHAR,
    date        DATE,
    close       DOUBLE,
    volume      DOUBLE,
    turnover    DOUBLE
);

CREATE TABLE IF NOT EXISTS companies (
    code            VARCHAR,
    name            VARCHAR,
    sector          VARCHAR,
    market_segment  VARCHAR
);

CREATE TABLE IF NOT EXISTS disclosures (
    code            VARCHAR,
    disclosed_date  DATE,
    disclosed_time  VARCHAR,
    doc_type        VARCHAR,
    period_end      VARCHAR
);

CREATE TABLE IF NOT EXISTS trading_days (
    date       DATE,
    day_index  INTEGER
);