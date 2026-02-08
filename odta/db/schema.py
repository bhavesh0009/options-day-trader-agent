import duckdb


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
        id INTEGER PRIMARY KEY,
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
        id INTEGER PRIMARY KEY,
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
        id INTEGER PRIMARY KEY,
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
    # Add sector and industry columns to fno_stocks if they don't exist
    """
    ALTER TABLE fno_stocks ADD COLUMN IF NOT EXISTS sector VARCHAR
    """,
    """
    ALTER TABLE fno_stocks ADD COLUMN IF NOT EXISTS industry VARCHAR
    """,
]


def initialize_database(db_path: str) -> None:
    """Create new tables and apply schema migrations."""
    conn = duckdb.connect(db_path)

    for ddl in NEW_TABLES_DDL:
        conn.execute(ddl)

    for migration in SCHEMA_MIGRATIONS:
        try:
            conn.execute(migration)
        except Exception:
            pass  # Column already exists or table doesn't exist yet

    # Create sequences for auto-increment IDs if they don't exist
    for table in ["trade_diary", "decision_log", "paper_positions"]:
        seq_name = f"{table}_id_seq"
        try:
            conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq_name}")
        except Exception:
            pass

    conn.close()
