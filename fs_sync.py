#!/usr/bin/env python
"""
fs_sync.py — Freshservice -> SQL Server daily sync with AI-generated summaries.

What it does:
  1. Downloads fresh data from Freshservice API into CSVs in EXPORT_FOLDER
  2. Truncates and reloads: tickets, ticketUsers, ticketAgentGroups, ticketUserRequesterGroups
  3. Merges ticket descriptions into ticketDescriptionSummaries (preserves existing summaries)
  4. Generates DescriptionSummary via Claude for any tickets missing one
  5. Writes DescriptionSummary back to Freshservice as the 'description_summary' custom field

Before writing anything, the script shows a full preview and requires you to type YES to proceed.

Config: C:\\Users\\lvankanten\\.claude\\.env

Field Mapping (Freshservice -> SQL):
  tickets
    display_id / id                        -> ID
    priority (mapped)                      -> Priority
    responder_id (resolved to name)        -> Agent Name
    status (mapped)                        -> Status
    category                               -> Category
    updated_at                             -> Last Updated Date
    urgency (mapped)                       -> Urgency
    stats.first_responded_at               -> First Response Date
    item_category                          -> Item Category
    impact (mapped)                        -> Impact
    stats.agent_responded_at               -> Assigned Date
    subject                                -> Subject
    fr_escalated                           -> First Response Escalated
    sub_category                           -> Sub-Category
    due_by                                 -> Due by
    source (mapped)                        -> Source
    type                                   -> Type
    fr_due_by                              -> First Response due in
    is_escalated                           -> Resolution Escalated
    created_at                             -> Created Date
    stats.resolved_at                      -> Resolved Date
    stats.closed_at                        -> Closed Date
    tags                                   -> Tags
    department_id (resolved to name)       -> Department Name
    requester_id -> name                   -> Requester Name
    requester_id -> job_title              -> Requester Job Title
    requester_id -> location               -> Requester Location
    requester_id -> email                  -> Requester Primary Email
    requester_id -> email                  -> Requester Emails
    planned_start_date                     -> Planned Start Date
    planned_end_date                       -> Planned End Date
    resolution_notes                       -> Resolution Notes

  ticketUsers  (from requesters + agents endpoints, merged by email)
    first_name + last_name                 -> Name
    primary_email / email                  -> Emails
    job_title                              -> Job Title
    time_zone                              -> Time Zone
    vip_user                               -> VIP User
    address                                -> Address
    location_name                          -> Location
    reporting_manager_id (resolved)        -> Reporting Manager Name
    background_information                 -> Background Information
    active                                 -> Is Active

  ticketAgentGroups
    display_id / id                        -> ID
    group_id (resolved to name)            -> Agent Group Name

  ticketUserRequesterGroups
    member first_name + last_name          -> Name
    member email                           -> Emails
    requester_group name                   -> Requester Group

  ticketDescriptionSummaries
    display_id / id                        -> ID
    description_text / description         -> Description
    custom_fields.ai_current_status        -> ai_current_status
    custom_fields.ai_description_summary   -> ai_description_summary
    custom_fields.ai_next_step             -> ai_next_step
    (Claude-generated)                     -> DescriptionSummary
"""

import os
import csv
import re
import time
import logging
import base64
from pathlib import Path

import requests
import pyodbc
import anthropic

# ── Load config ───────────────────────────────────────────────────────────────

def load_env(path):
    env = {}
    p = Path(path)
    if not p.exists():
        return env
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env

_here = Path(__file__).parent
CFG = load_env(_here.parent / ".claude" / ".env")
CFG.update(load_env(_here / ".claude" / ".env"))

FS_KEY     = CFG["FRESHSERVICE_APIKEY"]
FS_DOMAIN  = CFG["FRESHSERVICE_DOMAIN"]
FS_BASE    = f"https://{FS_DOMAIN}/api/v2"
FS_HEADERS = {
    "Authorization": "Basic " + base64.b64encode(f"{FS_KEY}:X".encode()).decode(),
    "Content-Type":  "application/json",
}

SQL_SERVER = CFG["SQL_SERVER"]
SQL_DB     = CFG["SQL_DATABASE"]
SQL_USER   = CFG["SQL_USERNAME"]
SQL_PASS   = CFG["SQL_PASSWORD"]

ANTHROPIC_KEY  = CFG.get("ANTHROPIC_API_KEY", "")
EXPORT_FOLDER  = Path(CFG.get("EXPORT_FOLDER", _here))


# ── Logging ───────────────────────────────────────────────────────────────────

LOG_FILE = EXPORT_FOLDER / "fs_sync.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)


# ── CSV helpers ───────────────────────────────────────────────────────────────

def find_latest(prefix):
    """Return the most recently modified CSV matching <prefix>_*.csv in EXPORT_FOLDER."""
    matches = list(EXPORT_FOLDER.glob(f"{prefix}_*.csv"))
    if not matches:
        log.warning(f"No CSV found for prefix '{prefix}' in {EXPORT_FOLDER}")
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def read_csv_positional(path):
    """Read CSV by position — handles duplicate column names correctly."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        raw_headers = next(reader)
        raw_rows = list(reader)
    return raw_headers, raw_rows


def build_rows(raw_headers, raw_rows):
    """
    Convert positional CSV data to list-of-dicts.
    Deduplicates column names by appending a number to repeats.
    Empty strings are converted to None (SQL NULL).
    """
    columns = []
    seen = {}
    for h in raw_headers:
        if h in seen:
            seen[h] += 1
            columns.append(f"{h}{seen[h]}")
        else:
            seen[h] = 0
            columns.append(h)

    rows = []
    for raw in raw_rows:
        row = {}
        for col, val in zip(columns, raw):
            row[col] = None if val == "" else val
        rows.append(row)

    return columns, rows


# ── Database ──────────────────────────────────────────────────────────────────

def get_conn():
    cs = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={SQL_SERVER};DATABASE={SQL_DB};"
        f"UID={SQL_USER};PWD={SQL_PASS}"
    )
    return pyodbc.connect(cs)


def truncate_and_load(conn, table, columns, rows):
    quoted = ", ".join(f"[{c}]" for c in columns)
    params = ", ".join("?" for _ in columns)
    insert_sql = f"INSERT INTO [{table}] ({quoted}) VALUES ({params})"

    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE [{table}]")
    for row in rows:
        cur.execute(insert_sql, [row.get(c) for c in columns])
    conn.commit()
    log.info(f"[{table}] truncated and loaded {len(rows)} rows")


def upsert_descriptions(conn, rows):
    """
    Merge descriptions into ticketDescriptionSummaries.
    Updates Description and current_status each run.
    Updates Description, ai_current_status, ai_description_summary, and ai_next_step each run.
    """
    cur = conn.cursor()
    for row in rows:
        cur.execute("""
            MERGE [ticketDescriptionSummaries] AS t
            USING (SELECT ? AS ID, ? AS Description, ? AS ai_current_status, ? AS ai_description_summary, ? AS ai_next_step) AS s ON t.ID = s.ID
            WHEN MATCHED THEN UPDATE SET
                Description = s.Description,
                ai_current_status = s.ai_current_status,
                ai_description_summary = s.ai_description_summary,
                ai_next_step = s.ai_next_step
            WHEN NOT MATCHED THEN INSERT (ID, Description, ai_current_status, ai_description_summary, ai_next_step)
                VALUES (s.ID, s.Description, s.ai_current_status, s.ai_description_summary, s.ai_next_step);
        """, row["ID"], row["Description"], row.get("ai_current_status"), row.get("ai_description_summary"), row.get("ai_next_step"))
    conn.commit()
    log.info(f"[ticketDescriptionSummaries] merged {len(rows)} rows (AI fields preserved)")


# ── AI summary (description_summary) ──────────────────────────────────────────

SUMMARY_PROMPT = (
    "Summarize this IT support ticket description in 1-2 concise sentences. "
    "State what the user needs and any key context. "
    "Plain language only. No headers, no bullet points, no markdown formatting. "
    "Output only the summary sentences, nothing else.\n\n"
)


def generate_summary(client, description):
    if not description or not description.strip():
        return None
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": SUMMARY_PROMPT + description[:4000]}]
    )
    return msg.content[0].text.strip()


def process_summaries(conn, client):
    cur = conn.cursor()
    cur.execute("""
        SELECT ID, Description
        FROM [ticketDescriptionSummaries]
        WHERE DescriptionSummary IS NULL
          AND Description IS NOT NULL
          AND LTRIM(RTRIM(Description)) <> ''
    """)
    pending = cur.fetchall()

    if not pending:
        log.info("No tickets are missing summaries")
        return

    log.info(f"Generating summaries for {len(pending)} ticket(s)")
    for ticket_id, description in pending:
        summary = generate_summary(client, description)
        if not summary:
            log.warning(f"Empty summary returned for {ticket_id}, skipping")
            continue

        cur.execute(
            "UPDATE [ticketDescriptionSummaries] SET DescriptionSummary = ? WHERE ID = ?",
            summary, ticket_id
        )
        conn.commit()
        log.info(f"Summary saved -> {ticket_id}: {summary[:80]}")

        numeric_id = re.sub(r"\D", "", str(ticket_id))
        if numeric_id:
            resp = requests.put(
                f"{FS_BASE}/tickets/{numeric_id}",
                headers=FS_HEADERS,
                json={"custom_fields": {"description_summary": summary}}
            )
            if resp.status_code == 200:
                log.info(f"Freshservice updated -> ticket {ticket_id}")
            else:
                log.warning(f"Freshservice update failed for {ticket_id}: {resp.status_code} {resp.text[:120]}")

        time.sleep(0.3)


# ── Freshservice API fetch ─────────────────────────────────────────────────────

PRIORITY_MAP = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}
STATUS_MAP   = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed",
                6: "Development", 7: "Waiting on Requestor"}
SOURCE_MAP   = {1: "Email", 2: "Portal", 3: "Phone", 4: "Chat",
                5: "Feedback Widget", 6: "Yammer", 7: "AWS Cloudwatch",
                8: "Pagerduty", 9: "Walk-up", 10: "Slack"}
URGENCY_MAP  = {1: "Low", 2: "Medium", 3: "High"}
IMPACT_MAP   = {1: "Low", 2: "Medium", 3: "High"}

TICKET_COLS = [
    "ID", "Priority", "Agent Name", "Status", "Category", "Last Updated Date",
    "Urgency", "First Response Date", "Item Category", "Child Tickets Count",
    "Impact", "Assigned Date", "Public Notes Count", "Agent Reply Count",
    "Total Quantity", "Subject", "First Contact Resolution Violated",
    "First Response Escalated", "Customer Reply Count", "Resolution Time in Bhrs",
    "Agent Reassign Count", "Group Reassign Count", "Total Cost", "Sub-Category",
    "Private Notes Count", "Due by", "Task Count", "Source",
    "First Response Time in Chrs", "Type", "First Response due in",
    "Resolution Escalated", "Reopen Count", "Avg Response Time in Bhrs",
    "Merged Ticket", "Created Date", "Avg Response Time", "First Response Status",
    "First Response Time in Bhrs", "Associated Assets Count", "Approval Status",
    "Resolved Date", "Closed Date", "Resolution Status", "Tags",
    "Department Name", "Requester Name", "Requester Job Title", "Requester Location",
    "Requester Primary Email", "Requester Emails", "Workspace",
    "Planned Start Date", "Planned End Date", "Resolution Notes",
]


def fs_get(url, params=None):
    """Single GET with automatic rate-limit retry."""
    while True:
        resp = requests.get(url, headers=FS_HEADERS, params=params)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 60))
            log.warning(f"Rate limited — waiting {wait}s before retry")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()


def paginate(url, key, params=None):
    """Yield all records from a paginated list endpoint (up to 100/page)."""
    page = 1
    base = dict(params or {})
    while True:
        data = fs_get(url, {**base, "page": page, "per_page": 100})
        items = data.get(key, []) if isinstance(data, dict) else data
        if not items:
            break
        yield from items
        if len(items) < 100:
            break
        page += 1


def write_csv(path, headers, rows):
    """Write a list of dicts to a quoted CSV file."""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.get(h, "") or "" for h in headers])


def fetch_all_data():
    """
    Download all Freshservice data via REST API and write CSVs to EXPORT_FOLDER.
    Replaces manual CSV exports. Called automatically at the start of each run.
    """
    log.info("=== Fetching data from Freshservice API ===")

    # Move any existing timestamped CSVs to history/ before writing new ones
    history_dir = EXPORT_FOLDER / "history"
    history_dir.mkdir(exist_ok=True)
    import re as _re
    for old_csv in EXPORT_FOLDER.glob("*.csv"):
        if _re.search(r"_\d{10,}", old_csv.name):
            old_csv.rename(history_dir / old_csv.name)
            log.info(f"Archived {old_csv.name} -> history/")

    ts = int(time.time() * 1000)

    # ── Build lookup caches ────────────────────────────────────────────────────
    log.info("Loading agents, departments, groups, requesters...")

    agents = {}
    for a in paginate(f"{FS_BASE}/agents", "agents"):
        agents[a["id"]] = {
            "name":      f"{a.get('first_name', '')} {a.get('last_name', '')}".strip(),
            "email":     a.get("email") or "",
            "job_title": a.get("job_title") or "",
            "time_zone": a.get("time_zone") or "",
            "vip_user":  str(a.get("vip_user", False)).lower(),
            "address":   a.get("address") or "",
            "location":  a.get("location_name") or "",
            "bg_info":   a.get("background_information") or "",
            "active":    "Yes" if a.get("active") else "No",
            "mgr_id":    a.get("reporting_manager_id"),
        }

    # Resolve agent reporting manager names
    for a in agents.values():
        mgr_id = a.pop("mgr_id", None)
        if mgr_id:
            a["mgr_name"] = (agents.get(mgr_id) or {}).get("name", "")
        else:
            a["mgr_name"] = ""

    departments = {}
    for d in paginate(f"{FS_BASE}/departments", "departments"):
        departments[d["id"]] = d.get("name", "") or ""

    groups = {}
    for g in paginate(f"{FS_BASE}/groups", "groups"):
        groups[g["id"]] = g.get("name", "") or ""

    requesters = {}
    for r in paginate(f"{FS_BASE}/requesters", "requesters"):
        requesters[r["id"]] = {
            "name":      f"{r.get('first_name', '')} {r.get('last_name', '')}".strip(),
            "email":     r.get("primary_email") or r.get("email") or "",
            "job_title": r.get("job_title") or "",
            "time_zone": r.get("time_zone") or "",
            "vip_user":  str(r.get("vip_user", False)).lower(),
            "address":   r.get("address") or "",
            "location":  r.get("location_name") or "",
            "bg_info":   r.get("background_information") or "",
            "active":    "Yes" if r.get("active") else "No",
            "mgr_id":    r.get("reporting_manager_id"),
        }

    # Resolve reporting manager names after all requesters are loaded
    for r in requesters.values():
        mgr_id = r.pop("mgr_id", None)
        if mgr_id:
            mgr = requesters.get(mgr_id, {})
            r["mgr_name"] = mgr.get("name") or (agents.get(mgr_id) or {}).get("name", "")
        else:
            r["mgr_name"] = ""

    # ── Fetch open tickets ─────────────────────────────────────────────────────
    log.info("Fetching open tickets...")
    raw_tickets = []
    for t in paginate(f"{FS_BASE}/tickets", "tickets", {"include": "stats"}):
        if t.get("status") != 5:  # exclude Closed
            raw_tickets.append(t)

    if raw_tickets:
        log.info(f"Ticket fields available: {list(raw_tickets[0].keys())}")

    ticket_rows = []
    for t in raw_tickets:
        stats   = t.get("stats") or {}
        req_id  = t.get("requester_id")
        req     = requesters.get(req_id, {})
        if not req and req_id and req_id in agents:
            req = agents[req_id]
        tid     = f"INC-{t.get('display_id') or t['id']}"
        tags    = ",".join(t.get("tags") or [])
        ticket_rows.append({
            "ID":                              tid,
            "Priority":                        PRIORITY_MAP.get(t.get("priority"), ""),
            "Agent Name":                      (agents.get(t.get("responder_id")) or {}).get("name", ""),
            "Status":                          STATUS_MAP.get(t.get("status"), ""),
            "Category":                        t.get("category") or "",
            "Last Updated Date":               t.get("updated_at") or "",
            "Urgency":                         URGENCY_MAP.get(t.get("urgency"), ""),
            "First Response Date":             stats.get("first_responded_at") or "",
            "Item Category":                   t.get("item_category") or "",
            "Child Tickets Count":             "",
            "Impact":                          IMPACT_MAP.get(t.get("impact"), ""),
            "Assigned Date":                   stats.get("agent_responded_at") or "",
            "Public Notes Count":              "",
            "Agent Reply Count":               "",
            "Total Quantity":                  "",
            "Subject":                         t.get("subject") or "",
            "First Contact Resolution Violated": "",
            "First Response Escalated":        str(t.get("fr_escalated", False)).lower(),
            "Customer Reply Count":            "",
            "Resolution Time in Bhrs":         "",
            "Agent Reassign Count":            "",
            "Group Reassign Count":            "",
            "Total Cost":                      "",
            "Sub-Category":                    t.get("sub_category") or "",
            "Private Notes Count":             "",
            "Due by":                          t.get("due_by") or "",
            "Task Count":                      "",
            "Source":                          SOURCE_MAP.get(t.get("source"), ""),
            "First Response Time in Chrs":     "",
            "Type":                            t.get("type") or "",
            "First Response due in":           t.get("fr_due_by") or "",
            "Resolution Escalated":            str(t.get("is_escalated", False)).lower(),
            "Reopen Count":                    "",
            "Avg Response Time in Bhrs":       "",
            "Merged Ticket":                   "",
            "Created Date":                    t.get("created_at") or "",
            "Avg Response Time":               "",
            "First Response Status":           "",
            "First Response Time in Bhrs":     "",
            "Associated Assets Count":         "",
            "Approval Status":                 "",
            "Resolved Date":                   stats.get("resolved_at") or "",
            "Closed Date":                     stats.get("closed_at") or "",
            "Resolution Status":               "",
            "Tags":                            tags,
            "Department Name":                 departments.get(t.get("department_id"), "") or "",
            "Requester Name":                  req.get("name", ""),
            "Requester Job Title":             req.get("job_title", ""),
            "Requester Location":              req.get("location", ""),
            "Requester Primary Email":         req.get("email", ""),
            "Requester Emails":                req.get("email", ""),
            "Workspace":                       "",
            "Planned Start Date":              t.get("planned_start_date") or "",
            "Planned End Date":                t.get("planned_end_date") or "",
            "Resolution Notes":                t.get("resolution_notes") or "",
        })

    path = EXPORT_FOLDER / f"tickets_{ts}.csv"
    write_csv(path, TICKET_COLS, ticket_rows)
    log.info(f"tickets: {len(ticket_rows)} rows -> {path.name}")

    # ── ticket_description (full text via individual GETs) ────────────────────
    log.info(f"Fetching full descriptions for {len(raw_tickets)} ticket(s)...")
    desc_rows = []
    for t in raw_tickets:
        tid = f"INC-{t.get('display_id') or t['id']}"
        try:
            detail     = fs_get(f"{FS_BASE}/tickets/{t['id']}")
            ticket_obj = detail.get("ticket", detail)
            desc       = ticket_obj.get("description_text") or ticket_obj.get("description") or ""
        except Exception as e:
            log.warning(f"Description fetch failed for {tid}: {e}")
            desc = ""
        cf = t.get("custom_fields") or {}
        desc_rows.append({
            "ID":                    tid,
            "Description":           desc,
            "ai_current_status":     cf.get("ai_current_status", ""),
            "ai_description_summary": cf.get("ai_description_summary", ""),
            "ai_next_step":          cf.get("ai_next_step", ""),
        })
        time.sleep(0.3)

    path = EXPORT_FOLDER / f"ticket_description_{ts}.csv"
    write_csv(path, ["ID", "Description", "ai_current_status", "ai_description_summary", "ai_next_step"], desc_rows)
    log.info(f"ticket_description: {len(desc_rows)} rows -> {path.name}")

    # ── ticketusers (all requesters) ───────────────────────────────────────────
    log.info("Writing ticketusers...")
    USER_COLS = [
        "Name", "Emails", "Job Title", "Time Zone", "VIP User", "Address",
        "Location", "Reporting Manager Name", "Background Information", "Is Active",
    ]
    user_rows = [
        {
            "Name":                   r["name"],
            "Emails":                 r["email"],
            "Job Title":              r["job_title"],
            "Time Zone":              r["time_zone"],
            "VIP User":               r["vip_user"],
            "Address":                r["address"],
            "Location":               r["location"],
            "Reporting Manager Name": r["mgr_name"],
            "Background Information": r["bg_info"],
            "Is Active":              r["active"],
        }
        for r in requesters.values()
    ]

    # Add agents not already present in ticketUsers (matched by email)
    requester_emails = {r["email"].lower() for r in requesters.values() if r["email"]}
    for a in agents.values():
        if a["email"] and a["email"].lower() not in requester_emails:
            user_rows.append({
                "Name":                   a["name"],
                "Emails":                 a["email"],
                "Job Title":              a["job_title"],
                "Time Zone":              a["time_zone"],
                "VIP User":               a["vip_user"],
                "Address":                a["address"],
                "Location":               a["location"],
                "Reporting Manager Name": a["mgr_name"],
                "Background Information": a["bg_info"],
                "Is Active":              a["active"],
            })
    log.info(f"ticketusers: {len(user_rows)} total ({len(user_rows) - len(list(requesters.values()))} agents added)")
    path = EXPORT_FOLDER / f"ticketusers_{ts}.csv"
    write_csv(path, USER_COLS, user_rows)
    log.info(f"ticketusers: {len(user_rows)} rows -> {path.name}")

    # ── ticketagentgroups (current group per open ticket) ─────────────────────
    log.info("Writing ticketagentgroups...")
    ag_rows = [
        {
            "ID":              f"INC-{t.get('display_id') or t['id']}",
            "Agent Group Name": groups.get(t.get("group_id"), "") or "",
        }
        for t in raw_tickets
    ]
    path = EXPORT_FOLDER / f"ticketagentgroups_{ts}.csv"
    write_csv(path, ["ID", "Agent Group Name"], ag_rows)
    log.info(f"ticketagentgroups: {len(ag_rows)} rows -> {path.name}")

    # ── ticketuserrequestergroups (group membership) ──────────────────────────
    log.info("Fetching requester groups and members...")
    RG_COLS   = ["Name", "Emails", "Requester Group"]
    rg_rows   = []
    for rg in paginate(f"{FS_BASE}/requester_groups", "requester_groups"):
        rg_name = rg.get("name", "") or ""
        try:
            members_data = fs_get(f"{FS_BASE}/requester_groups/{rg['id']}/members")
            members = (members_data.get("members")
                       or members_data.get("requesters")
                       or [])
        except Exception as e:
            log.warning(f"Could not fetch members for requester group '{rg_name}': {e}")
            members = []
        for m in members:
            req_id = m.get("id") or m.get("requester_id")
            req    = requesters.get(req_id, {})
            rg_rows.append({
                "Name":            req.get("name") or m.get("name", "") or "",
                "Emails":          req.get("email") or m.get("email", "") or "",
                "Requester Group": rg_name,
            })
        time.sleep(0.2)

    path = EXPORT_FOLDER / f"ticketuserrequestergroups_{ts}.csv"
    write_csv(path, RG_COLS, rg_rows)
    log.info(f"ticketuserrequestergroups: {len(rg_rows)} rows -> {path.name}")

    log.info("=== API fetch complete ===")


# ── Preview ───────────────────────────────────────────────────────────────────

# Maps CSV filename prefix -> SQL table name
TABLES = {
    "tickets":                   "tickets",
    "ticketusers":               "ticketUsers",
    "ticketagentgroups":         "ticketAgentGroups",
    "ticketuserrequestergroups": "ticketUserRequesterGroups",
}


def build_preview():
    """
    Scan the export folder and show exactly what will happen before any writes occur.
    Returns a list of (action, detail) tuples.
    """
    plan = []

    for prefix, table in TABLES.items():
        path = find_latest(prefix)
        if path:
            _, raw_rows = read_csv_positional(path)
            plan.append((f"TRUNCATE + RELOAD [{table}]", f"{len(raw_rows)} rows  ←  {path.name}"))
        else:
            plan.append((f"SKIP [{table}]", "no matching CSV found"))

    desc_path = find_latest("ticket_description")
    if desc_path:
        _, raw_rows = read_csv_positional(desc_path)
        plan.append((
            "MERGE [ticketDescriptionSummaries]",
            f"{len(raw_rows)} rows  ←  {desc_path.name}  (existing summaries preserved)"
        ))
    else:
        plan.append(("SKIP [ticketDescriptionSummaries]", "no matching CSV found"))

    if ANTHROPIC_KEY:
        plan.append(("GENERATE description_summary", "Claude will summarize tickets missing DescriptionSummary, then write back to Freshservice"))
    else:
        plan.append(("SKIP description_summary", "ANTHROPIC_API_KEY not set"))

    return plan


def confirm():
    """
    Show the full plan and require the user to type YES before proceeding.
    Returns True if confirmed, False if aborted.
    """
    plan = build_preview()

    print()
    print("=" * 65)
    print("  FS SYNC — LIVE RUN PREVIEW")
    print(f"  Target database : {SQL_SERVER} / {SQL_DB}")
    print(f"  Freshservice    : {FS_DOMAIN}")
    print("=" * 65)
    print()
    for action, detail in plan:
        print(f"  {action}")
        print(f"    {detail}")
        print()
    print("  *** This will TRUNCATE and RELOAD the tables listed above. ***")
    print("  *** Existing data in those tables will be permanently replaced. ***")
    print()

    answer = input("  Type YES to proceed, anything else to abort: ").strip()
    if answer == "YES":
        print()
        return True
    print("  Aborted — no changes made.")
    return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("fs_sync starting")
    log.info("=" * 60)

    fetch_all_data()

    if not confirm():
        return

    conn = get_conn()
    log.info(f"Connected to {SQL_SERVER}/{SQL_DB}")

    # Truncate + reload main tables
    for prefix, table in TABLES.items():
        path = find_latest(prefix)
        if not path:
            continue
        log.info(f"Reading {path.name}")
        raw_headers, raw_rows = read_csv_positional(path)
        columns, rows = build_rows(raw_headers, raw_rows)
        truncate_and_load(conn, table, columns, rows)

    # Merge descriptions (preserves summaries)
    desc_path = find_latest("ticket_description")
    desc_rows_loaded = []
    if desc_path:
        log.info(f"Reading {desc_path.name}")
        raw_headers, raw_rows = read_csv_positional(desc_path)
        _, desc_rows_loaded = build_rows(raw_headers, raw_rows)
        upsert_descriptions(conn, desc_rows_loaded)

    # Generate AI summaries for description_summary
    if ANTHROPIC_KEY:
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        process_summaries(conn, client)
    else:
        log.info("Skipping AI summaries — ANTHROPIC_API_KEY not set in .env")

    conn.close()
    log.info("fs_sync complete")


if __name__ == "__main__":
    main()
