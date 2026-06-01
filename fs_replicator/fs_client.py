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

    def _paginate(self, path: str, key: str, params: dict = None, max_pages: int = None) -> list:
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
            if len(items) < 100 or (max_pages and page >= max_pages):
                break
            page += 1
            time.sleep(0.5)
        return all_items

    # ── tickets ──────────────────────────────────────────────────────────────

    def get_all_tickets(self, updated_since: str = None, max_pages: int = None,
                        order_by: str = None, order_type: str = None) -> list:
        """Paginate all tickets. Pass updated_since as ISO8601 string for incremental."""
        params = {"include": "stats,tags"}
        if updated_since:
            params["updated_since"] = updated_since
        if order_by:
            params["order_by"] = order_by
        if order_type:
            params["order_type"] = order_type
        return self._paginate("tickets", "tickets", params, max_pages=max_pages)

    def get_ticket(self, ticket_id: int) -> dict:
        """Fetch a single ticket (includes description_text and full custom_fields)."""
        return self._get(f"tickets/{ticket_id}").get("ticket", {})

    def get_ticket_fields(self) -> list:
        """Return all ticket field definitions (used for custom field discovery)."""
        try:
            return self._get("ticket_form_fields").get("ticket_fields", [])
        except Exception as e:
            log.warning("Could not fetch ticket_form_fields (custom field columns will not be created): %s", e)
            return []

    # ── conversations ─────────────────────────────────────────────────────────

    def get_conversations(self, ticket_id: int) -> list:
        """Return all conversations for a ticket."""
        return self._paginate(f"tickets/{ticket_id}/conversations", "conversations")

    def get_ticket_tasks(self, ticket_id: int) -> list:
        """Return all tasks for a ticket."""
        return self._paginate(f"tickets/{ticket_id}/tasks", "tasks")

    def get_ticket_time_entries(self, ticket_id: int) -> list:
        """Return all time entries for a ticket."""
        return self._paginate(f"tickets/{ticket_id}/time_entries", "time_entries")

    # ── agents & requesters ───────────────────────────────────────────────────

    def get_agents(self) -> list:
        return self._paginate("agents", "agents")

    def get_requesters(self, active_only: bool = True) -> list:
        """Paginate all requesters. Default active_only=True filters to active users
        (~37% of total — saves significant API time)."""
        params = {"active": "true"} if active_only else None
        return self._paginate("requesters", "requesters", params)

    # ── groups ────────────────────────────────────────────────────────────────

    def get_agent_groups(self) -> list:
        return self._paginate("groups", "groups")

    def get_requester_groups(self) -> list:
        return self._paginate("requester_groups", "requester_groups")

    def get_requester_group_members(self, group_id: int) -> list:
        return self._paginate(f"requester_groups/{group_id}/members", "requesters")

    # ── departments & locations ───────────────────────────────────────────────

    def get_departments(self) -> list:
        return self._paginate("departments", "departments")

    def get_locations(self) -> list:
        return self._paginate("locations", "locations")

    # ── SLA policies ──────────────────────────────────────────────────────────

    def get_sla_policies(self) -> list:
        """Return all SLA policies. Small dataset — full reload per run."""
        return self._paginate("sla_policies", "sla_policies")

    # ── problems ──────────────────────────────────────────────────────────────

    def get_all_problems(self, updated_since: str = None, max_pages: int = None) -> list:
        params = {}
        if updated_since:
            params["updated_since"] = updated_since
        return self._paginate("problems", "problems", params, max_pages=max_pages)

    def get_problem(self, problem_id: int) -> dict:
        return self._get(f"problems/{problem_id}").get("problem", {})

    def get_problem_fields(self) -> list:
        try:
            return self._get("problem_form_fields").get("problem_fields", [])
        except Exception as e:
            log.warning("Could not fetch problem_form_fields: %s", e)
            return []

    def get_problem_conversations(self, problem_id: int) -> list:
        return self._paginate(f"problems/{problem_id}/conversations", "conversations")

    def get_problem_tasks(self, problem_id: int) -> list:
        return self._paginate(f"problems/{problem_id}/tasks", "tasks")

    def get_problem_time_entries(self, problem_id: int) -> list:
        return self._paginate(f"problems/{problem_id}/time_entries", "time_entries")

    # ── changes ───────────────────────────────────────────────────────────────

    def get_all_changes(self, updated_since: str = None, max_pages: int = None) -> list:
        params = {}
        if updated_since:
            params["updated_since"] = updated_since
        return self._paginate("changes", "changes", params, max_pages=max_pages)

    def get_change(self, change_id: int) -> dict:
        return self._get(f"changes/{change_id}").get("change", {})

    def get_change_fields(self) -> list:
        try:
            return self._get("change_form_fields").get("change_fields", [])
        except Exception as e:
            log.warning("Could not fetch change_form_fields: %s", e)
            return []

    def get_change_conversations(self, change_id: int) -> list:
        return self._paginate(f"changes/{change_id}/conversations", "conversations")

    def get_change_tasks(self, change_id: int) -> list:
        return self._paginate(f"changes/{change_id}/tasks", "tasks")

    def get_change_time_entries(self, change_id: int) -> list:
        return self._paginate(f"changes/{change_id}/time_entries", "time_entries")

    # ── releases ──────────────────────────────────────────────────────────────

    def get_all_releases(self, updated_since: str = None, max_pages: int = None) -> list:
        params = {}
        if updated_since:
            params["updated_since"] = updated_since
        return self._paginate("releases", "releases", params, max_pages=max_pages)

    def get_release(self, release_id: int) -> dict:
        return self._get(f"releases/{release_id}").get("release", {})

    def get_release_fields(self) -> list:
        try:
            return self._get("release_form_fields").get("release_fields", [])
        except Exception as e:
            log.warning("Could not fetch release_form_fields: %s", e)
            return []

    def get_release_conversations(self, release_id: int) -> list:
        return self._paginate(f"releases/{release_id}/conversations", "conversations")

    def get_release_tasks(self, release_id: int) -> list:
        return self._paginate(f"releases/{release_id}/tasks", "tasks")

    def get_release_time_entries(self, release_id: int) -> list:
        return self._paginate(f"releases/{release_id}/time_entries", "time_entries")

    # ── projects (NewGen, pm/ namespace) ──────────────────────────────────────
    # API path: /api/v2/pm/projects (NOT /api/v2/projects which returns 403)
    # Status/priority enum IDs are project-scoped; no metadata endpoint exposed.

    def get_projects(self, include_archived: bool = False) -> list:
        """Paginate all NewGen projects. JES has ~50 projects total — small dataset, full re-sync per run."""
        params = {}
        if include_archived:
            params["archived"] = "true"
        return self._paginate("pm/projects", "projects", params)

    def get_project_tasks(self, project_id: int) -> list:
        """Return all tasks for a project. Tasks have their own status_id enum (large IDs, per template)."""
        return self._paginate(f"pm/projects/{project_id}/tasks", "tasks")

    def get_project_memberships(self, project_id: int) -> list:
        """Return all memberships for a project (users + access_type + manage_settings + project_manager flags)."""
        return self._paginate(f"pm/projects/{project_id}/memberships", "memberships")
