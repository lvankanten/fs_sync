import logging
from datetime import datetime, timezone

import pyodbc

log = logging.getLogger(__name__)

# SQL type to use for each Freshservice custom field type
_CF_TYPE_MAP = {
    "custom_checkbox": "BIT",
    "custom_date": "DATETIMEOFFSET(0)",
    "custom_datetime": "DATETIMEOFFSET(0)",
    "custom_number": "DECIMAL(18,4)",
    "custom_decimal": "DECIMAL(18,4)",
}
_CF_TYPE_DEFAULT = "NVARCHAR(MAX)"


def get_conn(server: str, database: str, username: str, password: str) -> pyodbc.Connection:
    drivers = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server",
    ]
    for driver in drivers:
        try:
            conn = pyodbc.connect(
                f"DRIVER={{{driver}}};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"UID={username};"
                f"PWD={password};"
                "TrustServerCertificate=yes;"
                "Encrypt=yes;",
                autocommit=False,
            )
            log.debug("Connected via '%s'", driver)
            return conn
        except pyodbc.Error:
            continue
    raise RuntimeError("No suitable ODBC driver found. Install 'ODBC Driver 17/18 for SQL Server'.")


def merge_rows(conn: pyodbc.Connection, table: str, key_col: str, rows: list[dict]) -> int:
    """
    MERGE rows into table using key_col as the match key.
    Inserts new rows, updates changed rows. Does not delete.
    Returns number of rows processed.
    """
    if not rows:
        return 0

    cols = list(rows[0].keys())
    non_key = [c for c in cols if c != key_col]

    col_list  = ", ".join(f"[{c}]" for c in cols)
    src_list  = ", ".join(f"s.[{c}]" for c in cols)
    val_place = ", ".join("?" for _ in cols)
    set_clause = ", ".join(f"t.[{c}] = s.[{c}]" for c in non_key)

    sql = f"""
        MERGE [{table}] AS t
        USING (VALUES ({val_place})) AS s ({col_list})
        ON t.[{key_col}] = s.[{key_col}]
        WHEN MATCHED THEN
            UPDATE SET {set_clause}
        WHEN NOT MATCHED THEN
            INSERT ({col_list}) VALUES ({src_list});
    """

    cur = conn.cursor()
    for row in rows:
        vals = [row[c] for c in cols]
        cur.execute(sql, vals)
    conn.commit()
    return len(rows)


def get_last_synced_at(conn: pyodbc.Connection, entity: str) -> datetime | None:
    """Returns the last successful sync watermark for the given entity, or None."""
    cur = conn.cursor()
    cur.execute(
        "SELECT last_synced_at FROM sync_log WHERE entity = ? AND status = 'success'",
        entity,
    )
    row = cur.fetchone()
    if row and row[0]:
        val = row[0]
        # pyodbc may return datetime or datetimeoffset string
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(str(val))
    return None


def write_sync_log(
    conn: pyodbc.Connection,
    entity: str,
    status: str,
    rows: int,
    last_synced_at: datetime = None,
    error: str = None,
) -> None:
    """Upsert a row in sync_log for the given entity."""
    cur = conn.cursor()
    cur.execute(
        """
        MERGE sync_log AS t
        USING (VALUES (?, ?, ?, ?, ?, ?)) AS s (entity, last_synced_at, last_run_at, rows_affected, status, error_message)
        ON t.entity = s.entity
        WHEN MATCHED THEN
            UPDATE SET
                last_synced_at = s.last_synced_at,
                last_run_at    = s.last_run_at,
                rows_affected  = s.rows_affected,
                status         = s.status,
                error_message  = s.error_message
        WHEN NOT MATCHED THEN
            INSERT (entity, last_synced_at, last_run_at, rows_affected, status, error_message)
            VALUES (s.entity, s.last_synced_at, s.last_run_at, s.rows_affected, s.status, s.error_message);
        """,
        entity,
        last_synced_at,
        datetime.now(timezone.utc),
        rows,
        status,
        error,
    )
    conn.commit()


def ensure_custom_field_column(
    conn: pyodbc.Connection, field_name: str, field_type: str
) -> None:
    """
    Add a cf_<field_name> column to the tickets table if it does not exist.
    field_type is the Freshservice field_type string (e.g. 'custom_text').
    """
    col_name = f"cf_{field_name}" if not field_name.startswith("cf_") else field_name
    sql_type = _CF_TYPE_MAP.get(field_type, _CF_TYPE_DEFAULT)

    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'tickets' AND COLUMN_NAME = ?
        """,
        col_name,
    )
    if cur.fetchone() is None:
        log.info("Adding column [%s] %s to tickets table.", col_name, sql_type)
        cur.execute(f"ALTER TABLE tickets ADD [{col_name}] {sql_type} NULL")
        conn.commit()


def run_schema_file(conn: pyodbc.Connection, schema_path: str) -> None:
    """Execute all statements in schema.sql against the connection."""
    with open(schema_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Strip comment-only lines so they don't cause DDL blocks to be skipped
    cleaned = "".join(line for line in lines if not line.strip().startswith("--"))

    # Split on blank lines; each chunk is one executable statement
    statements = [s.strip() for s in cleaned.split("\n\n") if s.strip()]
    cur = conn.cursor()
    for stmt in statements:
        try:
            cur.execute(stmt)
            conn.commit()
        except pyodbc.Error as e:
            log.warning("Schema statement warning (may be harmless): %s", e)
    log.info("Schema setup complete.")
