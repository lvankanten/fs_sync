"""
Entity syncers. Each function returns the number of rows processed.
sync_tickets also returns the list of ticket IDs touched and the run-start timestamp
(used to drive conversation sync and watermark updates).
"""

import json
import logging
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
            "vip_user":                 bool(a.get("vip_user")) if a.get("vip_user") is not None else None,
            "address":                  a.get("address"),
            "location_name":            a.get("location_name"),
            "background_information":   a.get("background_information"),
            "reporting_manager_id":     a.get("reporting_manager_id"),
            "active":                   bool(a.get("active")) if a.get("active") is not None else None,
            "created_at":               _parse_dt(a.get("created_at")),
            "updated_at":               _parse_dt(a.get("updated_at")),
        })
    total = 0
    for i in range(0, len(rows), _BATCH):
        total += db.merge_rows(conn, "agents", "id", rows[i:i + _BATCH])
    log.info("Agents: %d rows upserted.", total)
    return total


# ── requesters ────────────────────────────────────────────────────────────────

def sync_requesters(conn, client: FreshserviceClient) -> int:
    log.info("Syncing requesters...")
    raw = client.get_requesters()
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
            "location_name":            r.get("location_name"),
            "background_information":   r.get("background_information"),
            "reporting_manager_id":     r.get("reporting_manager_id"),
            "department_id":            r.get("department_id"),
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

def sync_agent_groups(conn, client: FreshserviceClient) -> int:
    log.info("Syncing agent groups...")
    groups = client.get_agent_groups()
    group_rows = []
    member_count = 0

    for g in groups:
        group_rows.append({
            "id":           g.get("id"),
            "name":         g.get("name"),
            "description":  g.get("description"),
            "escalate_to":  g.get("escalate_to"),
            "unassigned_for": g.get("unassigned_for"),
            "created_at":   _parse_dt(g.get("created_at")),
            "updated_at":   _parse_dt(g.get("updated_at")),
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
        cur.execute("DELETE FROM agent_group_members WHERE group_id = ?", group_id)
        conn.commit()
        if member_ids:
            cur.executemany(
                "INSERT INTO agent_group_members (group_id, agent_id) VALUES (?, ?)",
                [(group_id, mid) for mid in member_ids],
            )
            conn.commit()
            member_count += len(member_ids)

    total = 0
    for i in range(0, len(group_rows), _BATCH):
        total += db.merge_rows(conn, "agent_groups", "id", group_rows[i:i + _BATCH])
    log.info("Agent groups: %d groups, %d members.", total, member_count)
    return total


# ── requester groups ──────────────────────────────────────────────────────────

def sync_requester_groups(conn, client: FreshserviceClient) -> int:
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
        cur.execute("DELETE FROM requester_group_members WHERE group_id = ?", group_id)
        conn.commit()
        if members:
            cur.executemany(
                "INSERT INTO requester_group_members (group_id, requester_id) VALUES (?, ?)",
                [(group_id, m.get("id")) for m in members if m.get("id")],
            )
            conn.commit()
            member_count += len(members)
        time.sleep(0.1)  # gentle rate-limit cushion

    total = 0
    for i in range(0, len(group_rows), _BATCH):
        total += db.merge_rows(conn, "requester_groups", "id", group_rows[i:i + _BATCH])
    log.info("Requester groups: %d groups, %d members.", total, member_count)
    return total


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
    """Merge list-endpoint ticket data with detail-endpoint data into a row dict."""
    # Prefer detail values where available
    t = {**ticket, **detail}

    custom_fields = t.get("custom_fields") or {}

    row = {
        "id":                   t.get("id"),
        "display_id":           t.get("display_id"),
        "subject":              t.get("subject"),
        "description_text":     t.get("description_text") or t.get("description"),
        "status":               t.get("status"),
        "priority":             t.get("priority"),
        "urgency":              t.get("urgency"),
        "impact":               t.get("impact"),
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
        "planned_start_date":   _parse_dt(t.get("planned_start_date")),
        "planned_end_date":     _parse_dt(t.get("planned_end_date")),
        "resolution_notes":     t.get("resolution_notes"),
        "custom_fields_json":   json.dumps(custom_fields) if custom_fields else None,
    }

    # Populate individual cf_ columns
    for field_name in cf_map:
        col = f"cf_{field_name}" if not field_name.startswith("cf_") else field_name
        row[col] = custom_fields.get(field_name)

    return row


def sync_tickets(
    conn,
    client: FreshserviceClient,
    last_synced_at: datetime | None,
    fetch_details: bool = True,
) -> tuple[int, list[int], datetime]:
    """
    Returns (row_count, touched_ticket_ids, run_start).
    run_start is recorded before the first API call — use as the next watermark.

    fetch_details=False skips individual ticket GETs (used for full load).
    description_text will be NULL but all other fields are populated from the list endpoint.
    Incremental runs use fetch_details=True so descriptions fill in as tickets are updated.
    """
    run_start = datetime.now(timezone.utc)

    # Discover / ensure custom field columns
    cf_map = _discover_custom_fields(conn, client)

    updated_since = last_synced_at.isoformat() if last_synced_at else None
    if updated_since:
        log.info("Syncing tickets updated since %s ...", updated_since)
    else:
        log.info("Full ticket sync (no watermark)...")

    tickets_list = client.get_all_tickets(updated_since=updated_since)
    log.info("  %d tickets to process.", len(tickets_list))

    if not fetch_details:
        log.info("  Skipping individual ticket GETs (description_text will be NULL on first load).")

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

        cur.execute("DELETE FROM conversations WHERE ticket_id = ?", tid)
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
            cur.executemany(
                """
                INSERT INTO conversations
                    (id, ticket_id, body_text, source, is_private, incoming, user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
