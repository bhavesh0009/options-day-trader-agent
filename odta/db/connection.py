import duckdb
from functools import lru_cache


@lru_cache(maxsize=1)
def get_db_connection(db_path: str = None) -> duckdb.DuckDBPyConnection:
    if db_path is None:
        from odta.models.config import load_config
        db_path = load_config().database.path
    conn = duckdb.connect(db_path)
    return conn
