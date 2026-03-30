"""
fs_lib.freshservice — shared Freshservice API client for FreshService+ tools.

Filter query syntax (passed to get_tickets_by_query / translate_query):
  status:Open                     single status by name
  status:not(Closed)              all statuses except named ones
  status:in(Open,Pending)         named statuses only
  agent_id:12345                  raw API field
  tag:'Project'                   tag filter
  id:12345                        fetch single ticket by ID (bypasses filter endpoint)
  id:in(12345,12346)              fetch specific tickets by ID
  id:range(12340,12350)           fetch inclusive ID range
  status:not(Closed) AND agent_id:12345 AND tag:'Project'   combined

Client-side pseudo-filters (stripped from API query, applied after fetch):
  planned_effort:empty            field is null, empty string, or 0
  planned_effort:not_empty        field has a truthy value
"""
import re
import time
import requests


# ---------------------------------------------------------------------------
# Status translation
# ---------------------------------------------------------------------------

STATUS_MAP = {
    'open': 2,
    'pending': 3,
    'resolved': 4,
    'closed': 5,
    'development': 6,
    'waiting on requester': 7,
}

STATUS_LABELS = {
    2: 'Open', 3: 'Pending', 4: 'Resolved', 5: 'Closed',
    6: 'Development', 7: 'Waiting on Requester',
}

PRIORITY_NAMES = {'low': 1, 'medium': 2, 'high': 3, 'urgent': 4}
PRIORITY_LABELS = {1: 'Low', 2: 'Medium', 3: 'High', 4: 'Urgent'}

STANDARD_FIELDS = {
    'status', 'priority', 'responder_id', 'group_id', 'due_by',
    'subject', 'description', 'type', 'source', 'category',
    'sub_category', 'item_category', 'department_id', 'urgency',
    'impact', 'tags', 'problem', 'change_initiating_ticket',
    'change_initiated_by_ticket', 'planned_effort',
    'planned_start_date', 'planned_end_date',
}


def _expand_statuses(names):
    parts = []
    for name in names:
        key = name.strip().lower()
        if key in STATUS_MAP:
            parts.append(f'status:{STATUS_MAP[key]}')
    return '(' + ' OR '.join(parts) + ')' if parts else ''


def _extract_client_filters(query):
    """Strip field:empty / field:not_empty pseudo-filters from query.

    Returns (cleaned_query, list_of_filter_funcs).
    Each filter func takes a ticket dict and returns True to keep it.
    """
    filters = []

    def _replace_empty(m):
        field = m.group(1)
        filters.append(lambda t, f=field: not _resolve_field(t, f))
        return ''

    def _replace_not_empty(m):
        field = m.group(1)
        filters.append(lambda t, f=field: bool(_resolve_field(t, f)))
        return ''

    query = re.sub(r'(\w+):not_empty\b', _replace_not_empty, query, flags=re.IGNORECASE)
    query = re.sub(r'(\w+):empty\b', _replace_empty, query, flags=re.IGNORECASE)

    # Clean up dangling AND operators left after stripping
    query = re.sub(r'\s+AND\s+AND\s+', ' AND ', query, flags=re.IGNORECASE)
    query = re.sub(r'^\s*AND\s+', '', query, flags=re.IGNORECASE)
    query = re.sub(r'\s+AND\s*$', '', query, flags=re.IGNORECASE)
    query = query.strip()

    return query, filters


def _resolve_field(ticket, field):
    """Look up a field value, checking top-level then custom_fields."""
    if field in ticket:
        return ticket[field]
    custom = ticket.get('custom_fields') or {}
    return custom.get(field)


def _apply_client_filters(tickets, filters):
    """Apply client-side filter functions to a ticket list."""
    for f in filters:
        tickets = [t for t in tickets if f(t)]
    return tickets


def translate_query(query):
    """Translate human-readable filter syntax to Freshservice API query string.

    status:Open               -> status:2
    status:not(Closed)        -> (status:2 OR status:3 OR ...)
    status:in(Open,Pending)   -> (status:2 OR status:3)
    """
    def replace_not(m):
        excluded = {n.strip().lower() for n in m.group(1).split(',')}
        included = [k for k in STATUS_MAP if k not in excluded]
        return _expand_statuses(included)
    query = re.sub(r'status:not\(([^)]+)\)', replace_not, query, flags=re.IGNORECASE)

    def replace_in(m):
        included = [n.strip() for n in m.group(1).split(',')]
        return _expand_statuses(included)
    query = re.sub(r'status:in\(([^)]+)\)', replace_in, query, flags=re.IGNORECASE)

    def replace_single(m):
        name = m.group(1).lower()
        return f'status:{STATUS_MAP[name]}' if name in STATUS_MAP else m.group(0)
    query = re.sub(
        r'status:(' + '|'.join(re.escape(k) for k in STATUS_MAP) + r')\b',
        replace_single,
        query,
        flags=re.IGNORECASE,
    )
    return query


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class FreshserviceError(Exception):
    def __init__(self, message, status_code=None, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class FreshserviceClient:

    def __init__(self, domain, api_key):
        self.base_url = f'https://{domain}/api/v2'
        self.session = requests.Session()
        self.session.auth = (api_key, 'X')
        self.session.headers['Content-Type'] = 'application/json'
        self._agents = None
        self._groups = None

    # --- HTTP helpers ---

    def _get(self, path, params=None):
        while True:
            resp = self.session.get(f'{self.base_url}{path}', params=params)
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get('Retry-After', 30)))
                continue
            self._raise(resp)
            return resp.json()

    def _put(self, path, data):
        while True:
            resp = self.session.put(f'{self.base_url}{path}', json=data)
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get('Retry-After', 30)))
                continue
            self._raise(resp)
            return resp.json()

    def _raise(self, resp):
        if not resp.ok:
            try:
                body = resp.json()
                msg = body.get('description', resp.text)
                details = body.get('errors')
            except Exception:
                msg = resp.text
                details = None
            raise FreshserviceError(msg, resp.status_code, details)

    # --- Agents ---

    def get_agents(self):
        if self._agents is None:
            self._agents = self._get('/agents')['agents']
        return self._agents

    def find_agent(self, name):
        """Find an agent by partial name match. Returns the agent dict or None."""
        name_lower = name.lower()
        for agent in self.get_agents():
            full = f"{agent['first_name']} {agent.get('last_name') or ''}".strip()
            if name_lower in full.lower():
                return agent
        return None

    # --- Groups ---

    def get_groups(self):
        if self._groups is None:
            self._groups = self._get('/groups')['groups']
        return self._groups

    def find_group(self, name):
        """Find a group by partial name match. Returns the group dict or None."""
        name_lower = name.lower()
        for group in self.get_groups():
            if name_lower in group['name'].lower():
                return group
        return None

    # --- Tickets ---

    def get_tickets_by_query(self, query):
        """Fetch all tickets matching a human-readable filter query, auto-paginating.

        The query is translated (status names → codes) before being sent to the API.
        Supports id: shortcuts: id:12345, id:in(1,2,3), id:range(1,10)
        Combined: id:in(1,2) AND status:not(Closed)
        Client-side pseudo-filters: field:empty, field:not_empty

        Returns (tickets, total).
        """
        q = query.strip()

        # Extract client-side pseudo-filters before any other processing
        q, client_filters = _extract_client_filters(q)

        # Combined: id:... AND <rest>
        m = re.match(r'^(id:(?:\d+|in\([^)]+\)|range\(\d+,\d+\)))\s+AND\s+(.+)$', q, re.IGNORECASE)
        if m:
            ids = self._ids_from_id_part(m.group(1))
            allowed = self._allowed_statuses(translate_query(m.group(2)))
            tickets = self._fetch_by_ids(ids)
            if allowed:
                tickets = [t for t in tickets if t.get('status') in allowed]
            tickets = _apply_client_filters(tickets, client_filters)
            return tickets, len(tickets)

        # id-only
        ids = self._ids_from_id_part(q)
        if ids:
            tickets = self._fetch_by_ids(ids)
            tickets = _apply_client_filters(tickets, client_filters)
            return tickets, len(tickets)

        # Normal filter query
        translated = translate_query(q)
        tickets = []
        total = None
        page = 1
        while True:
            resp = self.session.get(
                f'{self.base_url}/tickets/filter',
                params={'query': f'"{translated}"', 'page': page, 'per_page': 100},
            )
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get('Retry-After', 30)))
                continue
            self._raise(resp)
            data = resp.json()
            batch = data.get('tickets', [])
            if total is None:
                total = data.get('total', 0)
            tickets.extend(batch)
            if len(tickets) >= total or not batch:
                break
            page += 1
        tickets = _apply_client_filters(tickets, client_filters)
        return tickets, len(tickets)

    def _ids_from_id_part(self, id_part):
        m = re.match(r'^id:(\d+)$', id_part, re.IGNORECASE)
        if m:
            return [int(m.group(1))]
        m = re.match(r'^id:in\(([^)]+)\)$', id_part, re.IGNORECASE)
        if m:
            return [int(x.strip()) for x in m.group(1).split(',') if x.strip().isdigit()]
        m = re.match(r'^id:range\((\d+),(\d+)\)$', id_part, re.IGNORECASE)
        if m:
            return list(range(int(m.group(1)), int(m.group(2)) + 1))
        return []

    def _fetch_by_ids(self, ids):
        tickets = []
        for tid in ids:
            try:
                tickets.append(self.get_ticket(tid))
            except FreshserviceError:
                pass
        return tickets

    def _allowed_statuses(self, translated_query):
        matches = re.findall(r'status:(\d+)', translated_query)
        return {int(m) for m in matches} if matches else None

    def get_ticket(self, ticket_id, include=None):
        params = {'include': include} if include else None
        return self._get(f'/tickets/{ticket_id}', params=params)['ticket']

    def get_ticket_sample(self):
        data = self._get('/tickets', params={'page': 1, 'per_page': 1})
        tickets = data.get('tickets', [])
        return tickets[0] if tickets else {}

    def get_conversations(self, ticket_id):
        """Fetch all conversations for a ticket."""
        return self._get(f'/tickets/{ticket_id}/conversations').get('conversations', [])

    def get_ticket_activities(self, ticket_id):
        """Fetch the first page of activities for a ticket (newest-first)."""
        return self._get(f'/tickets/{ticket_id}/activities').get('activities', [])

    def get_agent_name(self, agent_id):
        """Return 'First Last' for an agent ID, cached per client instance."""
        if not hasattr(self, '_agent_name_cache'):
            self._agent_name_cache = {}
        if agent_id not in self._agent_name_cache:
            try:
                agent = self._get(f'/agents/{agent_id}').get('agent', {})
                name = f"{agent.get('first_name', '')} {agent.get('last_name', '')}".strip()
            except FreshserviceError:
                name = ''
            self._agent_name_cache[agent_id] = name
        return self._agent_name_cache[agent_id]

    def update_custom_fields(self, ticket_id, fields):
        """Write custom field values to a ticket. fields = {field_name: value}."""
        self._put(f'/tickets/{ticket_id}', {'custom_fields': fields})

    def update_ticket(self, ticket_id, fields):
        """Update a ticket. None values are sent as JSON null.
        Unknown fields are sent as custom_fields automatically.
        Accepts status/priority by name or numeric code.
        """
        payload = {}
        custom = {}

        for key, value in fields.items():
            if value is not None:
                if key == 'status':
                    value = STATUS_MAP.get(str(value).lower(), value)
                elif key == 'priority':
                    value = PRIORITY_NAMES.get(str(value).lower(), value)

            if key in STANDARD_FIELDS:
                payload[key] = value
            else:
                custom[key] = value

        if custom:
            payload['custom_fields'] = custom

        return self._put(f'/tickets/{ticket_id}', payload)['ticket']
