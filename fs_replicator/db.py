import logging
from datetime import datetime, timezone

import pymssql

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


def get_conn(server: str, database: str, username: str, password: str) -> pymssql.Connection:
    conn = pymssql.connect(
        server=server,
        user=username,
        password=password,
        database=database,
        autocommit=False,
    )
    log.debug("Connected via pymssql")
    return conn


def merge_rows(conn: pymssql.Connection, table: str, key_col: str, rows: list[dict]) -> int:
    """
    Upsert rows into table using key_col as the match key.
    Inserts new rows, updates changed rows. Does not delete.
    Returns number of rows processed.
    """
    if not rows:
        return 0

    cols = list(rows[0].keys())
    non_key = [c for c in cols if c != key_col]
    col_list     = ", ".join(f"[{c}]" for c in cols)
    placeholders = ", ".join("%s" for _ in cols)
    set_clause   = ", ".join(f"[{c}] = %s" for c in non_key)

    update_sql = f"UPDATE [{table}] SET {set_clause} WHERE [{key_col}] = %s"
    insert_sql = f"INSERT INTO [{table}] ({col_list}) VALUES ({placeholders})"

    cur = conn.cursor()
    for row in rows:
        non_key_vals = [row[c] for c in non_key]
        key_val      = row[key_col]
        try:
            cur.execute(update_sql, non_key_vals + [key_val])
        except Exception as e:
            log.error("UPDATE failed on %s=%s: %s", key_col, key_val, e)
            log.error("Params: %s", list(zip(non_key, non_key_vals)) + [(key_col, key_val)])
            raise
        if cur.rowcount == 0:
            try:
                cur.execute(insert_sql, [row[c] for c in cols])
            except Exception as e:
                log.error("INSERT failed on %s=%s: %s", key_col, key_val, e)
                log.error("Params: %s", list(zip(cols, [row[c] for c in cols])))
                raise
    conn.commit()
    return len(rows)


def get_last_synced_at(conn: pymssql.Connection, entity: str) -> datetime | None:
    """Returns the last successful sync watermark for the given entity, or None."""
    cur = conn.cursor()
    cur.execute(
        "SELECT last_synced_at FROM sync_log WHERE entity = %s AND status = 'success'",
        entity,
    )
    row = cur.fetchone()
    cur.close()
    if row and row[0]:
        dt = row[0]
        if isinstance(dt, datetime):
            return dt
        return datetime.fromisoformat(str(dt))
    return None


def write_sync_log(
    conn: pymssql.Connection,
    entity: str,
    status: str,
    rows: int,
    last_synced_at: datetime = None,
    error: str = None,
    cursor_id: int = None,
) -> None:
    """Upsert a row in sync_log for the given entity."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            MERGE sync_log AS t
            USING (VALUES (%s, %s, %s, %s, %s, %s, %s)) AS s (entity, last_synced_at, last_run_at, rows_affected, status, error_message, cursor_id)
            ON t.entity = s.entity
            WHEN MATCHED THEN
                UPDATE SET
                    last_synced_at = s.last_synced_at,
                    last_run_at    = s.last_run_at,
                    rows_affected  = s.rows_affected,
                    status         = s.status,
                    error_message  = s.error_message,
                    cursor_id      = COALESCE(s.cursor_id, t.cursor_id)
            WHEN NOT MATCHED THEN
                INSERT (entity, last_synced_at, last_run_at, rows_affected, status, error_message, cursor_id)
                VALUES (s.entity, s.last_synced_at, s.last_run_at, s.rows_affected, s.status, s.error_message, s.cursor_id);
            """,
            (entity, last_synced_at, datetime.now(timezone.utc), rows, status, error, cursor_id),
        )
        conn.commit()
    finally:
        cur.close()


def get_backfill_cursor(conn: pymssql.Connection, entity: str) -> int | None:
    """Return the last successfully processed parent ID for a backfill entity, or None."""
    cur = conn.cursor()
    cur.execute("SELECT cursor_id FROM sync_log WHERE entity = %s", entity)
    row = cur.fetchone()
    cur.close()
    return row[0] if row and row[0] is not None else None


def clear_backfill_cursor(conn: pymssql.Connection, entity: str) -> None:
    """Explicitly set cursor_id to NULL for the given entity."""
    cur = conn.cursor()
    cur.execute("UPDATE sync_log SET cursor_id = NULL WHERE entity = %s", entity)
    conn.commit()
    cur.close()


def ensure_custom_field_column(
    conn: pymssql.Connection, field_name: str, field_type: str, table: str = "tickets"
) -> None:
    """
    Add a cf_<field_name> column to the given table if it does not exist.
    field_type is the Freshservice field_type string (e.g. 'custom_text').
    """
    col_name = f"cf_{field_name}" if not field_name.startswith("cf_") else field_name
    sql_type = _CF_TYPE_MAP.get(field_type, _CF_TYPE_DEFAULT)

    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (table, col_name),
    )
    if cur.fetchone() is None:
        log.info("Adding column [%s] %s to %s table.", col_name, sql_type, table)
        cur.execute(f"ALTER TABLE [{table}] ADD [{col_name}] {sql_type} NULL")
        conn.commit()


def run_schema_file(conn: pymssql.Connection, schema_path: str) -> None:
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
        except Exception as e:
            log.warning("Schema statement warning (may be harmless): %s", e)
    log.info("Schema setup complete.")
