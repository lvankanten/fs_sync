# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

`fs_replicator` replicates all Freshservice data into a SQL Server database called `FS`. It is a standalone project — it does not share code, configuration, or `.env` with any other tool in the `FreshService+` folder.

**Full initial load:** all tickets (all statuses), agents, requesters, agent groups, requester groups.
**Incremental runs:** only records changed since the last successful sync, using `updated_since` watermarks per entity.

---

## Files

```
fs_replicator/
  replicator.py    # entry point and orchestration
  fs_client.py     # Freshservice API wrapper
  db.py            # SQL Server helpers
  syncers.py       # one sync function per entity type
  schema.sql       # CREATE TABLE DDL
  requirements.txt
  .env             # credentials (not committed)
  replicator.log   # runtime log (not committed)
```

---

## Setup & Running

```bash
pip install -r requirements.txt

python replicator.py --setup        # create all 9 tables in FS database
python replicator.py --reset        # drop all tables and recreate (use when schema changes)
python replicator.py --full         # full load of all entities
python replicator.py                # incremental run (changes since last sync)
```

### `.env` (place in `fs_replicator/` directory)
```
FRESHSERVICE_APIKEY=
FRESHSERVICE_DOMAIN=
SQL_SERVER=
SQL_USERNAME=
SQL_PASSWORD=
FS_DATABASE=FS
```

---

## SQL Schema (9 tables)

All ID and foreign key columns use `BIGINT` — Freshservice IDs exceed SQL Server `INT` range.

| Table | Key | Notes |
|---|---|---|
| `sync_log` | `entity` (PK) | Watermark per entity. `last_synced_at = NULL` triggers full load. |
| `tickets` | `id BIGINT` | All ticket fields + `custom_fields_json` (full JSON blob). `description_text` is NULL on full load; fills in on incremental runs. |
| `conversations` | `id BIGINT` | FK → `tickets(id)`. DELETE+re-INSERT per ticket on each sync. |
| `agents` | `id BIGINT` | Never hard-deleted (referential integrity). |
| `requesters` | `id BIGINT` | Never hard-deleted. |
| `agent_groups` | `id BIGINT` | `unassigned_for` is `NVARCHAR(50)` — API returns strings like `'4h'`. |
| `agent_group_members` | `(group_id, agent_id)` | API returns members as list of integer IDs, not dicts. |
| `requester_groups` | `id BIGINT` | |
| `requester_group_members` | `(group_id, requester_id)` | |

Indexes on `tickets`: `updated_at`, `status`, `requester_id`, `responder_id`.

---

## Architecture

### `fs_client.py` — `FreshserviceClient`
- HTTP Basic auth: API key as username, `"X"` as password
- `_get(path, params)` — single GET with 429 retry (reads `Retry-After` header)
- `_paginate(path, key, params)` — loops pages with `per_page=100`; sleeps 0.5s between pages to avoid rate limiting
- `get_all_tickets(updated_since=None)` — uses `include=stats` (not `include=description` — Freshservice returns 400 for that)
- `get_ticket_fields()` — returns `[]` gracefully if endpoint returns 404 (not available on all plans)

### `db.py`
- `get_conn(server, database, username, password)` — tries ODBC Driver 18, 17, then "SQL Server"
- `merge_rows(conn, table, key_col, rows)` — generic T-SQL MERGE, built dynamically from dict keys
- `run_schema_file(conn, path)` — strips `--` comment lines before splitting on blank lines (required because pyodbc cannot execute multi-statement batches)
- `ensure_custom_field_column(conn, field_name, field_type)` — auto-DDL: adds `cf_` column to `tickets` if missing

### `syncers.py`
- `sync_tickets(conn, client, last_synced_at, fetch_details=True)`
  - `fetch_details=False` on `--full`: skips individual ticket GETs entirely (37k tickets × 1s = ~10 hours otherwise). `description_text` is NULL on first load.
  - `fetch_details=True` on incremental: fetches individual ticket for `description_text` + `custom_fields`, with 1s sleep between GETs
  - Custom field discovery via `get_ticket_fields()` runs at start of each ticket sync
- `sync_conversations` — skipped entirely on `--full` (same scale problem). Runs on incremental for tickets touched in that run.
- `sync_agents` / `sync_requesters` — full reload every run via MERGE (datasets are small)
- `sync_agent_groups` / `sync_requester_groups` — full reload every run; members use DELETE+INSERT per group

### `replicator.py`
Sync order respects FK constraints: agents → requesters → agent_groups → requester_groups → tickets → conversations.

Each entity: read watermark → sync → write sync_log. Failure logs an error and continues; watermark is NOT advanced on failure so the next run retries from the same point.

`--reset` drops tables in reverse FK order before recreating.

---

## Known API Limitations

| Endpoint | Issue |
|---|---|
| `GET /api/v2/ticket_fields` | Returns 404 on this Freshservice plan. Custom field columns are not auto-created; all custom fields are still stored in `custom_fields_json`. |
| `GET /api/v2/tickets?include=description` | Returns 400 — not supported. `description_text` requires individual ticket GETs. |
| Conversations | No `updated_since` filter. Re-fetched per ticket on every incremental run for tickets that changed. |
| Agents / Requesters / Groups | No `updated_since` filter. Full reload on every run. |

## Rate Limiting

Freshservice enforces API rate limits. When hit (HTTP 429), the code reads `Retry-After` and sleeps automatically. Mitigations in place:
- 0.5s sleep between pagination pages
- 1s sleep between individual ticket GETs (incremental only)
- Full load skips individual GETs entirely

---

## Incremental Behavior

| Entity | Strategy |
|---|---|
| Tickets | `updated_since` watermark — only changed tickets fetched |
| Conversations | Re-fetched for tickets that appeared in the ticket sync window |
| Agents / Requesters | Full reload every run, MERGE upsert |
| Groups + Members | Full reload every run, DELETE+INSERT per group |

`description_text` fills in gradually on incremental runs as tickets are updated in Freshservice. Tickets that are never updated after the initial full load will retain `NULL` in `description_text`.
