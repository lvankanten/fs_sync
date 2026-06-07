# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

`fs_replicator` replicates all Freshservice data into a SQL Server database called `FS`. It is a standalone project — it does not share code, configuration, or `.env` with any other tool in the `FreshService+` folder.

**Full initial load:** all entities (all statuses/states).
**Incremental runs:** only records changed since the last successful sync, using `updated_since` watermarks per entity where supported. Also refreshes detail-only fields for all open tickets.

---

## Files

```
fs_replicator/
  replicator.py         # entry point — tickets, conversations, tasks, time entries,
                        #   agents, requesters, groups, departments, locations,
                        #   problems, changes, releases
  workload_sync.py      # separate process — captures planned_effort/start/end_date
                        #   into ticket_workload table on its own schedule
  projects_replicator.py  # projects, project tasks, milestones, members, time entries
  assets_replicator.py    # assets, asset relationships, components
  catalog_replicator.py   # service catalog categories and items
  kb_replicator.py        # knowledge base categories, folders, published articles
  config_replicator.py    # SLAs, canned responses, announcements
  fs_client.py          # Freshservice API wrapper (shared)
  db.py                 # SQL Server helpers (shared)
  syncers.py            # one sync function per entity type
  schema.sql            # CREATE TABLE DDL for replicator.py tables
  requirements.txt
  .env                  # credentials (not committed)
  replicator.log        # runtime log (not committed)
```

---

## Setup & Running

```bash
pip install -r requirements.txt

python replicator.py --setup                   # create tables in FS database
python replicator.py --reset                   # drop all tables and recreate (use when schema changes)
python replicator.py --truncate                # clear all data, keep schema (restore simulation / DB migration)
python replicator.py --full                    # full load of all entities (no sub-entities)
python replicator.py                           # run incremental continuously (loops, default 5min sleep). Ctrl-C to stop.
python replicator.py --once                    # single incremental run (changes since last sync), then exit
python replicator.py --interval-seconds 60     # loop with custom interval (e.g., 60s)
python replicator.py --test                    # smoke test: 300 newest tickets/problems/changes/releases
python replicator.py --backfill-sub-entities   # fetch conversations/tasks/time entries for ALL records in DB

python workload_sync.py                        # capture planned_effort/start_date/end_date for open tickets
python workload_sync.py --older-than-hours 4   # only refresh rows not checked in N hours
```

### Common workflows

**Initial load (first time or new database instance):**
```bash
python replicator.py --setup                   # create schema
python replicator.py --full                    # load all main entities
python replicator.py --backfill-sub-entities   # load all conversations/tasks/time entries (run overnight)
python replicator.py --once                    # incremental — picks up urgency/impact/etc. via per-ticket GET for open tickets
```

**Restore simulation / migrate to new database instance:**
```bash
python replicator.py --truncate                # clear all data, keep schema
python replicator.py --full
python replicator.py --backfill-sub-entities
python replicator.py --once                    # incremental — picks up urgency/impact/etc. via per-ticket GET
```

**Schema change (new columns or tables):**
```bash
python replicator.py --reset                   # drop and recreate all tables
python replicator.py --full
python replicator.py --backfill-sub-entities
python replicator.py --once                    # incremental — picks up urgency/impact/etc. via per-ticket GET
```

**Ongoing scheduled runs:**
```bash
python replicator.py --once                    # single incremental — for cron / Task Scheduler
python replicator.py                           # OR run continuously as a long-lived process (loops, Ctrl-C to stop)
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

## SQL Schema

All ID and foreign key columns use `BIGINT` — Freshservice IDs exceed SQL Server `INT` range.

### Current tables (replicator.py)

| Table | Key | Notes |
|---|---|---|
| `sync_log` | `entity` (PK) | Watermark per entity. `last_synced_at = NULL` triggers full load. `cursor_id BIGINT` for mid-entity backfill resume. `backfill_completed_at DATETIMEOFFSET` marks an entity as fully backfilled so a resumed backfill skips it. |
| `tickets` | `id BIGINT` | All ticket fields + `custom_fields_json` (full JSON blob). `planned_effort NVARCHAR(50)` — Workload Management field. Multi-select custom fields stored as comma-joined strings. |
| `conversations` | `id BIGINT` | FK → `tickets(id)`. DELETE+re-INSERT per ticket on each sync. |
| `ticket_tasks` | `id BIGINT` | FK → `tickets(id)`. Tasks assigned to agents on tickets. Includes `planned_start_date`, `planned_end_date`, `planned_effort`. |
| `ticket_time_entries` | `id BIGINT` | FK → `tickets(id)`. Time logged by agents on tickets. |
| `ticket_activities` | `id BIGINT IDENTITY` | FK → `tickets(id)`. Audit log of ticket actions (status changes, assignments, field updates, etc.). API returns no id on individual activities, so a surrogate IDENTITY PK is used; DELETE+INSERT per ticket on each sync. `sub_contents` stored as JSON when present. |
| `agents` | `id BIGINT` | Never hard-deleted (referential integrity). Profile + permission/role fields: `has_logged_in`, `last_active_at`, `last_login_at`, `occasional`, `auto_assign_tickets`, `auto_assign_status_changed_at`, `can_see_all_tickets_from_associated_departments`, `api_key_enabled`, `work_schedule_id`, `language`, `time_format`. List-shaped fields stored as JSON: `roles_json`, `member_of_json`, `observer_of_json`, `member_of_pending_approval_json`, `observer_of_pending_approval_json`, `workspace_ids_json`, `department_ids_json`, `workload_configs_json`. Empty arrays → NULL (not `'[]'`). |
| `requesters` | `id BIGINT` | Never hard-deleted. |
| `agent_groups` | `id BIGINT` | `unassigned_for` is `NVARCHAR(50)` — API returns strings like `'4h'`. |
| `agent_group_members` | `(group_id, agent_id)` | API returns members as list of integer IDs, not dicts. |
| `requester_groups` | `id BIGINT` | |
| `requester_group_members` | `(group_id, requester_id)` | |
| `departments` | `id BIGINT` | Lookup table. Full reload on `--full`. |
| `locations` | `id BIGINT` | Lookup table. Full reload on `--full`. |
| `problems` | `id BIGINT` | Incremental via `updated_since`. Custom fields promoted to `cf_` columns + `custom_fields_json`. |
| `problem_conversations` | `id BIGINT` | FK → `problems(id)`. DELETE+re-INSERT per problem. |
| `problem_tasks` | `id BIGINT` | FK → `problems(id)`. Includes `planned_start_date`, `planned_end_date`, `planned_effort`. |
| `problem_time_entries` | `id BIGINT` | FK → `problems(id)`. |
| `changes` | `id BIGINT` | Incremental via `updated_since`. Custom fields promoted to `cf_` columns + `custom_fields_json`. |
| `change_conversations` | `id BIGINT` | FK → `changes(id)`. DELETE+re-INSERT per change. |
| `change_tasks` | `id BIGINT` | FK → `changes(id)`. Includes `planned_start_date`, `planned_end_date`, `planned_effort`. |
| `change_time_entries` | `id BIGINT` | FK → `changes(id)`. |
| `releases` | `id BIGINT` | Incremental via `updated_since`. Custom fields promoted to `cf_` columns + `custom_fields_json`. |
| `release_conversations` | `id BIGINT` | FK → `releases(id)`. DELETE+re-INSERT per release. |
| `release_tasks` | `id BIGINT` | FK → `releases(id)`. Includes `planned_start_date`, `planned_end_date`, `planned_effort`. |
| `release_time_entries` | `id BIGINT` | FK → `releases(id)`. |
| `ticket_workload` | `ticket_id BIGINT` | FK → `tickets(id)`. Populated by `workload_sync.py`, NOT `replicator.py`. Tracks `planned_effort`, `planned_start_date`, `planned_end_date`, `last_checked_at`. Separate cadence because these fields don't bump ticket `updated_at` and so are invisible to the main replicator's incremental sync. |
| `sla_policies` | `id BIGINT` | Full reload every run (reference entity). Header columns + nested `applicable_to`/`sla_target`/`escalation` stored as JSON blobs. In the main replicator (NOT the planned `config_replicator.py`) so policy tweaks stay synced. |
| `roles` | `id BIGINT` | Agent roles lookup. Full reload every run (reference entity). Resolves the `role_id` values in `agents.roles_json` (which only carry `role_id` + `assignment_scope`) to names. API's `default` flag stored as `is_default` (`default` is a SQL reserved word). |
| `projects` | `id BIGINT` | NewGen projects (`pm/` namespace). Full reload every run. In the main replicator, not a standalone script — projects see growing use and need regular re-sync. |
| `project_tasks` | `id BIGINT` | FK → `projects(id)`. DELETE+re-INSERT per project each run. |
| `project_members` | `id BIGINT` | FK → `projects(id)`. DELETE+re-INSERT per project each run. |

Indexes on `tickets`: `updated_at`, `status`, `requester_id`, `responder_id`.

### Planned tables (not yet implemented)

> Note: entities that get adjusted over time and need regular re-syncing live in the main looping `replicator.py` (full-reload reference entities) rather than standalone scripts, so they can't be forgotten. `projects` and `sla_policies` were originally planned as standalone scripts but moved into the main replicator for this reason. Standalone Phase 2 scripts below are for rarely-changing / one-off config.

**assets_replicator.py:**
| Table | Key | Notes |
|---|---|---|
| `assets` | `id BIGINT` | Incremental sync via `updated_since` if supported. |
| `asset_relationships` | `id BIGINT` | Relationships between assets in CMDB. |
| `asset_components` | `id BIGINT` | FK → `assets(id)`. |

**catalog_replicator.py:**
| Table | Key | Notes |
|---|---|---|
| `catalog_categories` | `id BIGINT` | Service catalog categories. Full reload. |
| `catalog_items` | `id BIGINT` | FK → `catalog_categories(id)`. Service items. |

**kb_replicator.py:**
| Table | Key | Notes |
|---|---|---|
| `kb_categories` | `id BIGINT` | Solution categories. Full reload. |
| `kb_folders` | `id BIGINT` | FK → `kb_categories(id)`. Solution folders. |
| `kb_articles` | `id BIGINT` | FK → `kb_folders(id)`. Published articles only. |

**config_replicator.py:**
| Table | Key | Notes |
|---|---|---|
| `canned_responses` | `id BIGINT` | Canned response templates. Full reload. |
| `announcements` | `id BIGINT` | Announcements. Full reload. |

(SLA policies were originally planned here but now live in the main `replicator.py` — see current tables above.)

---

## Architecture

### `fs_client.py` — `FreshserviceClient`
- HTTP Basic auth: API key as username, `"X"` as password
- `_get(path, params)` — single GET with 429 retry (reads `Retry-After` header)
- `_paginate(path, key, params, max_pages=None)` — loops pages with `per_page=100`; sleeps 0.5s between pages; `max_pages=1` used by `--test` mode
- `get_all_tickets(updated_since=None, max_pages=None)` — uses `include=stats` (not `include=description` — Freshservice returns 400 for that)
- `get_ticket_fields()` — calls `ticket_form_fields` endpoint (not `ticket_fields` — returns 404 on this plan). Returns `[]` gracefully on error.
- Problem/change/release methods follow same pattern: `get_all_*`, `get_*`, `get_*_fields`, `get_*_conversations/tasks/time_entries`

### `db.py`
- Uses **pymssql** (not pyodbc). pyodbc + ODBC Driver 17 triggers TDS error 8058 (TVP misinterpretation) with >~30 parameters per statement. pymssql uses FreeTDS and does not have this issue.
- `get_conn(server, database, username, password)` — connects via pymssql
- `merge_rows(conn, table, key_col, rows)` — UPDATE existing row, INSERT if rowcount=0. Uses `%s` placeholders (pymssql DB-API 2.0 style, not `?`).
- `run_schema_file(conn, path)` — strips `--` comment lines before splitting on blank lines
- `ensure_custom_field_column(conn, field_name, field_type)` — auto-DDL: adds `cf_` column to tickets if missing
- `write_sync_log(conn, entity, status, rows, ...)` — MERGE upsert into sync_log. Uses `COALESCE(s.cursor_id, t.cursor_id)` to preserve cursor on non-backfill writes.
- `get_backfill_cursor(conn, entity)` — reads cursor_id for backfill resume
- `clear_backfill_cursor(conn, entity)` — explicitly sets cursor_id to NULL
- `mark_backfill_complete(conn, entity)` — stamps `backfill_completed_at` and clears cursor when an entity fully finishes (inserts a sync_log row if none exists, e.g. a zero-ID entity)
- `get_backfill_completed(conn, entity)` / `clear_backfill_completed(conn, entity)` — read / reset the completion marker; used by the backfill campaign logic to skip finished entities on resume

### `syncers.py`
- All direct cursor SQL uses `%s` placeholders (pymssql), not `?` (pyodbc)
- Multi-select custom fields (Python lists from API) are comma-joined to strings before storage
- `sync_tickets(conn, client, last_synced_at, fetch_details=True, limit=None)`
  - `fetch_details=False` on `--full` / `--test`: skips individual ticket GETs. Detail-only fields (`urgency`, `impact`, `planned_effort`, `planned_start_date`, `planned_end_date`, `resolution_notes`) are excluded from the row to avoid overwriting existing DB values with NULL.
  - `fetch_details=True` on incremental: fetches individual ticket for all fields, with 1s sleep between GETs
  - `limit=300` + `max_pages=1` on `--test`: fetches only first page, writes real watermark
  - Warns if >500 tickets require individual GETs (estimates hours)
  - Custom field discovery via `get_ticket_fields()` runs at start of each ticket sync
- `sync_conversations` — skipped on `--full`. Runs on incremental for tickets touched in that run.
- `sync_agents` — full reload every run (no `updated_since` filter; small dataset).
- `sync_requesters` — every run with `active_only=True` by default (passes `?active=true` to API, ~37% of total). `--full` passes `active_only=False` to pull active + inactive. Inactive requesters already in the DB are never deleted (FK integrity with tickets).
- `sync_agent_groups` / `sync_requester_groups` — full reload every run. Return `(groups, members)` tuple so the replicator writes separate `sync_log` entries for the parent table and `*_group_members` table.
- `sync_departments` / `sync_locations` — full reload every run.
- `sync_problems` / `sync_changes` / `sync_releases` — incremental via `updated_since`. Same detail-only field pattern as tickets.
- Generic helpers: `_sync_conversations_for`, `_sync_tasks_for`, `_sync_time_entries_for` — detect 404 on first call and skip the entire batch with a single warning.

### `replicator.py`
Sync order respects FK constraints:
- `--full` / `--test`: agents → requesters → groups → departments → locations → tickets → problems → changes → releases (+ sub-entities)
- Incremental: agents → requesters → groups → departments → locations → tickets → conversations/tasks/time entries → problems → changes → releases (+ sub-entities). Reference entities are full-reloaded every run (small datasets, ~30s overhead). Workload fields (planned_*) handled separately by `workload_sync.py`.

Each entity: read watermark → sync → write sync_log. Failure logs an error and continues; watermark is NOT advanced on failure so the next run retries from the same point.

`--reset` drops tables in reverse FK order before recreating.
`--truncate` uses `DELETE FROM` (not `TRUNCATE TABLE` — FK constraints prevent TRUNCATE even when child tables are empty).
`--backfill-sub-entities` processes in chunks of 500 with fresh DB connections per chunk to avoid DBPROCESS dead (error 20047) on long runs. Supports cursor-based resume — can be cancelled and restarted without losing progress.

---

## Known API Limitations

| Endpoint / Field | Issue |
|---|---|
| `GET /api/v2/ticket_fields` | Returns 404 on this plan. Use `ticket_form_fields` instead. |
| `GET /api/v2/tickets?include=description` | Returns 400 — not supported. |
| `GET /api/v2/tickets` (list endpoint) | Does NOT return `urgency`, `impact`, `planned_effort`, `planned_start_date`, `planned_end_date`, `resolution_notes`. These require individual ticket GETs. |
| Workload Management fields (`planned_effort`, `planned_start_date`, `planned_end_date`) | Updating these fields does **not** bump `updated_at` on the ticket. This means the `updated_since` filter will not pick up changes to these fields unless another field on the ticket also changes. **Captured by `workload_sync.py` (separate script)** writing to the `ticket_workload` table — runs on its own schedule, not part of `replicator.py`. |
| Problem conversations (`/problems/{id}/conversations`) | Returns 404 on this plan. Detected on first call and skipped. |
| Conversations / Tasks / Time Entries / Activities | No `updated_since` filter. Re-fetched per parent record on every incremental run. Activities additionally have no `id` field in the API response, so a surrogate IDENTITY PK is used. |
| Agents / Requesters / Groups / Departments / Locations | No `updated_since` filter. Full reload on `--full` only. |
| `planned_effort` | Part of Workload Management module. Returned as top-level ticket field (not a custom field). Data type is `NVARCHAR(50)` (duration string like `'4h'`). |
| Multi-select custom fields | API returns as Python lists (e.g. `[]`). Must be comma-joined before SQL insert — pymssql cannot bind a list as a parameter. |
| Duplicate conversation IDs | Same conversation can appear under multiple ticket IDs (merged tickets). Fixed by DELETEing by conversation ID before INSERT. |

---

## Technical Decisions & Lessons Learned

### pyodbc → pymssql migration
pyodbc with ODBC Driver 17 throws TDS error 8058 ("Table-valued parameter N... has no table type defined") when a parameterised statement has more than ~30 parameters. This affects tickets (31+ columns including custom fields). Switching to pymssql (FreeTDS) resolved the issue completely. All SQL placeholders use `%s` not `?`.

### MERGE → UPDATE+INSERT
T-SQL MERGE also triggers TDS error 8058 with many parameters regardless of syntax (`VALUES` or `SELECT ? AS col`). Replaced with UPDATE first, INSERT if rowcount=0. The sync_log table still uses MERGE (only ~7 parameters — well under the limit) via pymssql which handles it fine.

### BIGINT for all IDs
Freshservice IDs exceed SQL Server INT max (~2.1B). All PK and FK columns use BIGINT.

### Schema DDL execution
`run_schema_file` strips `--` comment lines before splitting on blank lines. pyodbc/pymssql cannot execute multi-statement batches; each statement must be executed individually.

### Full load strategy
37k+ tickets × 1s per individual GET = ~10 hours. `--full` uses `fetch_details=False` to skip individual GETs. Detail-only fields (`urgency`, `impact`, `planned_*`, `resolution_notes`) are excluded from the row so existing DB values are preserved. urgency/impact/resolution_notes fill in via normal incremental GETs (they bump `updated_at`). planned_* fields are handled by `workload_sync.py` (separate process).

### Detail-only fields (list vs individual GET)
The ticket list endpoint (`GET /tickets`) does not return: `urgency`, `impact`, `planned_effort`, `planned_start_date`, `planned_end_date`, `resolution_notes`. The individual ticket GET (`GET /tickets/{id}`) does return them. When `fetch_details=False`, these fields are excluded from `_map_ticket` output so `merge_rows` does not overwrite existing DB values with NULL. The `refresh_detail_fields` function on incremental runs re-fetches all open tickets individually and updates only where values differ (~4 min for ~250 open tickets).

### Workload Management fields don't update `updated_at`
Changing `planned_effort`, `planned_start_date`, or `planned_end_date` (via API or UI) does NOT change the ticket's `updated_at` timestamp. Standard fields (priority, status, category, custom fields, etc.) DO update `updated_at`. This was verified by controlled testing. Handled by `workload_sync.py` running on its own schedule (not part of `replicator.py`).

### `--test` mode
Fetches 300 newest tickets/problems/changes/releases (1 API page each), writes a real watermark. Then run incremental to validate the full pipeline end-to-end without processing all records.

### Backfill with cursor-based resume
`--backfill-sub-entities` processes ticket/problem/change/release IDs in chunks of 500, reconnecting to SQL Server between chunks to avoid DBPROCESS dead (error 20047) after ~2 hours. After each chunk, writes the last processed parent ID to `sync_log.cursor_id`. On restart, reads cursor and skips already-processed IDs *within* an entity. When an entity fully completes, `mark_backfill_complete` stamps `sync_log.backfill_completed_at` and clears the cursor. The `write_sync_log` MERGE uses `COALESCE(s.cursor_id, t.cursor_id)` so non-backfill writes (e.g., normal incremental sync) do not wipe an in-progress cursor, and it leaves `backfill_completed_at` untouched so the marker survives incremental runs.

**Campaign logic (skip completed entities on resume):** `cursor_id = NULL` alone can't distinguish "never started" from "finished," so an interrupted resume used to reprocess every already-completed entity from scratch (one API call per parent ID, even for zero-row entities like `ticket_tasks` across ~40k tickets). `backfill_completed_at` fixes this. At startup the backfill checks all 12 sub-entities: if **every** one is already complete it treats the run as a deliberate fresh full backfill — clears all markers and runs everything (matches the old always-rerun behavior); if **only some** are complete it's a resume — those entities are skipped and only the unfinished ones run. So a dropped VPN mid-backfill now costs only the unfinished entities on restart, not the whole set. Markers are per-entity in `sync_log`; `clear_backfill_completed` resets one.

### TRUNCATE → DELETE FROM
SQL Server does not allow `TRUNCATE TABLE` on a table referenced by FK constraints, even if the child tables are empty. `--truncate` uses `DELETE FROM` instead.

---

## Rate Limiting

Freshservice enforces API rate limits. When hit (HTTP 429), the code reads `Retry-After` and sleeps automatically. Mitigations:
- 0.5s sleep between pagination pages
- 1s sleep between individual ticket GETs (incremental sync_tickets and workload_sync.py)
- Full load skips individual GETs entirely

---

## Incremental Behavior

| Entity | Strategy |
|---|---|
| Tickets | `updated_since` watermark — only changed tickets fetched via list endpoint |
| Workload fields (planned_*) | Captured by `workload_sync.py` into `ticket_workload` table — separate process, own schedule |
| Conversations / Tasks / Time Entries / Activities | Re-fetched for tickets that appeared in the ticket sync window |
| Problems / Changes / Releases | `updated_since` watermark — same pattern as tickets |
| Agents / Requesters / Groups / Departments / Locations / SLA policies / Roles / Projects | Full reload every run (no `updated_since` filter, small datasets, ~30s overhead). Adds separate `sync_log` entries for `agent_group_members` and `requester_group_members`. Projects also re-sync `project_tasks` and `project_members` per run. |

---

## Expansion Roadmap

Phase 1 is complete. Implement Phase 2 in this order:

Projects and SLA policies are done — both folded into the main `replicator.py` (not standalone scripts) because they change over time and need regular re-syncing. Remaining Phase 2 work:

### Phase 2 — new replicators
1. `assets_replicator.py` — assets (incremental), relationships, components
2. `catalog_replicator.py` — service catalog categories + items
3. `kb_replicator.py` — solution categories, folders, published articles
4. `config_replicator.py` — canned responses, announcements
