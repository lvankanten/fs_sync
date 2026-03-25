"""
One-off script: bulk-update reporting_manager_id on Freshservice requesters.

Changes all requesters who report to Person A to instead report to Person B.
Looks up managers by last name, confirms matches, then confirms before updating.
"""

import os
import time
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

DOMAIN = os.environ["FRESHSERVICE_DOMAIN"]
AUTH = HTTPBasicAuth(os.environ["FRESHSERVICE_APIKEY"], "X")
BASE = f"https://{DOMAIN}/api/v2"


def _get(path, params=None):
    url = f"{BASE}/{path}"
    while True:
        r = requests.get(url, auth=AUTH, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 30)))
            continue
        r.raise_for_status()
        return r.json()


def _put(path, data):
    url = f"{BASE}/{path}"
    while True:
        r = requests.put(url, auth=AUTH, json=data, timeout=30)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 30)))
            continue
        r.raise_for_status()
        return r.json()


def search_requesters_by_last_name(last_name: str) -> list:
    data = _get("requesters", {"query": f'"last_name:\'{last_name}\'"'})
    return data.get("requesters", [])


def get_requesters_by_manager(manager_id: int) -> list:
    """Paginate through all requesters reporting to manager_id."""
    results = []
    page = 1
    while True:
        data = _get("requesters", {
            "query": f'"reporting_manager_id:{manager_id}"',
            "page": page,
            "per_page": 100,
        })
        batch = data.get("requesters", [])
        results.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return results


def pick_requester(label: str) -> dict:
    """Prompt for a last name, search, and let user pick if multiple matches."""
    while True:
        last_name = input(f"Enter last name of {label}: ").strip()
        if not last_name:
            print("  Name cannot be empty.")
            continue

        print(f"  Searching for last name '{last_name}'...")
        matches = search_requesters_by_last_name(last_name)

        if not matches:
            print(f"  No requesters found with last name '{last_name}'. Try again.")
            continue

        if len(matches) == 1:
            r = matches[0]
            full_name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
            confirm = input(f"  Found: {full_name} (ID {r['id']}, email: {r.get('primary_email', 'N/A')}). Use this person? [y/n]: ").strip().lower()
            if confirm == "y":
                return r
            else:
                continue

        # Multiple matches — let user pick
        print(f"  Found {len(matches)} matches:")
        for i, r in enumerate(matches, 1):
            full_name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
            print(f"    {i}. {full_name} (ID {r['id']}, email: {r.get('primary_email', 'N/A')})")

        choice = input(f"  Enter number (1-{len(matches)}) or 0 to search again: ").strip()
        if choice == "0":
            continue
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(matches):
                return matches[idx]
            else:
                print("  Invalid choice.")
        except ValueError:
            print("  Please enter a number.")


def main():
    print("=== Reporting Manager Bulk Update ===\n")

    print("Step 1: Identify the OLD manager (whose direct reports will be reassigned)")
    old_manager = pick_requester("old manager")
    old_name = f"{old_manager.get('first_name', '')} {old_manager.get('last_name', '')}".strip()
    print(f"  Old manager: {old_name} (ID {old_manager['id']})\n")

    print("Step 2: Identify the NEW manager")
    new_manager = pick_requester("new manager")
    new_name = f"{new_manager.get('first_name', '')} {new_manager.get('last_name', '')}".strip()
    print(f"  New manager: {new_name} (ID {new_manager['id']})\n")

    if old_manager["id"] == new_manager["id"]:
        print("Old and new manager are the same person. Nothing to do.")
        return

    print(f"Step 3: Finding all requesters who report to {old_name}...")
    affected = get_requesters_by_manager(old_manager["id"])

    if not affected:
        print(f"  No requesters found with reporting_manager_id = {old_manager['id']}.")
        return

    print(f"\n  Found {len(affected)} requester(s) to update:\n")
    for r in affected:
        full_name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
        print(f"    - {full_name} (ID {r['id']}, email: {r.get('primary_email', 'N/A')})")

    print(f"\nStep 4: Confirm update")
    print(f"  Change reporting_manager_id from {old_name} (ID {old_manager['id']})")
    print(f"  to {new_name} (ID {new_manager['id']})")
    print(f"  for {len(affected)} requester(s).")
    confirm = input("\n  Proceed? [y/n]: ").strip().lower()
    if confirm != "y":
        print("Aborted. No changes made.")
        return

    print("\nStep 5: Updating requesters...")
    success = 0
    failed = []
    for r in affected:
        full_name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
        try:
            _put(f"requesters/{r['id']}", {"reporting_manager_id": new_manager["id"]})
            print(f"  [OK] {full_name} (ID {r['id']})")
            success += 1
        except requests.HTTPError as e:
            print(f"  [FAIL] {full_name} (ID {r['id']}): {e}")
            failed.append(r)

    print(f"\n=== Summary ===")
    print(f"  Updated:  {success}")
    print(f"  Failed:   {len(failed)}")
    if failed:
        print("  Failed IDs:", [r["id"] for r in failed])


if __name__ == "__main__":
    main()
