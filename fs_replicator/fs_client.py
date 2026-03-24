import time
import logging
import requests

log = logging.getLogger(__name__)


class FreshserviceClient:
    def __init__(self, api_key: str, domain: str):
        self.base_url = f"https://{domain}/api/v2"
        self.auth = (api_key, "X")
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({"Content-Type": "application/json"})

    # ── low-level ────────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        while True:
            resp = self.session.get(url, params=params)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                log.warning("Rate limited. Sleeping %ds.", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()

    def _paginate(self, path: str, key: str, params: dict = None) -> list:
        params = dict(params or {})
        params["per_page"] = 100
        page = 1
        all_items = []
        while True:
            params["page"] = page
            data = self._get(path, params)
            items = data.get(key, [])
            all_items.extend(items)
            log.info("  %s page %d: %d records fetched (%d total so far)", path, page, len(items), len(all_items))
            if len(items) < 100:
                break
            page += 1
            time.sleep(0.5)
        return all_items

    # ── tickets ──────────────────────────────────────────────────────────────

    def get_all_tickets(self, updated_since: str = None) -> list:
        """Paginate all tickets. Pass updated_since as ISO8601 string for incremental."""
        params = {"include": "stats"}
        if updated_since:
            params["updated_since"] = updated_since
        return self._paginate("tickets", "tickets", params)

    def get_ticket(self, ticket_id: int) -> dict:
        """Fetch a single ticket (includes description_text and full custom_fields)."""
        return self._get(f"tickets/{ticket_id}").get("ticket", {})

    def get_ticket_fields(self) -> list:
        """Return all ticket field definitions (used for custom field discovery)."""
        try:
            return self._get("ticket_fields").get("ticket_fields", [])
        except Exception as e:
            log.warning("Could not fetch ticket_fields (custom field columns will not be created): %s", e)
            return []

    # ── conversations ─────────────────────────────────────────────────────────

    def get_conversations(self, ticket_id: int) -> list:
        """Return all conversations for a ticket."""
        return self._paginate(f"tickets/{ticket_id}/conversations", "conversations")

    # ── agents & requesters ───────────────────────────────────────────────────

    def get_agents(self) -> list:
        return self._paginate("agents", "agents")

    def get_requesters(self) -> list:
        return self._paginate("requesters", "requesters")

    # ── groups ────────────────────────────────────────────────────────────────

    def get_agent_groups(self) -> list:
        return self._paginate("groups", "groups")

    def get_requester_groups(self) -> list:
        return self._paginate("requester_groups", "requester_groups")

    def get_requester_group_members(self, group_id: int) -> list:
        return self._paginate(f"requester_groups/{group_id}/members", "members")
