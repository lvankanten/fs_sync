"""
Workload field sync — captures planned_effort / planned_start_date /
planned_end_date for open tickets independently of the main replicator.

These fields don't bump ticket.updated_at when changed, so they're invisible
to the main replicator's incremental sync. This script polls them on its own
schedule, writing to the ticket_workload table.

Usage:
  python workload_sync.py                       # refresh all open tickets
  python workload_sync.py --older-than-hours 4  # only refresh rows not checked in N hours
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import db
from fs_client import FreshserviceClient
from syncers import _parse_dt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).parent / "workload_sync.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def load_env() -> dict:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        log.error(".env file not found at %s", env_path)
        sys.exit(1)
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())
    return {
        "api_key":  os.environ["FRESHSERVICE_APIKEY"],
        "domain":   os.environ["FRESHSERVICE_DOMAIN"],
        "server":   os.environ["SQL_SERVER"],
        "database": os.environ.get("FS_DATABASE", "FS"),
        "username": os.environ["SQL_USERNAME"],
        "password": os.environ["SQL_PASSWORD"],
    }


def get_target_ticket_ids(conn, older_than_hours: int | None) -> list[int]:
    """Open tickets whose workload row is missing or older than N hours."""
    cur = conn.cursor()
    if older_than_hours is None:
        cur.execute("SELECT id FROM tickets WHERE status NOT IN (4, 5) ORDER BY id")
    else:
        cur.execute(
            """
            SELECT t.id
            FROM tickets t
            LEFT JOIN ticket_workload w ON w.ticket_id = t.id
            WHERE t.status NOT IN (4, 5)
              AND (w.last_checked_at IS NULL
                   OR w.last_checked_at < DATEADD(hour, -%s, SYSDATETIMEOFFSET()))
            ORDER BY t.id
            """,
            older_than_hours,
        )
    ids = [row[0] for row in cur.fetchall()]
    cur.close()
    return ids


def upsert_workload(conn, ticket_id: int, t: dict) -> None:
    """UPDATE existing row or INSERT new — pymssql + no MERGE = manual upsert."""
    planned_effort = t.get("planned_effort")
    planned_start  = _parse_dt(t.get("planned_start_date"))
    planned_end    = _parse_dt(t.get("planned_end_date"))

    cur = conn.cursor()
    cur.execute(
        """
        UPDATE ticket_workload
        SET planned_effort = %s, planned_start_date = %s, planned_end_date = %s,
            last_checked_at = SYSDATETIMEOFFSET()
        WHERE ticket_id = %s
        """,
        (planned_effort, planned_start, planned_end, ticket_id),
    )
    if cur.rowcount == 0:
        cur.execute(
            """
            INSERT INTO ticket_workload
                (ticket_id, planned_effort, planned_start_date, planned_end_date, last_checked_at)
            VALUES (%s, %s, %s, %s, SYSDATETIMEOFFSET())
            """,
            (ticket_id, planned_effort, planned_start, planned_end),
        )
    conn.commit()
    cur.close()


def main():
    parser = argparse.ArgumentParser(description="Sync workload fields (planned_*) to ticket_workload table")
    parser.add_argument("--older-than-hours", type=int, default=None,
                        help="Only refresh tickets whose last_checked_at is older than N hours (default: refresh all)")
    args = parser.parse_args()

    cfg = load_env()
    client = FreshserviceClient(cfg["api_key"], cfg["domain"])
    conn = db.get_conn(cfg["server"], cfg["database"], cfg["username"], cfg["password"])

    ticket_ids = get_target_ticket_ids(conn, args.older_than_hours)
    if not ticket_ids:
        log.info("No open tickets need refresh.")
        conn.close()
        return

    log.info("Refreshing workload fields for %d open tickets...", len(ticket_ids))
    fetched = 0
    failed = 0
    for i, tid in enumerate(ticket_ids):
        try:
            t = client.get_ticket(tid)
            time.sleep(1)
        except Exception as e:
            log.warning("  Could not fetch ticket %d: %s", tid, e)
            failed += 1
            continue
        try:
            upsert_workload(conn, tid, t)
            fetched += 1
        except Exception as e:
            log.warning("  Could not upsert workload for ticket %d: %s", tid, e)
            failed += 1
        if (i + 1) % 100 == 0:
            log.info("  Processed %d / %d tickets...", i + 1, len(ticket_ids))

    log.info("Done. %d tickets refreshed, %d failed.", fetched, failed)
    conn.close()


if __name__ == "__main__":
    main()
