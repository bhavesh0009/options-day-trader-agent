import duckdb


SEQUENCES_DDL = [
    "CREATE SEQUENCE IF NOT EXISTS trade_diary_id_seq",
    "CREATE SEQUENCE IF NOT EXISTS decision_log_id_seq",
    "CREATE SEQUENCE IF NOT EXISTS paper_positions_id_seq",
]

NEW_TABLES_DDL = [
    """
    CREATE TABLE IF NOT EXISTS ban_list (
        symbol VARCHAR NOT NULL,
        ban_date DATE NOT NULL,
        PRIMARY KEY (symbol, ban_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trade_diary (
        id INTEGER DEFAULT nextval('trade_diary_id_seq') PRIMARY KEY,
        trade_date DATE NOT NULL,
        symbol VARCHAR,
        option_symbol VARCHAR,
        entry_time TIMESTAMP,
        exit_time TIMESTAMP,
        entry_price DECIMAL(12,2),
        exit_price DECIMAL(12,2),
        quantity INTEGER,
        direction VARCHAR,
        pnl DECIMAL(12,2),
        entry_rationale TEXT,
        exit_rationale TEXT,
        market_conditions TEXT,
        learnings TEXT,
        mistakes TEXT,
        daily_summary TEXT,
        tags VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS decision_log (
        id INTEGER DEFAULT nextval('decision_log_id_seq') PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        trade_date DATE NOT NULL,
        phase VARCHAR NOT NULL,
        action_type VARCHAR NOT NULL,
        symbol VARCHAR,
        summary TEXT NOT NULL,
        reasoning TEXT,
        data_points TEXT,
        outcome VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_positions (
        id INTEGER DEFAULT nextval('paper_positions_id_seq') PRIMARY KEY,
        trade_date DATE NOT NULL,
        symbol VARCHAR NOT NULL,
        option_symbol VARCHAR NOT NULL,
        transaction_type VARCHAR NOT NULL,
        quantity INTEGER NOT NULL,
        entry_price DECIMAL(12,2) NOT NULL,
        entry_time TIMESTAMP NOT NULL,
        exit_price DECIMAL(12,2),
        exit_time TIMESTAMP,
        status VARCHAR DEFAULT 'OPEN',
        pnl DECIMAL(12,2)
    )
    """,
]

SCHEMA_MIGRATIONS = [
    "ALTER TABLE fno_stocks ADD COLUMN IF NOT EXISTS sector VARCHAR",
    "ALTER TABLE fno_stocks ADD COLUMN IF NOT EXISTS industry VARCHAR",
]


def initialize_database(db_path: str) -> None:
    """Create new tables and apply schema migrations."""
    conn = duckdb.connect(db_path)

    # Create sequences first (tables reference them)
    for seq in SEQUENCES_DDL:
        try:
            conn.execute(seq)
        except Exception:
            pass

    # Drop and recreate tables that lack auto-increment
    # (only if they exist AND have 0 rows — safe for fresh setup)
    for table_name in ["trade_diary", "decision_log", "paper_positions"]:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            if count == 0:
                # Check if id column has a default — if not, recreate
                cols = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
                id_col = [c for c in cols if c[1] == "id"]
                if id_col and id_col[0][4] is None:
                    conn.execute(f"DROP TABLE {table_name}")
        except Exception:
            pass

    for ddl in NEW_TABLES_DDL:
        conn.execute(ddl)

    for migration in SCHEMA_MIGRATIONS:
        try:
            conn.execute(migration)
        except Exception:
            pass

    conn.close()
