"""
Entity syncers. Each function returns the number of rows processed.
sync_tickets also returns the list of ticket IDs touched and the run-start timestamp
(used to drive conversation sync and watermark updates).
"""

import json
import logging
import math
import time
from datetime import datetime, timezone

import db
from fs_client import FreshserviceClient

log = logging.getLogger(__name__)

_BATCH = 100  # rows per merge_rows call


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_dt(val) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except ValueError:
        return None


def _join_tags(tags) -> str | None:
    if not tags:
        return None
    return ", ".join(str(t) for t in tags)


# ── agents ────────────────────────────────────────────────────────────────────

def _bool_or_none(v) -> bool | None:
    return None if v is None else bool(v)


def _json_or_none(v) -> str | None:
    """JSON-encode lists/dicts; return None for missing/empty so DB stays NULL rather than '[]'."""
    if v is None or v == [] or v == {}:
        return None
    return json.dumps(v)


def sync_agents(conn, client: FreshserviceClient) -> int:
    log.info("Syncing agents...")
    raw = client.get_agents()
    rows = []
    for a in raw:
        rows.append({
            "id":                       a.get("id"),
            "first_name":               a.get("first_name"),
            "last_name":                a.get("last_name"),
            "email":                    a.get("email"),
            "job_title":                a.get("job_title"),
            "time_zone":                a.get("time_zone"),
            "vip_user":                 _bool_or_none(a.get("vip_user")),
            "address":                  a.get("address"),
            "location_id":              a.get("location_id"),
            "location_name":            a.get("location_name"),
            "background_information":   a.get("background_information"),
            "reporting_manager_id":     a.get("reporting_manager_id"),
            "active":                   _bool_or_none(a.get("active")),
            "has_logged_in":            _bool_or_none(a.get("has_logged_in")),
            "last_active_at":           _parse_dt(a.get("last_active_at")),
            "last_login_at":            _parse_dt(a.get("last_login_at")),
            "occasional":               _bool_or_none(a.get("occasional")),
            "auto_assign_tickets":      _bool_or_none(a.get("auto_assign_tickets")),
            "auto_assign_status_changed_at": _parse_dt(a.get("auto_assign_status_changed_at")),
            "can_see_all_tickets_from_associated_departments":
                _bool_or_none(a.get("can_see_all_tickets_from_associated_departments")),
            "api_key_enabled":          _bool_or_none(a.get("api_key_enabled")),
            "work_schedule_id":         a.get("work_schedule_id"),
            "language":                 a.get("language"),
            "time_format":              a.get("time_format"),
            "roles_json":               _json_or_none(a.get("roles")),
            "member_of_json":           _json_or_none(a.get("member_of")),
            "observer_of_json":         _json_or_none(a.get("observer_of")),
            "member_of_pending_approval_json":   _json_or_none(a.get("member_of_pending_approval")),
            "observer_of_pending_approval_json": _json_or_none(a.get("observer_of_pending_approval")),
            "workspace_ids_json":       _json_or_none(a.get("workspace_ids")),
            "department_ids_json":      _json_or_none(a.get("department_ids")),
            "workload_configs_json":    _json_or_none(a.get("workload_configs")),
            "created_at":               _parse_dt(a.get("created_at")),
            "updated_at":               _parse_dt(a.get("updated_at")),
        })
    total = 0
    for i in range(0, len(rows), _BATCH):
        total += db.merge_rows(conn, "agents", "id", rows[i:i + _BATCH])
    log.info("Agents: %d rows upserted.", total)
    return total


# ── requesters ────────────────────────────────────────────────────────────────

def sync_requesters(conn, client: FreshserviceClient, active_only: bool = True) -> int:
    log.info("Syncing requesters (active_only=%s)...", active_only)
    raw = client.get_requesters(active_only=active_only)
    rows = []
    for r in raw:
        rows.append({
            "id":                       r.get("id"),
            "first_name":               r.get("first_name"),
            "last_name":                r.get("last_name"),
            "primary_email":            r.get("primary_email") or r.get("email"),
            "job_title":                r.get("job_title"),
            "time_zone":                r.get("time_zone"),
            "vip_user":                 bool(r.get("vip_user")) if r.get("vip_user") is not None else None,
            "address":                  r.get("address"),
            "location_id":              r.get("location_id"),
            "location_name":            r.get("location_name"),
            "background_information":   r.get("background_information"),
            "reporting_manager_id":     r.get("reporting_manager_id"),
            "department_ids_json":      _json_or_none(r.get("department_ids")),
            "can_see_all_tickets_from_associated_departments": bool(r["can_see_all_tickets_from_associated_departments"]) if r.get("can_see_all_tickets_from_associated_departments") is not None else None,
            "has_logged_in":            bool(r["has_logged_in"]) if r.get("has_logged_in") is not None else None,
            "secondary_emails":         _json_or_none(r.get("secondary_emails")),
            "active":                   bool(r.get("active")) if r.get("active") is not None else None,
            "created_at":               _parse_dt(r.get("created_at")),
            "updated_at":               _parse_dt(r.get("updated_at")),
        })
    total = 0
    for i in range(0, len(rows), _BATCH):
        total += db.merge_rows(conn, "requesters", "id", rows[i:i + _BATCH])
    log.info("Requesters: %d rows upserted.", total)
    return total


# ── agent groups ──────────────────────────────────────────────────────────────

def sync_agent_groups(conn, client: FreshserviceClient) -> tuple[int, int]:
    log.info("Syncing agent groups...")
    groups = client.get_agent_groups()
    group_rows = []
    member_count = 0

    for g in groups:
        group_rows.append({
            "id":                 g.get("id"),
            "name":               g.get("name"),
            "description":        g.get("description"),
            "escalate_to":        g.get("escalate_to"),
            "unassigned_for":     g.get("unassigned_for"),
            "auto_ticket_assign": bool(g["auto_ticket_assign"]) if g.get("auto_ticket_assign") is not None else None,
            "restricted":         bool(g["restricted"]) if g.get("restricted") is not None else None,
            "workspace_id":       g.get("workspace_id"),
            "business_hours_id":  g.get("business_hours_id"),
            "approval_required":  bool(g["approval_required"]) if g.get("approval_required") is not None else None,
            "ocs_schedule_id":    g.get("ocs_schedule_id"),
            "created_at":         _parse_dt(g.get("created_at")),
            "updated_at":         _parse_dt(g.get("updated_at")),
        })

        # Refresh members for this group
        # members can be a list of ints (IDs) or list of dicts depending on API version
        group_id = g.get("id")
        raw_members = g.get("members") or []
        member_ids = [
            m if isinstance(m, int) else m.get("id")
            for m in raw_members
            if m is not None and (isinstance(m, int) or (isinstance(m, dict) and m.get("id")))
        ]
        cur = conn.cursor()
        cur.execute("DELETE FROM agent_group_members WHERE group_id = %s", group_id)
        conn.commit()
        if member_ids:
            cur.executemany(
                "INSERT INTO agent_group_members (group_id, agent_id) VALUES (%s, %s)",
                [(group_id, mid) for mid in member_ids],
            )
            conn.commit()
            member_count += len(member_ids)

    total = 0
    for i in range(0, len(group_rows), _BATCH):
        total += db.merge_rows(conn, "agent_groups", "id", group_rows[i:i + _BATCH])
    log.info("Agent groups: %d groups, %d members.", total, member_count)
    return total, member_count


# ── requester groups ──────────────────────────────────────────────────────────

def sync_requester_groups(conn, client: FreshserviceClient) -> tuple[int, int]:
    log.info("Syncing requester groups...")
    groups = client.get_requester_groups()
    group_rows = []
    member_count = 0

    for g in groups:
        group_rows.append({
            "id":           g.get("id"),
            "name":         g.get("name"),
            "description":  g.get("description"),
            "created_at":   _parse_dt(g.get("created_at")),
            "updated_at":   _parse_dt(g.get("updated_at")),
        })

        group_id = g.get("id")
        try:
            members = client.get_requester_group_members(group_id)
        except Exception as e:
            log.warning("Could not fetch members for requester group %d: %s", group_id, e)
            members = []

        cur = conn.cursor()
        cur.execute("DELETE FROM requester_group_members WHERE group_id = %s", group_id)
        conn.commit()
        if members:
            cur.executemany(
                "INSERT INTO requester_group_members (group_id, requester_id) VALUES (%s, %s)",
                [(group_id, m.get("id")) for m in members if m.get("id")],
            )
            conn.commit()
            member_count += len(members)
        time.sleep(0.1)  # gentle rate-limit cushion

    total = 0
    for i in range(0, len(group_rows), _BATCH):
        total += db.merge_rows(conn, "requester_groups", "id", group_rows[i:i + _BATCH])
    log.info("Requester groups: %d groups, %d members.", total, member_count)
    return total, member_count


# ── tickets ───────────────────────────────────────────────────────────────────

def _discover_custom_fields(conn, client: FreshserviceClient) -> dict:
    """
    Call /api/v2/ticket_fields, ensure each custom field has a cf_ column in tickets,
    and return a dict mapping field_name → field_type for use during row mapping.
    """
    fields = client.get_ticket_fields()
    cf_map = {}
    for f in fields:
        name = f.get("name", "")
        ftype = f.get("field_type", "custom_text")
        # Freshservice names custom fields as 'cf_xxx' in the custom_fields dict
        if name.startswith("cf_") or ftype.startswith("custom_"):
            cf_map[name] = ftype
            db.ensure_custom_field_column(conn, name, ftype)
    return cf_map


def _map_ticket(ticket: dict, detail: dict, cf_map: dict) -> dict:
    """Merge list-endpoint ticket data with detail-endpoint data into a row dict.

    Fields only returned by the individual ticket GET (not the list endpoint)
    are excluded when detail is empty, so merge_rows won't overwrite existing
    DB values with NULL.
    """
    # Prefer detail values where available
    t = {**ticket, **detail}
    has_detail = bool(detail)

    custom_fields = t.get("custom_fields") or {}

    row = {
        "id":                   t.get("id"),
        "display_id":           t.get("display_id"),
        "subject":              t.get("subject"),
        "description_text":     t.get("description_text") or t.get("description"),
        "status":               t.get("status"),
        "priority":             t.get("priority"),
        "source":               t.get("source"),
        "ticket_type":          t.get("type"),
        "category":             t.get("category"),
        "sub_category":         t.get("sub_category"),
        "item_category":        t.get("item_category"),
        "tags":                 _join_tags(t.get("tags")),
        "department_id":        t.get("department_id"),
        "responder_id":         t.get("responder_id"),
        "group_id":             t.get("group_id"),
        "requester_id":         t.get("requester_id"),
        "workspace_id":         t.get("workspace_id"),
        "fr_escalated":         bool(t["fr_escalated"]) if t.get("fr_escalated") is not None else None,
        "is_escalated":         bool(t["is_escalated"]) if t.get("is_escalated") is not None else None,
        "created_at":           _parse_dt(t.get("created_at")),
        "updated_at":           _parse_dt(t.get("updated_at")),
        "due_by":               _parse_dt(t.get("due_by")),
        "fr_due_by":            _parse_dt(t.get("fr_due_by")),
        "resolved_at":          _parse_dt(t.get("stats", {}).get("resolved_at") or t.get("resolved_at")),
        "closed_at":            _parse_dt(t.get("stats", {}).get("closed_at") or t.get("closed_at")),
        "custom_fields_json":   json.dumps(custom_fields) if custom_fields else None,
    }

    # Fields only returned by the individual ticket GET (not the list endpoint).
    # Exclude when no detail was fetched to avoid overwriting existing DB values with NULL.
    # planned_* are owned by workload_sync.py and stored in the ticket_workload table.
    if has_detail:
        row["urgency"]            = t.get("urgency")
        row["impact"]             = t.get("impact")
        row["resolution_notes"]   = t.get("resolution_notes")

    # Populate individual cf_ columns
    for field_name in cf_map:
        col = f"cf_{field_name}" if not field_name.startswith("cf_") else field_name
        val = custom_fields.get(field_name)
        # Multi-select fields return as lists — comma-join for storage
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val) if val else None
        row[col] = val

    return row


def sync_tickets(
    conn,
    client: FreshserviceClient,
    last_synced_at: datetime | None,
    fetch_details: bool = True,
    limit: int = None,
) -> tuple[int, list[int], datetime]:
    """
    Returns (row_count, touched_ticket_ids, run_start).
    run_start is recorded before the first API call — use as the next watermark.

    fetch_details=False skips individual ticket GETs (used for full load).
    description_text will be NULL but all other fields are populated from the list endpoint.
    Incremental runs use fetch_details=True so descriptions fill in as tickets are updated.

    limit truncates the ticket list (used by --test mode).
    """
    run_start = datetime.now(timezone.utc)

    # Discover / ensure custom field columns
    cf_map = _discover_custom_fields(conn, client)

    updated_since = last_synced_at.isoformat() if last_synced_at else None
    if updated_since:
        log.info("Syncing tickets updated since %s ...", updated_since)
    else:
        log.info("Full ticket sync (no watermark)...")

    max_pages = math.ceil(limit / 100) if limit else None
    tickets_list = client.get_all_tickets(
        updated_since=updated_since,
        max_pages=max_pages,
        order_by="updated_at" if limit else None,
        order_type="desc" if limit else None,
    )
    if limit:
        tickets_list = tickets_list[:limit]
        log.info("  %d tickets to process (test run, %d most recently updated).", len(tickets_list), limit)
    else:
        log.info("  %d tickets to process.", len(tickets_list))

    if not fetch_details:
        log.info("  Skipping individual ticket GETs (description_text will be NULL on first load).")
    elif len(tickets_list) > 500:
        est_hours = len(tickets_list) / 3600
        log.warning(
            "  WARNING: %d tickets will each require an individual API GET (1s sleep between each). "
            "Estimated time: %.1f hours. Consider using --full instead.",
            len(tickets_list), est_hours,
        )

    rows = []
    ticket_ids = []

    for i, t in enumerate(tickets_list):
        tid = t.get("id")
        ticket_ids.append(tid)

        if fetch_details:
            try:
                detail = client.get_ticket(tid)
                time.sleep(1)
            except Exception as e:
                log.warning("  Could not fetch detail for ticket %d: %s", tid, e)
                detail = {}
        else:
            detail = {}

        rows.append(_map_ticket(t, detail, cf_map))


    total = 0
    for i in range(0, len(rows), _BATCH):
        total += db.merge_rows(conn, "tickets", "id", rows[i:i + _BATCH])
        log.info("  Written %d / %d tickets to SQL...", min(total, len(rows)), len(rows))

    log.info("Tickets: %d rows upserted.", total)
    return total, ticket_ids, run_start


# ── conversations ─────────────────────────────────────────────────────────────

def sync_conversations(conn, client: FreshserviceClient, ticket_ids: list[int]) -> int:
    """
    Re-fetch and replace conversations for all given ticket IDs.
    Uses DELETE + INSERT per ticket (no updated_since available on this endpoint).
    """
    if not ticket_ids:
        return 0

    log.info("Syncing conversations for %d tickets...", len(ticket_ids))
    cur = conn.cursor()
    total = 0

    for i, tid in enumerate(ticket_ids):
        try:
            convs = client.get_conversations(tid)
        except Exception as e:
            log.warning("  Could not fetch conversations for ticket %d: %s", tid, e)
            continue

        cur.execute("DELETE FROM conversations WHERE ticket_id = %s", tid)
        conn.commit()

        rows = []
        for c in convs:
            rows.append({
                "id":           c.get("id"),
                "ticket_id":    tid,
                "body_text":    c.get("body_text") or c.get("body"),
                "source":       c.get("source"),
                "is_private":   bool(c["private"]) if c.get("private") is not None else None,
                "incoming":     bool(c["incoming"]) if c.get("incoming") is not None else None,
                "user_id":      c.get("user_id"),
                "created_at":   _parse_dt(c.get("created_at")),
                "updated_at":   _parse_dt(c.get("updated_at")),
            })

        if rows:
            # Also delete by id in case any conversation appears under multiple tickets
            # (merged tickets / email threads) to avoid PK violations
            placeholders = ", ".join(["%s"] * len(rows))
            cur.execute(
                f"DELETE FROM conversations WHERE id IN ({placeholders})",
                [r["id"] for r in rows],
            )
            conn.commit()
            cur.executemany(
                """
                INSERT INTO conversations
                    (id, ticket_id, body_text, source, is_private, incoming, user_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        r["id"], r["ticket_id"], r["body_text"], r["source"],
                        r["is_private"], r["incoming"], r["user_id"],
                        r["created_at"], r["updated_at"],
                    )
                    for r in rows
                ],
            )
            conn.commit()
            total += len(rows)

        if (i + 1) % 50 == 0:
            log.info("  Conversations: %d / %d tickets done...", i + 1, len(ticket_ids))

        time.sleep(0.05)

    log.info("Conversations: %d rows inserted.", total)
    return total


# ── ticket tasks ──────────────────────────────────────────────────────────────

def sync_ticket_tasks(conn, client: FreshserviceClient, ticket_ids: list[int]) -> int:
    """Re-fetch and replace tasks for all given ticket IDs."""
    if not ticket_ids:
        return 0

    log.info("Syncing tasks for %d tickets...", len(ticket_ids))
    cur = conn.cursor()
    total = 0

    for tid in ticket_ids:
        try:
            tasks = client.get_ticket_tasks(tid)
        except Exception as e:
            log.warning("  Could not fetch tasks for ticket %d: %s", tid, e)
            continue

        cur.execute("DELETE FROM ticket_tasks WHERE ticket_id = %s", tid)
        conn.commit()

        if tasks:
            ids = [t.get("id") for t in tasks if t.get("id") is not None]
            if ids:
                placeholders = ", ".join(["%s"] * len(ids))
                cur.execute(
                    f"DELETE FROM ticket_tasks WHERE id IN ({placeholders})",
                    ids,
                )
                conn.commit()
            cur.executemany(
                """
                INSERT INTO ticket_tasks
                    (id, ticket_id, agent_id, status, due_date, notify_before,
                     title, description, planned_start_date, planned_end_date, planned_effort,
                     created_at, updated_at, closed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        t.get("id"), tid, t.get("agent_id"), t.get("status"),
                        _parse_dt(t.get("due_date")), t.get("notify_before"),
                        t.get("title"), t.get("description"),
                        _parse_dt(t.get("planned_start_date")),
                        _parse_dt(t.get("planned_end_date")),
                        t.get("planned_effort"),
                        _parse_dt(t.get("created_at")), _parse_dt(t.get("updated_at")),
                        _parse_dt(t.get("closed_at")),
                    )
                    for t in tasks
                ],
            )
            conn.commit()
            total += len(tasks)

        time.sleep(0.05)

    log.info("Ticket tasks: %d rows inserted.", total)
    return total


# ── ticket time entries ───────────────────────────────────────────────────────

def sync_ticket_time_entries(conn, client: FreshserviceClient, ticket_ids: list[int]) -> int:
    """Re-fetch and replace time entries for all given ticket IDs."""
    if not ticket_ids:
        return 0

    log.info("Syncing time entries for %d tickets...", len(ticket_ids))
    cur = conn.cursor()
    total = 0

    for tid in ticket_ids:
        try:
            entries = client.get_ticket_time_entries(tid)
        except Exception as e:
            log.warning("  Could not fetch time entries for ticket %d: %s", tid, e)
            continue

        cur.execute("DELETE FROM ticket_time_entries WHERE ticket_id = %s", tid)
        conn.commit()

        if entries:
            ids = [e.get("id") for e in entries if e.get("id") is not None]
            if ids:
                placeholders = ", ".join(["%s"] * len(ids))
                cur.execute(
                    f"DELETE FROM ticket_time_entries WHERE id IN ({placeholders})",
                    ids,
                )
                conn.commit()
            cur.executemany(
                """
                INSERT INTO ticket_time_entries
                    (id, ticket_id, agent_id, time_spent, billable, note,
                     start_time, timer_running, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        e.get("id"), tid, e.get("agent_id"), e.get("time_spent"),
                        bool(e["billable"]) if e.get("billable") is not None else None,
                        e.get("note"),
                        _parse_dt(e.get("start_time")),
                        bool(e["timer_running"]) if e.get("timer_running") is not None else None,
                        _parse_dt(e.get("created_at")), _parse_dt(e.get("updated_at")),
                    )
                    for e in entries
                ],
            )
            conn.commit()
            total += len(entries)

        time.sleep(0.05)

    log.info("Ticket time entries: %d rows inserted.", total)
    return total


# ── ticket activities ─────────────────────────────────────────────────────────

def sync_ticket_activities(conn, client: FreshserviceClient, ticket_ids: list[int]) -> int:
    """Re-fetch and replace activity audit entries for all given ticket IDs.

    The API returns no id on individual activities. We DELETE WHERE ticket_id=?
    then INSERT all current activities; a surrogate IDENTITY PK is assigned by SQL.
    """
    if not ticket_ids:
        return 0

    log.info("Syncing activities for %d tickets...", len(ticket_ids))
    cur = conn.cursor()
    total = 0

    for tid in ticket_ids:
        try:
            acts = client.get_ticket_activities(tid)
        except Exception as e:
            if "404" in str(e):
                log.warning("  ticket_activities endpoint not available on this plan — skipping.")
                return 0
            log.warning("  Could not fetch activities for ticket %d: %s", tid, e)
            continue

        cur.execute("DELETE FROM ticket_activities WHERE ticket_id = %s", tid)
        conn.commit()

        if acts:
            cur.executemany(
                """
                INSERT INTO ticket_activities
                    (ticket_id, actor_id, actor_name, actor_is_agent,
                     content, sub_contents, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        tid,
                        (a.get("actor") or {}).get("id"),
                        (a.get("actor") or {}).get("name"),
                        bool((a.get("actor") or {}).get("is_agent")) if (a.get("actor") or {}).get("is_agent") is not None else None,
                        a.get("content"),
                        json.dumps(a["sub_contents"]) if a.get("sub_contents") else None,
                        _parse_dt(a.get("created_at")),
                    )
                    for a in acts
                ],
            )
            conn.commit()
            total += len(acts)

        time.sleep(0.05)

    log.info("Ticket activities: %d rows inserted.", total)
    return total


# ── deleted-ticket reconciliation ─────────────────────────────────────────────

def reconcile_deleted_tickets(conn, client: FreshserviceClient) -> int:
    """Mark replica rows for tickets that have been deleted in live FS.

    The main /tickets list endpoint never returns deleted records, so without
    this pass they'd linger forever as phantoms — frozen at pre-deletion state.
    Soft-delete (set deleted=1) rather than hard DELETE preserves audit history.
    """
    log.info("Reconciling deleted tickets...")
    try:
        deleted = client.get_deleted_tickets()
    except Exception as e:
        log.warning("  Could not fetch deleted tickets: %s", e)
        raise

    deleted_ids = [t.get("id") for t in deleted if t.get("id") is not None]
    if not deleted_ids:
        log.info("  No deleted tickets returned by API.")
        return 0

    log.info("  %d deleted tickets returned by API; updating replica...", len(deleted_ids))
    cur = conn.cursor()
    marked = 0
    # Chunk the IN-list to keep the parameter count well under SQL Server's limit.
    CHUNK = 500
    for i in range(0, len(deleted_ids), CHUNK):
        chunk = deleted_ids[i:i + CHUNK]
        placeholders = ", ".join(["%s"] * len(chunk))
        cur.execute(
            f"UPDATE tickets SET deleted = 1 WHERE id IN ({placeholders}) AND deleted = 0",
            chunk,
        )
        marked += cur.rowcount
        conn.commit()
    cur.close()

    log.info("Deleted-ticket reconciliation: %d row(s) newly marked deleted.", marked)
    return marked


# ── shared helpers for problem / change / release sub-entities ────────────────

def _sync_conversations_for(
    conn, entity_ids: list[int], get_fn, table: str, parent_col: str
) -> int:
    """DELETE+INSERT conversations for any entity type."""
    if not entity_ids:
        return 0
    log.info("Syncing %s for %d records...", table, len(entity_ids))
    cur = conn.cursor()
    total = 0
    for i, eid in enumerate(entity_ids):
        try:
            convs = get_fn(eid)
        except Exception as e:
            if "404" in str(e):
                log.warning("  %s endpoint not available on this plan — skipping.", table)
                return 0
            log.warning("  Could not fetch %s for %s=%d: %s", table, parent_col, eid, e)
            continue
        cur.execute(f"DELETE FROM {table} WHERE {parent_col} = %s", eid)
        conn.commit()
        rows = [
            (
                c.get("id"), eid,
                c.get("body_text") or c.get("body"),
                c.get("source"),
                bool(c["private"]) if c.get("private") is not None else None,
                bool(c["incoming"]) if c.get("incoming") is not None else None,
                c.get("user_id"),
                _parse_dt(c.get("created_at")),
                _parse_dt(c.get("updated_at")),
            )
            for c in convs
        ]
        if rows:
            cur.executemany(
                f"INSERT INTO {table} (id, {parent_col}, body_text, source, is_private, incoming, user_id, created_at, updated_at) "
                f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )
            conn.commit()
            total += len(rows)
        if (i + 1) % 50 == 0:
            log.info("  %s: %d / %d records done...", table, i + 1, len(entity_ids))
        time.sleep(0.05)
    log.info("%s: %d rows inserted.", table, total)
    return total


def _sync_tasks_for(
    conn, entity_ids: list[int], get_fn, table: str, parent_col: str
) -> int:
    """DELETE+INSERT tasks for any entity type."""
    if not entity_ids:
        return 0
    log.info("Syncing %s for %d records...", table, len(entity_ids))
    cur = conn.cursor()
    total = 0
    for eid in entity_ids:
        try:
            tasks = get_fn(eid)
        except Exception as e:
            if "404" in str(e):
                log.warning("  %s endpoint not available on this plan — skipping.", table)
                return 0
            log.warning("  Could not fetch %s for %s=%d: %s", table, parent_col, eid, e)
            continue
        cur.execute(f"DELETE FROM {table} WHERE {parent_col} = %s", eid)
        conn.commit()
        rows = [
            (
                t.get("id"), eid, t.get("agent_id"), t.get("status"),
                _parse_dt(t.get("due_date")), t.get("notify_before"),
                t.get("title"), t.get("description"),
                _parse_dt(t.get("planned_start_date")),
                _parse_dt(t.get("planned_end_date")),
                t.get("planned_effort"),
                _parse_dt(t.get("created_at")), _parse_dt(t.get("updated_at")),
                _parse_dt(t.get("closed_at")),
            )
            for t in tasks
        ]
        if rows:
            ids = [r[0] for r in rows if r[0] is not None]
            if ids:
                placeholders = ", ".join(["%s"] * len(ids))
                cur.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
                conn.commit()
            cur.executemany(
                f"INSERT INTO {table} (id, {parent_col}, agent_id, status, due_date, notify_before, "
                f"title, description, planned_start_date, planned_end_date, planned_effort, "
                f"created_at, updated_at, closed_at) "
                f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )
            conn.commit()
            total += len(rows)
        time.sleep(0.05)
    log.info("%s: %d rows inserted.", table, total)
    return total


def _sync_time_entries_for(
    conn, entity_ids: list[int], get_fn, table: str, parent_col: str
) -> int:
    """DELETE+INSERT time entries for any entity type."""
    if not entity_ids:
        return 0
    log.info("Syncing %s for %d records...", table, len(entity_ids))
    cur = conn.cursor()
    total = 0
    for eid in entity_ids:
        try:
            entries = get_fn(eid)
        except Exception as e:
            if "404" in str(e):
                log.warning("  %s endpoint not available on this plan — skipping.", table)
                return 0
            log.warning("  Could not fetch %s for %s=%d: %s", table, parent_col, eid, e)
            continue
        cur.execute(f"DELETE FROM {table} WHERE {parent_col} = %s", eid)
        conn.commit()
        rows = [
            (
                e.get("id"), eid, e.get("agent_id"), e.get("time_spent"),
                bool(e["billable"]) if e.get("billable") is not None else None,
                e.get("note"),
                _parse_dt(e.get("start_time")),
                bool(e["timer_running"]) if e.get("timer_running") is not None else None,
                _parse_dt(e.get("created_at")), _parse_dt(e.get("updated_at")),
            )
            for e in entries
        ]
        if rows:
            ids = [r[0] for r in rows if r[0] is not None]
            if ids:
                placeholders = ", ".join(["%s"] * len(ids))
                cur.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
                conn.commit()
            cur.executemany(
                f"INSERT INTO {table} (id, {parent_col}, agent_id, time_spent, billable, note, "
                f"start_time, timer_running, created_at, updated_at) "
                f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )
            conn.commit()
            total += len(rows)
        time.sleep(0.05)
    log.info("%s: %d rows inserted.", table, total)
    return total


# ── departments ───────────────────────────────────────────────────────────────

def sync_departments(conn, client: FreshserviceClient) -> int:
    log.info("Syncing departments...")
    raw = client.get_departments()
    rows = []
    for d in raw:
        domains = d.get("domains")
        rows.append({
            "id":           d.get("id"),
            "name":         d.get("name"),
            "description":  d.get("description"),
            "head_user_id": d.get("head_user_id"),
            "prime_user_id": d.get("prime_user_id"),
            "domains":      ", ".join(domains) if isinstance(domains, list) else domains,
            "created_at":   _parse_dt(d.get("created_at")),
            "updated_at":   _parse_dt(d.get("updated_at")),
        })
    total = 0
    for i in range(0, len(rows), _BATCH):
        total += db.merge_rows(conn, "departments", "id", rows[i:i + _BATCH])
    log.info("Departments: %d rows upserted.", total)
    return total


# ── locations ─────────────────────────────────────────────────────────────────

def sync_locations(conn, client: FreshserviceClient) -> int:
    log.info("Syncing locations...")
    raw = client.get_locations()
    rows = []
    for loc in raw:
        addr = loc.get("address") or {}
        rows.append({
            "id":                   loc.get("id"),
            "name":                 loc.get("name"),
            "parent_location_id":   loc.get("parent_location_id"),
            "contact_name":         loc.get("contact_name"),
            "email":                loc.get("email"),
            "phone":                loc.get("phone"),
            "address_line1":        addr.get("line1") or addr.get("address_line1"),
            "city":                 addr.get("city"),
            "state":                addr.get("state"),
            "zip_code":             addr.get("zip_code") or addr.get("zipcode"),
            "country":              addr.get("country"),
            "created_at":           _parse_dt(loc.get("created_at")),
            "updated_at":           _parse_dt(loc.get("updated_at")),
        })
    total = 0
    for i in range(0, len(rows), _BATCH):
        total += db.merge_rows(conn, "locations", "id", rows[i:i + _BATCH])
    log.info("Locations: %d rows upserted.", total)
    return total


# ── SLA policies ────────────────────────────────────────────────────────────────

def sync_sla_policies(conn, client: FreshserviceClient) -> int:
    log.info("Syncing SLA policies...")
    raw = client.get_sla_policies()
    rows = []
    for s in raw:
        rows.append({
            "id":                  s.get("id"),
            "name":                s.get("name"),
            "description":         s.get("description"),
            "is_default":          _bool_or_none(s.get("is_default")),
            "active":              _bool_or_none(s.get("active")),
            "deleted":             _bool_or_none(s.get("deleted")),
            "position":            s.get("position"),
            "parent_entity":       s.get("parent_entity"),
            "workspace_id":        s.get("workspace_id"),
            "applicable_to_json":  _json_or_none(s.get("applicable_to")),
            "sla_targets_json":    _json_or_none(s.get("sla_targets")),
            "escalation_json":     _json_or_none(s.get("escalation")),
            "created_at":          _parse_dt(s.get("created_at")),
            "updated_at":          _parse_dt(s.get("updated_at")),
        })
    total = 0
    for i in range(0, len(rows), _BATCH):
        total += db.merge_rows(conn, "sla_policies", "id", rows[i:i + _BATCH])
    log.info("SLA policies: %d rows upserted.", total)
    return total


# ── roles ─────────────────────────────────────────────────────────────────────

def sync_roles(conn, client: FreshserviceClient) -> int:
    log.info("Syncing roles...")
    raw = client.get_roles()
    rows = []
    for r in raw:
        rows.append({
            "id":           r.get("id"),
            "name":         r.get("name"),
            "description":  r.get("description"),
            "is_default":   _bool_or_none(r.get("default")),
            "role_type":    r.get("role_type"),
            "scopes_json":  _json_or_none(r.get("scopes")),
            "created_at":   _parse_dt(r.get("created_at")),
            "updated_at":   _parse_dt(r.get("updated_at")),
        })
    total = 0
    for i in range(0, len(rows), _BATCH):
        total += db.merge_rows(conn, "roles", "id", rows[i:i + _BATCH])
    log.info("Roles: %d rows upserted.", total)
    return total


# ── problems ──────────────────────────────────────────────────────────────────

def _discover_entity_custom_fields(conn, client_get_fn, table: str) -> dict:
    """Discover custom fields for problems/changes/releases and ensure columns exist."""
    fields = client_get_fn()
    cf_map = {}
    for f in fields:
        name = f.get("name", "")
        ftype = f.get("field_type", "custom_text")
        if name.startswith("cf_") or ftype.startswith("custom_"):
            cf_map[name] = ftype
            db.ensure_custom_field_column(conn, name, ftype, table=table)
    return cf_map


def _map_entity(raw: dict, detail: dict, cf_map: dict, extra_cols: dict) -> dict:
    """Build a row dict for problems/changes/releases from list + detail data.

    Detail-only fields are excluded when detail is empty to avoid overwriting
    existing DB values with NULL.
    """
    e = {**raw, **detail}
    has_detail = bool(detail)
    custom_fields = e.get("custom_fields") or {}

    row = {
        "id":                   e.get("id"),
        "display_id":           e.get("display_id"),
        "subject":              e.get("subject"),
        "status":               e.get("status"),
        "priority":             e.get("priority"),
        "impact":               e.get("impact"),
        "category":             e.get("category"),
        "sub_category":         e.get("sub_category"),
        "item_category":        e.get("item_category"),
        "department_id":        e.get("department_id"),
        "agent_id":             e.get("agent_id") or e.get("responder_id"),
        "group_id":             e.get("group_id"),
        "workspace_id":         e.get("workspace_id"),
        "created_at":           _parse_dt(e.get("created_at")),
        "updated_at":           _parse_dt(e.get("updated_at")),
        "custom_fields_json":   json.dumps(custom_fields) if custom_fields else None,
    }

    if has_detail:
        row["description_text"]   = e.get("description_text") or e.get("description")
        row["planned_start_date"] = _parse_dt(e.get("planned_start_date"))
        row["planned_end_date"]   = _parse_dt(e.get("planned_end_date"))
        row["planned_effort"]     = e.get("planned_effort")

    row.update(extra_cols(e))

    for field_name in cf_map:
        col = f"cf_{field_name}" if not field_name.startswith("cf_") else field_name
        val = custom_fields.get(field_name)
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val) if val else None
        row[col] = val

    return row


def sync_problems(
    conn,
    client: FreshserviceClient,
    last_synced_at: datetime | None,
    fetch_details: bool = True,
    limit: int = None,
) -> tuple[int, list[int], datetime]:
    run_start = datetime.now(timezone.utc)
    cf_map = _discover_entity_custom_fields(conn, client.get_problem_fields, "problems")

    updated_since = last_synced_at.isoformat() if last_synced_at else None
    if updated_since:
        log.info("Syncing problems updated since %s ...", updated_since)
    else:
        log.info("Full problem sync (no watermark)...")

    max_pages = math.ceil(limit / 100) if limit else None
    problems_list = client.get_all_problems(updated_since=updated_since, max_pages=max_pages)
    if limit:
        problems_list = problems_list[:limit]
    log.info("  %d problems to process.", len(problems_list))

    if not fetch_details:
        log.info("  Skipping individual problem GETs (description_text will be NULL).")

    def extra_cols(e):
        return {
            "requester_id": e.get("requester_id"),
            "due_by":       _parse_dt(e.get("due_by")),
            "closed_at":    _parse_dt(e.get("closed_at")),
        }

    rows = []
    problem_ids = []
    for p in problems_list:
        pid = p.get("id")
        problem_ids.append(pid)
        if fetch_details:
            try:
                detail = client.get_problem(pid)
                time.sleep(0.5)
            except Exception as e:
                log.warning("  Could not fetch detail for problem %d: %s", pid, e)
                detail = {}
        else:
            detail = {}
        rows.append(_map_entity(p, detail, cf_map, extra_cols))

    total = 0
    for i in range(0, len(rows), _BATCH):
        total += db.merge_rows(conn, "problems", "id", rows[i:i + _BATCH])

    log.info("Problems: %d rows upserted.", total)
    return total, problem_ids, run_start


def sync_problem_conversations(conn, client: FreshserviceClient, problem_ids: list[int]) -> int:
    return _sync_conversations_for(conn, problem_ids, client.get_problem_conversations, "problem_conversations", "problem_id")


def sync_problem_tasks(conn, client: FreshserviceClient, problem_ids: list[int]) -> int:
    return _sync_tasks_for(conn, problem_ids, client.get_problem_tasks, "problem_tasks", "problem_id")


def sync_problem_time_entries(conn, client: FreshserviceClient, problem_ids: list[int]) -> int:
    return _sync_time_entries_for(conn, problem_ids, client.get_problem_time_entries, "problem_time_entries", "problem_id")


# ── changes ───────────────────────────────────────────────────────────────────

def sync_changes(
    conn,
    client: FreshserviceClient,
    last_synced_at: datetime | None,
    fetch_details: bool = True,
    limit: int = None,
) -> tuple[int, list[int], datetime]:
    run_start = datetime.now(timezone.utc)
    cf_map = _discover_entity_custom_fields(conn, client.get_change_fields, "changes")

    updated_since = last_synced_at.isoformat() if last_synced_at else None
    if updated_since:
        log.info("Syncing changes updated since %s ...", updated_since)
    else:
        log.info("Full change sync (no watermark)...")

    max_pages = math.ceil(limit / 100) if limit else None
    changes_list = client.get_all_changes(updated_since=updated_since, max_pages=max_pages)
    if limit:
        changes_list = changes_list[:limit]
    log.info("  %d changes to process.", len(changes_list))

    if not fetch_details:
        log.info("  Skipping individual change GETs (description_text will be NULL).")

    def extra_cols(e):
        return {
            "requester_id":     e.get("requester_id"),
            "risk":             e.get("risk"),
            "change_type":      e.get("change_type"),
            "approval_status":  e.get("approval_status"),
        }

    rows = []
    change_ids = []
    for c in changes_list:
        cid = c.get("id")
        change_ids.append(cid)
        if fetch_details:
            try:
                detail = client.get_change(cid)
                time.sleep(0.5)
            except Exception as e:
                log.warning("  Could not fetch detail for change %d: %s", cid, e)
                detail = {}
        else:
            detail = {}
        rows.append(_map_entity(c, detail, cf_map, extra_cols))

    total = 0
    for i in range(0, len(rows), _BATCH):
        total += db.merge_rows(conn, "changes", "id", rows[i:i + _BATCH])

    log.info("Changes: %d rows upserted.", total)
    return total, change_ids, run_start


def sync_change_conversations(conn, client: FreshserviceClient, change_ids: list[int]) -> int:
    return _sync_conversations_for(conn, change_ids, client.get_change_conversations, "change_conversations", "change_id")


def sync_change_tasks(conn, client: FreshserviceClient, change_ids: list[int]) -> int:
    return _sync_tasks_for(conn, change_ids, client.get_change_tasks, "change_tasks", "change_id")


def sync_change_time_entries(conn, client: FreshserviceClient, change_ids: list[int]) -> int:
    return _sync_time_entries_for(conn, change_ids, client.get_change_time_entries, "change_time_entries", "change_id")


# ── releases ──────────────────────────────────────────────────────────────────

def sync_releases(
    conn,
    client: FreshserviceClient,
    last_synced_at: datetime | None,
    fetch_details: bool = True,
    limit: int = None,
) -> tuple[int, list[int], datetime]:
    run_start = datetime.now(timezone.utc)
    cf_map = _discover_entity_custom_fields(conn, client.get_release_fields, "releases")

    updated_since = last_synced_at.isoformat() if last_synced_at else None
    if updated_since:
        log.info("Syncing releases updated since %s ...", updated_since)
    else:
        log.info("Full release sync (no watermark)...")

    max_pages = math.ceil(limit / 100) if limit else None
    releases_list = client.get_all_releases(updated_since=updated_since, max_pages=max_pages)
    if limit:
        releases_list = releases_list[:limit]
    log.info("  %d releases to process.", len(releases_list))

    if not fetch_details:
        log.info("  Skipping individual release GETs (description_text will be NULL).")

    def extra_cols(e):
        return {
            "release_type": e.get("release_type"),
        }

    rows = []
    release_ids = []
    for r in releases_list:
        rid = r.get("id")
        release_ids.append(rid)
        if fetch_details:
            try:
                detail = client.get_release(rid)
                time.sleep(0.5)
            except Exception as e:
                log.warning("  Could not fetch detail for release %d: %s", rid, e)
                detail = {}
        else:
            detail = {}
        rows.append(_map_entity(r, detail, cf_map, extra_cols))

    total = 0
    for i in range(0, len(rows), _BATCH):
        total += db.merge_rows(conn, "releases", "id", rows[i:i + _BATCH])

    log.info("Releases: %d rows upserted.", total)
    return total, release_ids, run_start


def sync_release_conversations(conn, client: FreshserviceClient, release_ids: list[int]) -> int:
    return _sync_conversations_for(conn, release_ids, client.get_release_conversations, "release_conversations", "release_id")


def sync_release_tasks(conn, client: FreshserviceClient, release_ids: list[int]) -> int:
    return _sync_tasks_for(conn, release_ids, client.get_release_tasks, "release_tasks", "release_id")


def sync_release_time_entries(conn, client: FreshserviceClient, release_ids: list[int]) -> int:
    return _sync_time_entries_for(conn, release_ids, client.get_release_time_entries, "release_time_entries", "release_id")


# ── projects (NewGen, pm/ namespace) ──────────────────────────────────────────

def _parse_date_only(val) -> datetime | None:
    """Parse YYYY-MM-DD date string into a date-only datetime, or pass through datetime."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val.date() if hasattr(val, "date") else val
    try:
        # FS returns "2026-03-24" for start_date/end_date (date-only, no time)
        return datetime.fromisoformat(str(val)).date()
    except (ValueError, AttributeError):
        return None


def sync_projects(conn, client: FreshserviceClient) -> tuple[int, list[int]]:
    """
    Full re-sync of NewGen projects. Small dataset (~tens at JES) so no incremental needed.
    Returns (row_count, project_ids) — IDs feed sub-entity syncs.

    The default GET /api/v2/pm/projects returns all non-archived projects (Completed included).
    Archived projects are not exposed via this endpoint at JES (the archived=true param doesn't
    filter — empirically returns same set). The `archived` BIT column on rows reflects the value
    FS returned per-project, so SQL queries can still filter.
    """
    log.info("Syncing NewGen projects...")
    raw = client.get_projects()
    log.info("  %d projects total", len(raw))

    rows = []
    project_ids = []
    for p in raw:
        pid = p.get("id")
        project_ids.append(pid)
        rows.append({
            "id":                  pid,
            "name":                p.get("name"),
            "key":                 p.get("key"),
            "description":         p.get("description"),
            "status_id":           p.get("status_id"),
            "priority_id":         p.get("priority_id"),
            "sprint_duration":     p.get("sprint_duration"),
            "project_type":        p.get("project_type"),
            "start_date":          _parse_date_only(p.get("start_date")),
            "end_date":            _parse_date_only(p.get("end_date")),
            "archived":            _bool_or_none(p.get("archived")),
            "visibility":          p.get("visibility"),
            "manager_id":          p.get("manager_id"),
            "custom_fields_json":  _json_or_none(p.get("custom_fields")),
            "created_at":          _parse_dt(p.get("created_at")),
            "updated_at":          _parse_dt(p.get("updated_at")),
        })

    total = 0
    for i in range(0, len(rows), _BATCH):
        total += db.merge_rows(conn, "projects", "id", rows[i:i + _BATCH])
    log.info("Projects: %d rows upserted.", total)
    return total, project_ids


def sync_project_tasks(conn, client: FreshserviceClient, project_ids: list[int]) -> int:
    """Re-fetch and replace project tasks for all given project IDs."""
    if not project_ids:
        return 0

    log.info("Syncing project tasks for %d projects...", len(project_ids))
    cur = conn.cursor()
    total = 0

    for pid in project_ids:
        try:
            tasks = client.get_project_tasks(pid)
        except Exception as e:
            log.warning("  Could not fetch tasks for project %d: %s", pid, e)
            continue

        cur.execute("DELETE FROM project_tasks WHERE project_id = %s", pid)
        conn.commit()

        if not tasks:
            continue

        rows = []
        for t in tasks:
            rows.append({
                "id":                  t.get("id"),
                "project_id":          pid,
                "title":               t.get("title"),
                "description":         t.get("description"),
                "status_id":           t.get("status_id"),
                "priority_id":         t.get("priority_id"),
                "type_id":             t.get("type_id"),
                "display_key":         t.get("display_key"),
                "reporter_id":         t.get("reporter_id"),
                "assignee_id":         t.get("assignee_id"),
                "planned_start_date":  _parse_dt(t.get("planned_start_date")),
                "planned_end_date":    _parse_dt(t.get("planned_end_date")),
                "planned_effort":      str(t.get("planned_effort")) if t.get("planned_effort") is not None else None,
                "planned_duration":    str(t.get("planned_duration")) if t.get("planned_duration") is not None else None,
                "version_id":          t.get("version_id"),
                "parent_id":           t.get("parent_id"),
                "story_points":        t.get("story_points"),
                "sprint_id":           t.get("sprint_id"),
                "custom_fields_json":  _json_or_none(t.get("custom_fields")),
                "created_at":          _parse_dt(t.get("created_at")),
                "updated_at":          _parse_dt(t.get("updated_at")),
            })

        for i in range(0, len(rows), _BATCH):
            total += db.merge_rows(conn, "project_tasks", "id", rows[i:i + _BATCH])
        time.sleep(0.1)  # gentle rate-limit cushion

    log.info("Project tasks: %d rows upserted.", total)
    return total


def sync_project_members(conn, client: FreshserviceClient, project_ids: list[int]) -> int:
    """Re-fetch and replace project memberships for all given project IDs."""
    if not project_ids:
        return 0

    log.info("Syncing project memberships for %d projects...", len(project_ids))
    cur = conn.cursor()
    total = 0

    for pid in project_ids:
        try:
            members = client.get_project_memberships(pid)
        except Exception as e:
            log.warning("  Could not fetch memberships for project %d: %s", pid, e)
            continue

        cur.execute("DELETE FROM project_members WHERE project_id = %s", pid)
        conn.commit()

        if not members:
            continue

        rows = []
        for m in members:
            rows.append({
                "id":               m.get("id"),
                "project_id":       pid,
                "user_id":          m.get("user_id"),
                "access_type":      m.get("access_type"),
                "manage_settings":  _bool_or_none(m.get("manage_settings")),
                "project_manager":  _bool_or_none(m.get("project_manager")),
                "created_at":       _parse_dt(m.get("created_at")),
                "updated_at":       _parse_dt(m.get("updated_at")),
            })

        for i in range(0, len(rows), _BATCH):
            total += db.merge_rows(conn, "project_members", "id", rows[i:i + _BATCH])
        time.sleep(0.1)

    log.info("Project members: %d rows upserted.", total)
    return total
