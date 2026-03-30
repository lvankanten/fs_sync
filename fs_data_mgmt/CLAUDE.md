# fs_data_mgmt

## What this folder contains

General Freshservice tooling and utilities, housing the `fs_cli` sub-project.
All Freshservice apps in `FreshService+/` share a common client library at `FreshService+/fs_lib/`.

---

## fs_lib — Shared Freshservice Client Library

**Location:** `FreshService+/fs_lib/freshservice.py`

The canonical Freshservice API client used by all tools under `FreshService+/`. Apps import it by adding the parent directory to `sys.path`:

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))  # or '../..'
from fs_lib.freshservice import FreshserviceClient, FreshserviceError
```

### Key capabilities
- **Filter query syntax** — human-readable, translated to API format before sending
- **Client-side pseudo-filters** — `field:empty` / `field:not_empty` for fields not filterable by the API
- **Rate-limit retry** — HTTP 429 handled automatically with `Retry-After` backoff
- **Agent/group caching** — agents and groups fetched once per client instance
- **`update_ticket`** — routes unknown fields to `custom_fields` automatically; accepts `None` for JSON null

### Filter query syntax

| Example | Meaning |
|---|---|
| `status:Open` | Single status by name |
| `status:not(Closed)` | All statuses except named ones |
| `status:in(Open,Pending)` | Named statuses only |
| `tag:'Project'` | Filter by tag |
| `id:12345` | Fetch single ticket by ID (bypasses filter endpoint) |
| `id:in(12345,12346)` | Fetch specific tickets by ID |
| `id:range(12340,12350)` | Fetch inclusive ID range |
| `planned_effort:empty` | Client-side: field is null, empty string, or 0 |
| `planned_effort:not_empty` | Client-side: field has a truthy value |
| `status:not(Closed) AND agent_id:12345 AND tag:'Project'` | Combined |
| `status:not(Closed) AND planned_effort:not_empty` | API + client-side combined |

Status names: `Open`, `Pending`, `Resolved`, `Closed`, `Development`, `Waiting on Requester`

**Client-side filters:** `:empty` and `:not_empty` work on any field (standard or custom). They are stripped from the API query and applied after fetch — no performance cost since the data is already returned by the filter endpoint.

### Client methods
- `get_tickets_by_query(query)` → `(tickets, total)`
- `get_ticket(ticket_id, include=None)` → `dict`
- `get_ticket_sample()` → `dict`
- `update_ticket(ticket_id, fields)` — standard + custom fields, accepts `None`
- `update_custom_fields(ticket_id, fields)` — convenience wrapper
- `get_conversations(ticket_id)` → `list`
- `get_ticket_activities(ticket_id)` → `list`
- `find_agent(name)` → agent dict (partial name match)
- `find_group(name)` → group dict (partial name match)
- `get_agent_name(agent_id)` → `str` (cached)

### Apps using fs_lib
- `fs_data_mgmt/fs_cli/` — imports via `../../`
- `ticket-field-updater/` — imports via `../`, thin shim in local `freshservice.py`

---

## fs_cli — Freshservice CLI Tool

**Location:** `fs_data_mgmt/fs_cli/`

A Python CLI for querying and updating Freshservice tickets directly via the API.
Imports from `fs_lib` — does not have its own `freshservice.py`.

### Files
- `fs.py` — CLI entry point (commands: `tickets`, `update`, `fields`)
- `requirements.txt` — `requests`, `click`, `rich`, `python-dotenv`
- `.env` — Freshservice credentials (`FRESHSERVICE_DOMAIN`, `FRESHSERVICE_APIKEY`)

### Usage

```bash
# List tickets (default query: status:Open)
python fs.py tickets
python fs.py tickets --agent "Lesley van Kanten"
python fs.py tickets --agent "Lesley" --query "status:not(Closed)"
python fs.py tickets --query "status:not(Closed) AND tag:'Project'"
python fs.py tickets --agent "Lesley" --query "status:not(Closed)" --count

# Client-side filtering (field:empty / field:not_empty)
python fs.py tickets --agent "Lesley" --query "status:not(Closed) AND planned_effort:empty"
python fs.py tickets --query "status:not(Closed) AND planned_effort:not_empty AND tag:'Project'"

# Group filter
python fs.py tickets --group "IT Support" --query "status:Open"

# Update a single ticket
python fs.py update 12345 priority=high
python fs.py update 12345 planned_effort=null
python fs.py update 12345 planned_start_date=2026-04-01 responder_id=8000361776

# Bulk update via filter (shows confirmation table before applying)
python fs.py update --agent "Lesley" --query "status:not(Closed)" planned_effort=null
python fs.py update --query "status:not(Closed) AND tag:'Project'" planned_effort=null
python fs.py update --agent "Lesley" --query "status:not(Closed)" --yes planned_effort=null

# Bulk update with client-side filtering
python fs.py update --agent "Lesley" --query "status:not(Closed) AND planned_effort:not_empty AND tag:'Project'" planned_effort=null

# Inspect available fields
python fs.py fields
python fs.py fields --ticket-id 12345
```

### Key design notes
- **`--query`** — uses the shared filter query syntax from `fs_lib`; defaults to `status:Open` for `tickets`
- **`--agent` / `--group`** — accept partial names, resolved to IDs before querying
- **Bulk update confirmation** — shows ticket ID, subject, and requester for all matched tickets before applying; use `--yes` to skip
- **Bulk error reporting** — prints per-ticket errors; aborts early if first 3 updates all fail
- **`null` values** — `field=null` sends JSON null to the API (clears the field)
- **Custom fields** — any field not in the standard-field list is automatically sent under `custom_fields`
- **Pagination** — all queries auto-paginate to return the full result set
- **Filter API quirk** — `/tickets/filter` requires the query string wrapped in double quotes; `include=requester` is not supported on this endpoint

### Credentials
Stored in `fs_cli/.env`. Same API key as used in other tools under `FreshService+/`.

---

## Notes on Freshservice API behavior

- The MCP `freshservice-mcp` tool has bugs: broken filter query formatting (missing wrapper quotes), no error handling on empty API responses (`get_ticket_by_id` crashes), no rate-limit retry. `fs_lib` replaces it entirely.
- The `/api/v2/ticket_fields` admin endpoint returns 404 for this account; `fields` works around this by introspecting a real ticket.
- The `/tickets/filter` endpoint does not support `include=requester` — requester names fall back to IDs in bulk mode.
- The `/tickets/filter` endpoint does not support filtering on `planned_effort` or other non-standard fields — use `field:empty` / `field:not_empty` client-side pseudo-filters instead.
- `planned_effort` expects a duration string (`"8h"`, `"1h 30m"`), not an integer. Use `null` to clear it.
- Rate limiting (HTTP 429) is handled automatically in `fs_lib` via `Retry-After`.
- Status codes: 2=Open, 3=Pending, 4=Resolved, 5=Closed, 6=Development, 7=Waiting on Requester.
- Priority codes: 1=Low, 2=Medium, 3=High, 4=Urgent.
