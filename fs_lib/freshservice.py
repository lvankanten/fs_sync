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
    'change_initiated_by_ticket',
}


def _expand_statuses(names):
    parts = []
    for name in names:
        key = name.strip().lower()
        if key in STATUS_MAP:
            parts.append(f'status:{STATUS_MAP[key]}')
    return '(' + ' OR '.join(parts) + ')' if parts else ''


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

        Returns (tickets, total).
        """
        q = query.strip()

        # Combined: id:... AND <rest>
        m = re.match(r'^(id:(?:\d+|in\([^)]+\)|range\(\d+,\d+\)))\s+AND\s+(.+)$', q, re.IGNORECASE)
        if m:
            ids = self._ids_from_id_part(m.group(1))
            allowed = self._allowed_statuses(translate_query(m.group(2)))
            tickets = self._fetch_by_ids(ids)
            if allowed:
                tickets = [t for t in tickets if t.get('status') in allowed]
            return tickets, len(tickets)

        # id-only
        ids = self._ids_from_id_part(q)
        if ids:
            tickets = self._fetch_by_ids(ids)
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
        return tickets, total

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

    def get_ticket(self, ticket_id):
        return self._get(f'/tickets/{ticket_id}')['ticket']

    def get_ticket_sample(self):
        data = self._get('/tickets', params={'page': 1, 'per_page': 1})
        tickets = data.get('tickets', [])
        return tickets[0] if tickets else {}

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
