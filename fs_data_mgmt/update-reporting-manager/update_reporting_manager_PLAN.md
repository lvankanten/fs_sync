# Plan: One-off Reporting Manager Update Script

## Context
The user needs to bulk-update the `reporting_manager_id` field on requester profiles in Freshservice — changing all requesters who report to Person A to instead report to Person B. The script should look up managers by name and confirm before making changes.

## Approach

Create a standalone script `update_reporting_manager.py` in `C:\Users\lvankanten\ticket-field-updater\` that:

1. Prompts for old manager name and new manager name
2. Searches Freshservice for each by last name, confirms the match
3. Finds all requesters whose `reporting_manager_id` matches the old manager
4. Prints the list and asks for confirmation before updating
5. Updates each requester's `reporting_manager_id` to the new manager
6. Prints a summary

## Freshservice API calls

All use `HTTPBasicAuth(FRESHSERVICE_APIKEY, "X")` from `.env`.

- **Find manager by name:** `GET /api/v2/requesters?query="last_name:'Surname'"`
- **Find affected requesters:** `GET /api/v2/requesters?query="reporting_manager_id:ID"` (paginated)
- **Update requester:** `PUT /api/v2/requesters/{id}` with `{"reporting_manager_id": new_id}`

## Critical files

- New file: `C:\Users\lvankanten\ticket-field-updater\update_reporting_manager.py`
- Reference: `C:\Users\lvankanten\ticket-field-updater\freshservice.py` — reuse `HTTPBasicAuth` pattern and `.env` loading

## Script outline

```python
load_dotenv()
domain = os.environ["FRESHSERVICE_DOMAIN"]
auth = HTTPBasicAuth(os.environ["FRESHSERVICE_APIKEY"], "X")

# 1. Prompt for names
# 2. Search each by last name, handle multiple matches by listing and asking user to pick
# 3. GET /api/v2/requesters?query="reporting_manager_id:OLD_ID" (paginate)
# 4. Print affected requesters, confirm
# 5. PUT each with new reporting_manager_id
# 6. Print success/fail counts
```

## Verification

Run `python update_reporting_manager.py`, enter "Bellingham" as old manager and a test name as new, verify the dry-run list looks correct before confirming.
