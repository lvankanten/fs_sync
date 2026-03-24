"""
Freshservice → SQL Server replicator

Usage:
  python replicator.py           # incremental run (changes since last sync)
  python replicator.py --full    # force full reload of all entities
  python replicator.py --setup   # create tables in FS database, then exit
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# ── logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).parent / "replicator.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ── env loading ───────────────────────────────────────────────────────────────

def load_env() -> dict:
    """
    Load config from .env in the same directory as this script.
    Environment variables always take precedence.
    """
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        log.error(".env file not found at %s", env_path)
        sys.exit(1)
    log.debug("Loading .env from %s", env_path)
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

    required = ["FRESHSERVICE_APIKEY", "FRESHSERVICE_DOMAIN", "SQL_SERVER", "SQL_USERNAME", "SQL_PASSWORD"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        log.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)

    return {
        "api_key":   os.environ["FRESHSERVICE_APIKEY"],
        "domain":    os.environ["FRESHSERVICE_DOMAIN"],
        "server":    os.environ["SQL_SERVER"],
        "database":  os.environ.get("FS_DATABASE", "FS"),
        "username":  os.environ["SQL_USERNAME"],
        "password":  os.environ["SQL_PASSWORD"],
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Freshservice → SQL Server replicator")
    parser.add_argument("--setup", action="store_true", help="Create tables in FS database and exit")
    parser.add_argument("--reset", action="store_true", help="Drop all tables then recreate (implies --setup). Use when schema changes.")
    parser.add_argument("--full",  action="store_true", help="Force full reload (ignore watermarks)")
    args = parser.parse_args()

    cfg = load_env()

    import db
    import syncers
    from fs_client import FreshserviceClient

    conn = db.get_conn(cfg["server"], cfg["database"], cfg["username"], cfg["password"])
    log.info("Connected to %s / %s", cfg["server"], cfg["database"])

    # ── setup / reset mode ────────────────────────────────────────────────────
    if args.reset or args.setup:
        if args.reset:
            log.info("Dropping all tables...")
            drop_order = [
                "conversations", "tickets",
                "agent_group_members", "agent_groups",
                "requester_group_members", "requester_groups",
                "agents", "requesters", "sync_log",
            ]
            cur = conn.cursor()
            for table in drop_order:
                cur.execute(f"IF OBJECT_ID('{table}', 'U') IS NOT NULL DROP TABLE [{table}]")
                conn.commit()
                log.info("  Dropped %s", table)
        schema_path = Path(__file__).parent / "schema.sql"
        log.info("Running schema setup from %s ...", schema_path)
        db.run_schema_file(conn, str(schema_path))
        conn.close()
        return

    client = FreshserviceClient(cfg["api_key"], cfg["domain"])

    # Sync order respects FK constraints: agents/requesters before tickets,
    # tickets before conversations.
    ENTITIES = [
        ("agents",           lambda: syncers.sync_agents(conn, client)),
        ("requesters",       lambda: syncers.sync_requesters(conn, client)),
        ("agent_groups",     lambda: syncers.sync_agent_groups(conn, client)),
        ("requester_groups", lambda: syncers.sync_requester_groups(conn, client)),
    ]

    errors = []

    # ── non-ticket entities ───────────────────────────────────────────────────
    for entity, fn in ENTITIES:
        try:
            rows = fn()
            db.write_sync_log(conn, entity, "success", rows)
        except Exception as e:
            log.error("%s sync failed: %s", entity, e)
            db.write_sync_log(conn, entity, "error", 0, error=str(e))
            errors.append(entity)

    # ── tickets ───────────────────────────────────────────────────────────────
    try:
        last_tickets = None if args.full else db.get_last_synced_at(conn, "tickets")
        rows, ticket_ids, run_start = syncers.sync_tickets(
            conn, client, last_tickets, fetch_details=not args.full
        )
        db.write_sync_log(conn, "tickets", "success", rows, last_synced_at=run_start)
    except Exception as e:
        log.error("tickets sync failed: %s", e)
        db.write_sync_log(conn, "tickets", "error", 0, error=str(e))
        errors.append("tickets")
        ticket_ids = []
        run_start = None

    # ── conversations ─────────────────────────────────────────────────────────
    if args.full:
        log.info("Skipping conversations on full load (will sync on incremental runs).")
        ticket_ids = []

    if ticket_ids:
        try:
            rows = syncers.sync_conversations(conn, client, ticket_ids)
            db.write_sync_log(
                conn, "conversations", "success", rows,
                last_synced_at=run_start,
            )
        except Exception as e:
            log.error("conversations sync failed: %s", e)
            db.write_sync_log(conn, "conversations", "error", 0, error=str(e))
            errors.append("conversations")
    else:
        log.info("No tickets to sync conversations for.")

    conn.close()

    if errors:
        log.warning("Completed with errors in: %s", ", ".join(errors))
        sys.exit(1)
    else:
        log.info("All entities synced successfully.")


if __name__ == "__main__":
    main()
