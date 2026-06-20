"""
Freshservice → SQL Server replicator

Usage:
  python replicator.py           # loop incremental continuously (Ctrl-C to stop)
  python replicator.py --once    # single incremental run, then exit
  python replicator.py --full    # force full reload of all entities
  python replicator.py --setup   # create tables in FS database, then exit
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
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
    parser.add_argument("--setup",              action="store_true", help="Create tables in FS database and exit")
    parser.add_argument("--reset",              action="store_true", help="Drop all tables then recreate (implies --setup). Use when schema changes.")
    parser.add_argument("--truncate",           action="store_true", help="Truncate all tables (keep schema). Use for restore simulation or migrating to a new database instance.")
    parser.add_argument("--full",               action="store_true", help="Force full reload (ignore watermarks)")
    parser.add_argument("--test",               action="store_true", help="Smoke test: sync first 300 tickets/problems/changes/releases, write real watermarks")
    parser.add_argument("--backfill-sub-entities", action="store_true", help="Fetch conversations, tasks, and time entries for ALL tickets/problems/changes/releases in DB")
    parser.add_argument("--once",               action="store_true", help="Run a single incremental and exit (default is to loop continuously)")
    parser.add_argument("--interval-seconds",   type=int, default=300, help="Seconds to sleep between iterations when looping (default: 300)")
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
                "project_tasks", "project_members", "projects",
                "release_time_entries", "release_tasks", "release_conversations", "releases",
                "change_time_entries", "change_tasks", "change_conversations", "changes",
                "problem_time_entries", "problem_tasks", "problem_conversations", "problems",
                "ticket_activities", "ticket_time_entries", "ticket_tasks", "conversations", "tickets",
                "agent_group_members", "agent_groups",
                "requester_group_members", "requester_groups",
                "agents", "requesters", "departments", "locations", "sla_policies", "roles", "sync_log",
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

    # ── truncate mode ─────────────────────────────────────────────────────────
    if args.truncate:
        truncate_order = [
            "conversations", "ticket_tasks", "ticket_time_entries", "ticket_activities",
            "problem_conversations", "problem_tasks", "problem_time_entries",
            "change_conversations", "change_tasks", "change_time_entries",
            "release_conversations", "release_tasks", "release_time_entries",
            "project_tasks", "project_members",
            "tickets", "problems", "changes", "releases", "projects",
            "agent_group_members", "agent_groups",
            "requester_group_members", "requester_groups",
            "agents", "requesters", "departments", "locations", "sla_policies", "roles", "sync_log",
        ]
        log.info("Truncating all tables (schema preserved)...")
        cur = conn.cursor()
        for table in truncate_order:
            cur.execute(f"DELETE FROM [{table}]")
            conn.commit()
            log.info("  Truncated %s", table)
        log.info("All tables truncated. Run --full then --backfill-sub-entities to reload.")
        conn.close()
        return

    # ── backfill sub-entities mode ────────────────────────────────────────────
    if args.backfill_sub_entities:
        _CHUNK = 500  # reconnect every N parent IDs to avoid connection timeout

        def _fresh_conn():
            return db.get_conn(cfg["server"], cfg["database"], cfg["username"], cfg["password"])

        def _load_ids(table, id_col="id"):
            c = _fresh_conn()
            cur = c.cursor()
            cur.execute(f"SELECT [{id_col}] FROM [{table}] ORDER BY [{id_col}]")
            ids = [row[0] for row in cur.fetchall()]
            c.close()
            return ids

        def _backfill_entity(entity, all_ids, sync_fn_factory):
            """Process all_ids in chunks, reconnecting between chunks. Resumes from cursor if
            interrupted. Entities already finished earlier in this campaign are skipped entirely."""
            if entity in completed_entities:
                log.info("  %s: already backfilled this campaign — skipping.", entity)
                return 0
            # Read resume cursor
            c0 = _fresh_conn()
            cursor_id = db.get_backfill_cursor(c0, entity)
            c0.close()
            if cursor_id is not None:
                original_count = len(all_ids)
                all_ids = [i for i in all_ids if i > cursor_id]
                log.info("  %s: resuming after cursor %d — skipping %d already-done IDs, %d remaining.",
                         entity, cursor_id, original_count - len(all_ids), len(all_ids))

            total = 0
            for i in range(0, len(all_ids), _CHUNK):
                chunk = all_ids[i:i + _CHUNK]
                c = _fresh_conn()
                try:
                    rows = sync_fn_factory(c)(chunk)
                    total += rows
                    db.write_sync_log(c, entity, "success", total, cursor_id=chunk[-1])
                    log.info("  %s: chunk %d-%d done (%d rows so far).",
                             entity, i + 1, i + len(chunk), total)
                except Exception as e:
                    log.error("%s backfill failed at chunk starting %d: %s", entity, i, e)
                    db.write_sync_log(c, entity, "error", total, error=str(e),
                                      cursor_id=chunk[0] - 1 if chunk else cursor_id)
                    c.close()
                    raise
                finally:
                    c.close()
            # Mark entity fully done (also clears the resume cursor) so a backfill resumed
            # after an interruption skips it instead of reprocessing every parent ID.
            c_final = _fresh_conn()
            db.mark_backfill_complete(c_final, entity)
            c_final.close()
            return total

        errors = []
        log.info("=== Backfill sub-entities mode ===")
        backfill_start = datetime.now(timezone.utc)

        # Campaign logic — distinguish "interrupted, now resuming" from "deliberate fresh re-run":
        #   • If EVERY sub-entity is already marked complete, treat this invocation as a brand-new
        #     full backfill: reset the markers and run them all (matches the old always-rerun behavior).
        #   • Otherwise we're resuming an interrupted campaign: skip the entities that already finished
        #     and only process the rest. This avoids re-issuing one API call per parent ID for entities
        #     that completed before the interruption (e.g. a dropped VPN).
        ALL_BACKFILL_ENTITIES = [
            "conversations", "ticket_tasks", "ticket_time_entries", "ticket_activities",
            "problem_conversations", "problem_tasks", "problem_time_entries",
            "change_conversations", "change_tasks", "change_time_entries",
            "release_conversations", "release_tasks", "release_time_entries",
        ]
        c_camp = _fresh_conn()
        completed_entities = {e for e in ALL_BACKFILL_ENTITIES if db.get_backfill_completed(c_camp, e)}
        if len(completed_entities) == len(ALL_BACKFILL_ENTITIES):
            log.info("All sub-entities already backfilled — starting a fresh campaign (resetting completion markers).")
            for e in ALL_BACKFILL_ENTITIES:
                db.clear_backfill_completed(c_camp, e)
            completed_entities = set()
        elif completed_entities:
            log.info("Resuming backfill — %d entities already complete, will be skipped: %s",
                     len(completed_entities), ", ".join(sorted(completed_entities)))
        c_camp.close()

        ticket_ids = _load_ids("tickets")
        log.info("Backfilling sub-entities for %d tickets...", len(ticket_ids))
        for entity, fn_factory in [
            ("conversations",       lambda c: lambda ids: syncers.sync_conversations(c, client, ids)),
            ("ticket_tasks",        lambda c: lambda ids: syncers.sync_ticket_tasks(c, client, ids)),
            ("ticket_time_entries", lambda c: lambda ids: syncers.sync_ticket_time_entries(c, client, ids)),
            ("ticket_activities",   lambda c: lambda ids: syncers.sync_ticket_activities(c, client, ids)),
        ]:
            try:
                rows = _backfill_entity(entity, ticket_ids, fn_factory)
                log.info("%s backfill complete: %d rows.", entity, rows)
            except Exception as e:
                errors.append(entity)

        problem_ids = _load_ids("problems")
        log.info("Backfilling sub-entities for %d problems...", len(problem_ids))
        for entity, fn_factory in [
            ("problem_conversations", lambda c: lambda ids: syncers.sync_problem_conversations(c, client, ids)),
            ("problem_tasks",         lambda c: lambda ids: syncers.sync_problem_tasks(c, client, ids)),
            ("problem_time_entries",  lambda c: lambda ids: syncers.sync_problem_time_entries(c, client, ids)),
        ]:
            try:
                rows = _backfill_entity(entity, problem_ids, fn_factory)
                log.info("%s backfill complete: %d rows.", entity, rows)
            except Exception as e:
                errors.append(entity)

        change_ids = _load_ids("changes")
        log.info("Backfilling sub-entities for %d changes...", len(change_ids))
        for entity, fn_factory in [
            ("change_conversations", lambda c: lambda ids: syncers.sync_change_conversations(c, client, ids)),
            ("change_tasks",         lambda c: lambda ids: syncers.sync_change_tasks(c, client, ids)),
            ("change_time_entries",  lambda c: lambda ids: syncers.sync_change_time_entries(c, client, ids)),
        ]:
            try:
                rows = _backfill_entity(entity, change_ids, fn_factory)
                log.info("%s backfill complete: %d rows.", entity, rows)
            except Exception as e:
                errors.append(entity)

        release_ids = _load_ids("releases")
        log.info("Backfilling sub-entities for %d releases...", len(release_ids))
        for entity, fn_factory in [
            ("release_conversations", lambda c: lambda ids: syncers.sync_release_conversations(c, client, ids)),
            ("release_tasks",         lambda c: lambda ids: syncers.sync_release_tasks(c, client, ids)),
            ("release_time_entries",  lambda c: lambda ids: syncers.sync_release_time_entries(c, client, ids)),
        ]:
            try:
                rows = _backfill_entity(entity, release_ids, fn_factory)
                log.info("%s backfill complete: %d rows.", entity, rows)
            except Exception as e:
                errors.append(entity)

        elapsed = (datetime.now(timezone.utc) - backfill_start).total_seconds()
        hours, remainder = divmod(int(elapsed), 3600)
        minutes, seconds = divmod(remainder, 60)
        conn.close()
        if errors:
            log.warning("Backfill completed with errors in: %s (elapsed: %dh %dm %ds)",
                        ", ".join(errors), hours, minutes, seconds)
            sys.exit(1)
        else:
            log.info("Backfill complete. Elapsed: %dh %dm %ds.", hours, minutes, seconds)
        return

    # ── single-shot or loop ───────────────────────────────────────────────────
    # Loop is the default. --once, --full, and --test all run a single cycle.
    should_loop = not (args.once or args.full or args.test)
    if should_loop:
        log.info("Starting continuous incremental loop, interval=%ds. Press Ctrl-C to stop.", args.interval_seconds)
        conn.close()  # we'll open a fresh one per iteration
        iteration = 0
        try:
            while True:
                iteration += 1
                log.info("===== Iteration %d =====", iteration)
                c = db.get_conn(cfg["server"], cfg["database"], cfg["username"], cfg["password"])
                try:
                    _run_sync_cycle(c, client, args, db, syncers)
                finally:
                    c.close()
                log.info("Iteration %d complete. Sleeping %ds...", iteration, args.interval_seconds)
                time.sleep(args.interval_seconds)
        except KeyboardInterrupt:
            log.info("Loop stopped by user after %d iteration(s).", iteration)
            return

    errors = _run_sync_cycle(conn, client, args, db, syncers)
    conn.close()
    if errors:
        log.warning("Completed with errors in: %s", ", ".join(errors))
        sys.exit(1)
    else:
        log.info("All entities synced successfully.")


def _run_sync_cycle(conn, client, args, db, syncers):
    """Run one full incremental (or --full) sync cycle. Returns list of error entity names."""
    # Sync order respects FK constraints: reference data before tickets/problems/changes/releases.
    # Reference entities have no updated_since filter — full reload every run (small datasets, ~30s overhead).
    ENTITIES = [
        ("agents",           lambda: syncers.sync_agents(conn, client)),
        ("requesters",       lambda: syncers.sync_requesters(conn, client, active_only=not args.full)),
        ("agent_groups",     lambda: syncers.sync_agent_groups(conn, client)),
        ("requester_groups", lambda: syncers.sync_requester_groups(conn, client)),
        ("departments",      lambda: syncers.sync_departments(conn, client)),
        ("locations",        lambda: syncers.sync_locations(conn, client)),
        ("sla_policies",     lambda: syncers.sync_sla_policies(conn, client)),
        ("roles",            lambda: syncers.sync_roles(conn, client)),
    ]

    errors = []

    # ── reference entities ────────────────────────────────────────────────────
    # agent_groups / requester_groups return (groups, members) and produce two log entries.
    GROUP_MEMBER_TABLE = {
        "agent_groups":     "agent_group_members",
        "requester_groups": "requester_group_members",
    }
    for entity, fn in ENTITIES:
        try:
            result = fn()
            if entity in GROUP_MEMBER_TABLE:
                rows, member_rows = result
                db.write_sync_log(conn, entity, "success", rows)
                db.write_sync_log(conn, GROUP_MEMBER_TABLE[entity], "success", member_rows)
            else:
                db.write_sync_log(conn, entity, "success", result)
        except Exception as e:
            log.error("%s sync failed: %s", entity, e)
            db.write_sync_log(conn, entity, "error", 0, error=str(e))
            errors.append(entity)

    # ── tickets ───────────────────────────────────────────────────────────────
    try:
        last_tickets = None if (args.full or args.test) else db.get_last_synced_at(conn, "tickets")
        rows, ticket_ids, run_start = syncers.sync_tickets(
            conn, client, last_tickets,
            fetch_details=not (args.full or args.test),
            limit=300 if args.test else None,
        )
        db.write_sync_log(conn, "tickets", "success", rows, last_synced_at=run_start)
    except Exception as e:
        log.error("tickets sync failed: %s", e)
        db.write_sync_log(conn, "tickets", "error", 0, error=str(e))
        errors.append("tickets")
        ticket_ids = []
        run_start = None

    # ── ticket sub-entities ───────────────────────────────────────────────────
    if args.full:
        log.info("Skipping ticket sub-entities on full load (will sync on incremental runs).")
        ticket_ids = []

    if ticket_ids:
        for entity, fn in [
            ("conversations",       lambda: syncers.sync_conversations(conn, client, ticket_ids)),
            ("ticket_tasks",        lambda: syncers.sync_ticket_tasks(conn, client, ticket_ids)),
            ("ticket_time_entries", lambda: syncers.sync_ticket_time_entries(conn, client, ticket_ids)),
            ("ticket_activities",   lambda: syncers.sync_ticket_activities(conn, client, ticket_ids)),
        ]:
            try:
                rows = fn()
                db.write_sync_log(conn, entity, "success", rows, last_synced_at=run_start)
            except Exception as e:
                log.error("%s sync failed: %s", entity, e)
                db.write_sync_log(conn, entity, "error", 0, error=str(e))
                errors.append(entity)
    else:
        log.info("No tickets to sync sub-entities for.")

    # ── problems ──────────────────────────────────────────────────────────────
    try:
        last_problems = None if (args.full or args.test) else db.get_last_synced_at(conn, "problems")
        rows, problem_ids, problem_run_start = syncers.sync_problems(
            conn, client, last_problems,
            fetch_details=not (args.full or args.test),
            limit=300 if args.test else None,
        )
        db.write_sync_log(conn, "problems", "success", rows, last_synced_at=problem_run_start)
    except Exception as e:
        log.error("problems sync failed: %s", e)
        db.write_sync_log(conn, "problems", "error", 0, error=str(e))
        errors.append("problems")
        problem_ids = []
        problem_run_start = None

    if args.full:
        problem_ids = []

    if problem_ids:
        for entity, fn in [
            ("problem_conversations", lambda: syncers.sync_problem_conversations(conn, client, problem_ids)),
            ("problem_tasks",         lambda: syncers.sync_problem_tasks(conn, client, problem_ids)),
            ("problem_time_entries",  lambda: syncers.sync_problem_time_entries(conn, client, problem_ids)),
        ]:
            try:
                rows = fn()
                db.write_sync_log(conn, entity, "success", rows, last_synced_at=problem_run_start)
            except Exception as e:
                log.error("%s sync failed: %s", entity, e)
                db.write_sync_log(conn, entity, "error", 0, error=str(e))
                errors.append(entity)
    else:
        log.info("No problems to sync sub-entities for.")

    # ── changes ───────────────────────────────────────────────────────────────
    try:
        last_changes = None if (args.full or args.test) else db.get_last_synced_at(conn, "changes")
        rows, change_ids, change_run_start = syncers.sync_changes(
            conn, client, last_changes,
            fetch_details=not (args.full or args.test),
            limit=300 if args.test else None,
        )
        db.write_sync_log(conn, "changes", "success", rows, last_synced_at=change_run_start)
    except Exception as e:
        log.error("changes sync failed: %s", e)
        db.write_sync_log(conn, "changes", "error", 0, error=str(e))
        errors.append("changes")
        change_ids = []
        change_run_start = None

    if args.full:
        change_ids = []

    if change_ids:
        for entity, fn in [
            ("change_conversations", lambda: syncers.sync_change_conversations(conn, client, change_ids)),
            ("change_tasks",         lambda: syncers.sync_change_tasks(conn, client, change_ids)),
            ("change_time_entries",  lambda: syncers.sync_change_time_entries(conn, client, change_ids)),
        ]:
            try:
                rows = fn()
                db.write_sync_log(conn, entity, "success", rows, last_synced_at=change_run_start)
            except Exception as e:
                log.error("%s sync failed: %s", entity, e)
                db.write_sync_log(conn, entity, "error", 0, error=str(e))
                errors.append(entity)
    else:
        log.info("No changes to sync sub-entities for.")

    # ── releases ──────────────────────────────────────────────────────────────
    try:
        last_releases = None if (args.full or args.test) else db.get_last_synced_at(conn, "releases")
        rows, release_ids, release_run_start = syncers.sync_releases(
            conn, client, last_releases,
            fetch_details=not (args.full or args.test),
            limit=300 if args.test else None,
        )
        db.write_sync_log(conn, "releases", "success", rows, last_synced_at=release_run_start)
    except Exception as e:
        log.error("releases sync failed: %s", e)
        db.write_sync_log(conn, "releases", "error", 0, error=str(e))
        errors.append("releases")
        release_ids = []
        release_run_start = None

    if args.full:
        release_ids = []

    if release_ids:
        for entity, fn in [
            ("release_conversations", lambda: syncers.sync_release_conversations(conn, client, release_ids)),
            ("release_tasks",         lambda: syncers.sync_release_tasks(conn, client, release_ids)),
            ("release_time_entries",  lambda: syncers.sync_release_time_entries(conn, client, release_ids)),
        ]:
            try:
                rows = fn()
                db.write_sync_log(conn, entity, "success", rows, last_synced_at=release_run_start)
            except Exception as e:
                log.error("%s sync failed: %s", entity, e)
                db.write_sync_log(conn, entity, "error", 0, error=str(e))
                errors.append(entity)
    else:
        log.info("No releases to sync sub-entities for.")

    # ── projects (NewGen) ────────────────────────────────────────────────────
    # Small dataset (~50 at JES) — full re-sync each run, no updated_since filter on this endpoint.
    project_run_start = datetime.now(timezone.utc)
    try:
        rows, project_ids = syncers.sync_projects(conn, client)
        db.write_sync_log(conn, "projects", "success", rows, last_synced_at=project_run_start)
    except Exception as e:
        log.error("projects sync failed: %s", e)
        db.write_sync_log(conn, "projects", "error", 0, error=str(e))
        errors.append("projects")
        project_ids = []

    if project_ids:
        for entity, fn in [
            ("project_tasks",   lambda: syncers.sync_project_tasks(conn, client, project_ids)),
            ("project_members", lambda: syncers.sync_project_members(conn, client, project_ids)),
        ]:
            try:
                rows = fn()
                db.write_sync_log(conn, entity, "success", rows, last_synced_at=project_run_start)
            except Exception as e:
                log.error("%s sync failed: %s", entity, e)
                db.write_sync_log(conn, entity, "error", 0, error=str(e))
                errors.append(entity)
    else:
        log.info("No projects to sync sub-entities for.")

    # ── deleted-ticket reconciliation ─────────────────────────────────────────
    # The main /tickets endpoint never returns deleted records; without this
    # pass they'd linger as phantoms with stale state. Runs every cycle.
    try:
        marked = syncers.reconcile_deleted_tickets(conn, client)
        db.write_sync_log(conn, "deleted_tickets", "success", marked)
    except Exception as e:
        log.error("Deleted-ticket reconciliation failed: %s", e)
        db.write_sync_log(conn, "deleted_tickets", "error", 0, error=str(e))
        errors.append("deleted_tickets")

    if errors:
        log.warning("Cycle completed with errors in: %s", ", ".join(errors))
    else:
        log.info("Cycle complete: all entities synced successfully.")
    return errors


if __name__ == "__main__":
    main()
