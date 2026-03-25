# fs_data_mgmt

## What this folder contains

General Freshservice tooling and utilities, currently housing the `fs_cli` sub-project.

---

## fs_cli — Freshservice CLI Tool

A Python CLI for querying and updating Freshservice tickets directly via the Freshservice API (not the replicated SQL database).

### Location
`fs_data_mgmt/fs_cli/`

### Files
- `fs.py` — CLI entry point (commands: `tickets`, `update`, `fields`)
- `freshservice.py` — API client (`FreshserviceClient` class)
- `requirements.txt` — `requests`, `click`, `rich`, `python-dotenv`
- `.env` — Freshservice credentials (`FRESHSERVICE_DOMAIN`, `FRESHSERVICE_APIKEY`)

### Usage
```bash
# List open tickets assigned to an agent (default status: open)
python fs.py tickets --agent "Lesley van Kanten"

# Filter by status
python fs.py tickets --agent "Lesley" --status all
python fs.py tickets --status open --count

# Filter by group
python fs.py tickets --group "IT Support"

# Update ticket fields (standard or custom)
python fs.py update 12345 priority=high
python fs.py update 12345 status=pending planned_effort=8
python fs.py update 12345 planned_start_date=2026-04-01 responder_id=8000361776

# Inspect available fields
python fs.py fields
python fs.py fields --ticket-id 12345
```

### Key design notes
- **Agent/group lookup** — `--agent` and `--group` accept partial names; resolved to IDs before querying.
- **Status/priority** — accepted as names (`open`, `high`) or numeric codes (2, 3).
- **Custom fields** — any `update` argument not in the known standard-field list is automatically sent under `custom_fields`.
- **Pagination** — all `tickets` queries auto-paginate to return the full result set.
- **Filter API quirk** — the Freshservice `/tickets/filter` endpoint requires the query string to be wrapped in double quotes in the URL (e.g. `?query="agent_id:123"`). The `requests` library handles this correctly when passing the quoted string as a `params` value; the MCP freshservice tool does not, which is why this CLI was built.

### Credentials
Stored in `fs_cli/.env`. Same API key as used in other tools under `FreshService+/`.

---

## Notes on Freshservice API behavior (discovered during development)

- The MCP `filter_tickets` tool cannot properly format the filter query (missing wrapper quotes), making it unusable for agent/status filtering.
- The `/api/v2/ticket_fields` admin endpoint returns 404 for this account; the `fields` command works around this by introspecting a real ticket.
- Rate limiting (HTTP 429) can occur after bursts of API calls — the CLI does not currently retry automatically.
- Status codes: 2=Open, 3=Pending, 4=Resolved, 5=Closed.
- Priority codes: 1=Low, 2=Medium, 3=High, 4=Urgent.
