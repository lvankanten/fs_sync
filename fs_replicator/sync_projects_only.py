"""
One-shot: sync ONLY projects + project_tasks + project_members.
Used during Layer 0 development to verify project sync without a full ticket re-sync.

Usage:  python sync_projects_only.py
"""

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

import db
import syncers
from fs_client import FreshserviceClient

conn = db.get_conn(
    os.environ["SQL_SERVER"],
    os.environ.get("FS_DATABASE", "FS"),
    os.environ["SQL_USERNAME"],
    os.environ["SQL_PASSWORD"],
)
client = FreshserviceClient(os.environ["FRESHSERVICE_APIKEY"], os.environ["FRESHSERVICE_DOMAIN"])

run_start = datetime.now(timezone.utc)
errors = []

try:
    rows, project_ids = syncers.sync_projects(conn, client)
    db.write_sync_log(conn, "projects", "success", rows, last_synced_at=run_start)
except Exception as e:
    log.error("projects sync failed: %s", e)
    db.write_sync_log(conn, "projects", "error", 0, error=str(e))
    errors.append("projects")
    project_ids = []
    raise

if project_ids:
    for entity, fn in [
        ("project_tasks",   lambda: syncers.sync_project_tasks(conn, client, project_ids)),
        ("project_members", lambda: syncers.sync_project_members(conn, client, project_ids)),
    ]:
        try:
            rows = fn()
            db.write_sync_log(conn, entity, "success", rows, last_synced_at=run_start)
        except Exception as e:
            log.error("%s sync failed: %s", entity, e)
            db.write_sync_log(conn, entity, "error", 0, error=str(e))
            errors.append(entity)

conn.close()
if errors:
    log.warning("Completed with errors in: %s", ", ".join(errors))
    sys.exit(1)
else:
    log.info("All project entities synced successfully.")
