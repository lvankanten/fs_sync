# Handoff — FS replicator gap: sync `can_see_all_tickets_from_associated_departments` (+ a few) to the `requesters` table

**Date:** 2026-06-18 · **Discovered under:** FS #41430 restructure · **Tracks against:** task #21 (replicator sync gaps)
**Owner to action:** replicator workstream (this is infra, not a ticket fix — read in the replicator session)

---

## TL;DR
The FS SQL replica's **`requesters`** table is **missing `can_see_all_tickets_from_associated_departments`** (and a few other useful fields). That column is the on/off switch for department-head portal visibility — and **all department heads are requesters**. The column **does** exist on the `agents` table (added 2026-05-01) but was never added to the requester sync. Add it (and ideally the secondary fields below) to the requester upsert so head visibility is auditable/reportable from SQL.

## Evidence (run today, 2026-06-18)
```sql
SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME = 'can_see_all_tickets_from_associated_departments';
-- returns ONLY: agents.   requesters -> absent.
```
Current `requesters` columns (17): active, address, background_information, created_at, department_ids_json, first_name, id, job_title, last_name, location_id, location_name, primary_email, replicated_at, reporting_manager_id, time_zone, updated_at, vip_user.

## Why it matters
- The restructure's **BU-isolation visibility** depends on `can_see_all_tickets_from_associated_departments = true` on each **head requester** (native `department_head` mechanism — no Business Agent license needed). See `wiki/concepts/freshservice-replicator-architecture.md` and the `reference_fs_department_head_portal_visibility` memory.
- Because the flag isn't replicated for requesters, you **cannot audit "do the heads still have visibility?" from SQL** — only via a live FS API `GET /api/v2/requesters/{id}` per head. The Tickets-v4 and Reports To Matrix reports (replica-backed) can't show or filter on it either.
- **Silent-break risk:** a `PUT /requesters/{id}` that sends `department_ids` **without** re-sending the flag silently resets it to `false` (verified gotcha — see `reference_fs_department_head_portal_visibility`). Today nothing replica-side would detect that; a head would quietly lose all-department visibility until a complaint or a live per-head check. Replicating the column closes that monitoring blind spot.

## The fix
In the replicator's **requester upsert / column mapping** (same place the 2026-05-01 change added 19 columns to the **agents** table — use that change as the template), add to the `requesters` table + sync:

| Priority | Column | Type | FS requester API field | Why |
|---|---|---|---|---|
| **Required** | `can_see_all_tickets_from_associated_departments` | `bit` | same name (bool) | head-visibility audit/monitoring — the actual gap |
| Nice-to-have | `has_logged_in` | `bit` | `has_logged_in` | portal-adoption / true-active analysis |
| Nice-to-have | `secondary_emails` | `nvarchar` (JSON) | `secondary_emails` (array) | duplicate-account / alias work (e.g. the twin-account cleanup this session) |
| Optional | `work_phone_number`, `mobile_phone_number`, `language`, `time_format` | per API | same | completeness; low value |

Lead with the **Required** one; the rest are "while you're in there."

## Acceptance criteria
1. `INFORMATION_SCHEMA` shows `can_see_all_tickets_from_associated_departments` on `requesters`.
2. After a sync, the 12 Reports To v3 heads show `can_see_all_tickets_from_associated_departments = 1` in the replica (they were all set/verified `true` live on 2026-06-18 — see `raw/tickets/fs41430/log.md`).
3. A spot-check matches the live FS API for 2-3 heads (e.g. Laura Neuschafer 8005315766, Bill Bellingham 8006036335).
4. (If added) `secondary_emails` / `has_logged_in` populate and match the API.

## Pointers
- Replicator architecture + where the column mapping is defined: `wiki/concepts/freshservice-replicator-architecture.md`
- Schema cheat-sheet / prior agent-column add pattern: `reference_fs_replicator_schema` memory (the 2026-05-01 "added 19 columns to agents" change)
- Manual trigger: `reference_fs_replicator_manual_trigger` memory
- Visibility mechanism + the reset gotcha: `reference_fs_department_head_portal_visibility` memory
- Discovery context: `raw/tickets/fs41430/log.md` (2026-06-18 "Executive dept restored to all 12 heads") · FS #41430 https://jesengr.freshservice.com/helpdesk/tickets/41430
