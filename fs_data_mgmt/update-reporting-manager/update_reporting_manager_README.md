# update_reporting_manager.py

## Background

> "i need a one-off script to change requester Reporting Manager Name to a different Reporting Manager Name"

This script bulk-reassigns the reporting manager for all Freshservice requesters who currently report to Person A, switching them to report to Person B. It looks up managers by last name, confirms matches interactively, and requires explicit confirmation before making any changes.

## Requirements

- Python 3.8+
- Freshservice account with API access
- The API key user must have permission to read and update requesters

Install dependencies:

```bash
pip install -r requirements.txt
```

## Setup

Create a `.env` file in the same directory as the script:

```
FRESHSERVICE_DOMAIN=yourcompany.freshservice.com
FRESHSERVICE_APIKEY=your_api_key_here
```

The API key is used as the Basic Auth password (username is the key itself, password is `X` — standard Freshservice convention).

## Usage

```bash
python update_reporting_manager.py
```

The script walks through five steps interactively:

1. **Find old manager** — enter their last name; pick from results if multiple match
2. **Find new manager** — same lookup
3. **Preview affected requesters** — lists everyone whose `reporting_manager_id` currently points to the old manager
4. **Confirm** — no changes are made until you type `y`
5. **Update** — PUTs each requester and prints a success/fail summary

## API Calls

| Purpose | Method | Endpoint |
|---------|--------|----------|
| Find manager by last name | `GET` | `/api/v2/requesters?query="last_name:'Surname'"` |
| Find affected requesters | `GET` | `/api/v2/requesters?query="reporting_manager_id:ID"` (paginated) |
| Update requester | `PUT` | `/api/v2/requesters/{id}` with `{"reporting_manager_id": new_id}` |

All requests use HTTP Basic Auth with the API key as the username and `X` as the password.

## Notes

- The script only changes `reporting_manager_id`; no other requester fields are touched.
- Rate-limit responses (HTTP 429) are handled automatically with the `Retry-After` backoff from Freshservice.
- If any individual update fails (e.g. permission error), the script continues and reports the failed IDs at the end.
