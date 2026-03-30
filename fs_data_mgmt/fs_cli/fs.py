#!/usr/bin/env python
"""
fs.py — Freshservice CLI
Usage examples:
  python fs.py tickets --query "status:Open"
  python fs.py tickets --agent "Lesley" --query "status:not(Closed)"
  python fs.py tickets --query "status:not(Closed) AND tag:'Project'"
  python fs.py tickets --agent "Lesley" --query "status:not(Closed)" --count

  # Single ticket update
  python fs.py update 12345 priority=high status=pending
  python fs.py update 12345 planned_effort=null

  # Bulk update via filter query
  python fs.py update --agent "Lesley" --query "status:not(Closed)" planned_effort=null
  python fs.py update --query "status:not(Closed) AND tag:'Project'" planned_effort=null

  python fs.py fields
  python fs.py fields --ticket-id 12345
"""
import os
import sys
import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# fs_lib is two levels up from this file (FreshService+/fs_lib/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from fs_lib.freshservice import FreshserviceClient, FreshserviceError, STATUS_LABELS, PRIORITY_LABELS

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

console = Console()

STATUS_COLORS = {'Open': 'green', 'Pending': 'yellow', 'Resolved': 'blue', 'Closed': 'dim',
                 'Development': 'cyan', 'Waiting on Requester': 'magenta'}
PRIORITY_COLORS = {'Low': 'dim', 'Medium': 'white', 'High': 'yellow', 'Urgent': 'red'}


def get_client():
    domain = os.getenv('FRESHSERVICE_DOMAIN')
    api_key = os.getenv('FRESHSERVICE_APIKEY')
    if not domain or not api_key:
        console.print('[red]Error:[/red] FRESHSERVICE_DOMAIN and FRESHSERVICE_APIKEY must be set in .env')
        sys.exit(1)
    return FreshserviceClient(domain, api_key)


def colored(text, color_map):
    color = color_map.get(text, 'white')
    return f'[{color}]{text}[/{color}]'


def parse_assignments(assignments):
    """Parse field=value pairs. 'null' becomes None, plain integers become int."""
    fields = {}
    for assignment in assignments:
        if '=' not in assignment:
            console.print(f'[red]Invalid argument:[/red] {assignment!r}  (expected field=value)')
            sys.exit(1)
        key, _, value = assignment.partition('=')
        key = key.strip()
        value = value.strip()
        if value.lower() == 'null':
            value = None
        elif value.lstrip('-').isdigit():
            value = int(value)
        fields[key] = value
    return fields


def requester_name(ticket):
    """Extract requester name from a ticket dict, falling back to ID."""
    r = ticket.get('requester') or {}
    name = r.get('name') or f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
    return name or f'ID {ticket.get("requester_id", "?")}'


def build_query(query, agent_id=None, group_id=None):
    """Prepend resolved agent/group IDs to a query string."""
    parts = []
    if agent_id:
        parts.append(f'agent_id:{agent_id}')
    if group_id:
        parts.append(f'group_id:{group_id}')
    if query:
        parts.append(query)
    return ' AND '.join(parts)


@click.group()
def cli():
    """Freshservice CLI — query and update tickets directly."""
    pass


@cli.command()
@click.option('--agent', '-a', metavar='NAME', help='Filter by agent name (partial match)')
@click.option('--agent-id', type=int, metavar='ID', help='Filter by agent ID')
@click.option('--group', '-g', metavar='NAME', help='Filter by group name (partial match)')
@click.option('--group-id', type=int, metavar='ID', help='Filter by group ID')
@click.option('--query', '-q', metavar='QUERY', default='status:Open', show_default=True,
              help='Filter query (e.g. "status:not(Closed) AND tag:\'Project\'")')
@click.option('--count', is_flag=True, help='Print total count only')
def tickets(agent, agent_id, group, group_id, query, count):
    """List or count tickets.

    \b
    Query syntax:
      status:Open
      status:not(Closed)
      status:in(Open,Pending)
      status:not(Closed) AND tag:'Project'
      agent_id:12345 AND status:Open
    """
    client = get_client()

    if agent and not agent_id:
        found = client.find_agent(agent)
        if not found:
            console.print(f'[red]No agent found matching:[/red] {agent}')
            sys.exit(1)
        agent_id = found['id']
        console.print(f'[dim]Agent:[/dim] {found["first_name"]} {found.get("last_name") or ""} (ID {agent_id})')

    if group and not group_id:
        found = client.find_group(group)
        if not found:
            console.print(f'[red]No group found matching:[/red] {group}')
            sys.exit(1)
        group_id = found['id']
        console.print(f'[dim]Group:[/dim] {found["name"]} (ID {group_id})')

    full_query = build_query(query, agent_id=agent_id, group_id=group_id)

    with console.status('Fetching tickets...'):
        try:
            ticket_list, total = client.get_tickets_by_query(full_query)
        except FreshserviceError as e:
            console.print(f'[red]API error:[/red] {e}')
            if e.details:
                for err in e.details:
                    console.print(f'  [dim]{err}[/dim]')
            sys.exit(1)

    if count:
        console.print(f'[bold]{total}[/bold] ticket(s)')
        return

    table = Table(show_header=True, header_style='bold', box=None, pad_edge=False)
    table.add_column('ID', style='cyan', no_wrap=True, min_width=8)
    table.add_column('Subject', min_width=40, max_width=70, no_wrap=True, overflow='ellipsis')
    table.add_column('Status', no_wrap=True)
    table.add_column('Priority', no_wrap=True)
    table.add_column('Created', no_wrap=True)

    for t in ticket_list:
        status_label = STATUS_LABELS.get(t.get('status'), str(t.get('status', '')))
        priority_label = PRIORITY_LABELS.get(t.get('priority'), str(t.get('priority', '')))
        created = (t.get('created_at') or '')[:10]

        table.add_row(
            str(t['id']),
            t.get('subject') or '',
            colored(status_label, STATUS_COLORS),
            colored(priority_label, PRIORITY_COLORS),
            created,
        )

    console.print(table)
    console.print(f'[dim]{len(ticket_list)} ticket(s)[/dim]')


@cli.command()
@click.argument('args_in', nargs=-1, required=True, metavar='[ticket_id] field=value ...')
@click.option('--agent', '-a', metavar='NAME', help='Filter by agent name (partial match)')
@click.option('--agent-id', type=int, metavar='ID', help='Filter by agent ID')
@click.option('--group', '-g', metavar='NAME', help='Filter by group name (partial match)')
@click.option('--group-id', type=int, metavar='ID', help='Filter by group ID')
@click.option('--query', '-q', metavar='QUERY',
              help='Filter query (e.g. "status:not(Closed)")')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt')
def update(args_in, agent, agent_id, group, group_id, query, yes):
    """Update ticket fields — single ticket or bulk via filter query.

    Pass a ticket ID for single-ticket mode, or use --query (with optional
    --agent/--group) for bulk. Use field=null to clear a field.

    \b
    Single ticket:
      python fs.py update 12345 priority=high
      python fs.py update 12345 planned_effort=null

    \b
    Bulk:
      python fs.py update --agent "Lesley" --query "status:not(Closed)" planned_effort=null
      python fs.py update --query "status:not(Closed) AND tag:'Project'" planned_effort=null
    """
    # Split args_in: digit-only arg is ticket_id, everything else is field=value
    ticket_id = None
    raw_assignments = []
    for arg in args_in:
        if '=' not in arg:
            if arg.isdigit():
                ticket_id = int(arg)
            else:
                console.print(f'[red]Invalid argument:[/red] {arg!r}  (expected a ticket ID or field=value)')
                sys.exit(1)
        else:
            raw_assignments.append(arg)

    if not raw_assignments:
        console.print('[red]Error:[/red] At least one field=value assignment is required.')
        sys.exit(1)

    fields = parse_assignments(raw_assignments)

    has_filters = bool(agent or agent_id or group or group_id or query)

    if ticket_id and has_filters:
        console.print('[red]Error:[/red] Cannot combine a ticket ID with filter options.')
        sys.exit(1)

    if not ticket_id and not has_filters:
        console.print('[red]Error:[/red] Specify a ticket ID or filter options (--query, --agent, --group).')
        sys.exit(1)

    client = get_client()

    fields_display = '  '.join(
        f'[cyan]{k}[/cyan] = [yellow]{v if v is not None else "null"}[/yellow]'
        for k, v in fields.items()
    )

    # --- Single ticket mode ---
    if ticket_id:
        try:
            ticket = client.get_ticket(ticket_id)
        except FreshserviceError as e:
            console.print(f'[red]Could not fetch ticket #{ticket_id}:[/red] {e}')
            sys.exit(1)

        console.print(f'  [cyan]#{ticket_id}[/cyan]  {ticket.get("subject", "")}  [dim]{requester_name(ticket)}[/dim]')
        console.print(f'Will set: {fields_display}\n')

        if not yes:
            click.confirm('Proceed?', abort=True)

        try:
            client.update_ticket(ticket_id, fields)
        except FreshserviceError as e:
            console.print(f'[red]Update failed:[/red] {e}')
            if e.details:
                for err in e.details:
                    console.print(f'  [dim]{err}[/dim]')
            sys.exit(1)

        console.print(f'[green]Updated ticket #{ticket_id}[/green]')
        return

    # --- Bulk mode ---
    if agent and not agent_id:
        found = client.find_agent(agent)
        if not found:
            console.print(f'[red]No agent found matching:[/red] {agent}')
            sys.exit(1)
        agent_id = found['id']
        console.print(f'[dim]Agent:[/dim] {found["first_name"]} {found.get("last_name") or ""} (ID {agent_id})')

    if group and not group_id:
        found = client.find_group(group)
        if not found:
            console.print(f'[red]No group found matching:[/red] {group}')
            sys.exit(1)
        group_id = found['id']
        console.print(f'[dim]Group:[/dim] {found["name"]} (ID {group_id})')

    full_query = build_query(query or '', agent_id=agent_id, group_id=group_id)

    with console.status('Fetching tickets...'):
        try:
            ticket_list, total = client.get_tickets_by_query(full_query)
        except FreshserviceError as e:
            console.print(f'[red]API error:[/red] {e}')
            if e.details:
                for err in e.details:
                    console.print(f'  [dim]{err}[/dim]')
            sys.exit(1)

    if not ticket_list:
        console.print('[yellow]No tickets found.[/yellow]')
        return

    console.print(f'Found [bold]{len(ticket_list)}[/bold] ticket(s). Will set: {fields_display}\n')

    table = Table(show_header=False, box=None, pad_edge=False, padding=(0, 2, 0, 0))
    table.add_column('ID', style='cyan', no_wrap=True)
    table.add_column('Subject', max_width=60, no_wrap=True, overflow='ellipsis')
    table.add_column('Requester', style='dim')

    for t in ticket_list:
        table.add_row(f'#{t["id"]}', t.get('subject') or '', requester_name(t))

    console.print(table)
    console.print()

    if not yes:
        click.confirm('Proceed?', abort=True)

    success = 0
    errors = 0
    with console.status(f'Updating {len(ticket_list)} ticket(s)...'):
        for t in ticket_list:
            try:
                client.update_ticket(t['id'], fields)
                success += 1
            except FreshserviceError as e:
                errors += 1
                console.print(f'  [red]#{t["id"]} failed:[/red] {e}')
                if e.details:
                    for err in e.details:
                        console.print(f'    [dim]{err}[/dim]')
                if errors >= 3 and success == 0:
                    console.print('[red]All updates failing — aborting.[/red]')
                    break

    if errors:
        console.print(f'[green]Updated {success} ticket(s)[/green], [red]{errors} failed[/red]')
    else:
        console.print(f'[green]Updated {success} ticket(s)[/green]')


@cli.command()
@click.option('--ticket-id', type=int, metavar='ID', help='Inspect fields from a specific ticket')
def fields(ticket_id):
    """Show available ticket fields by inspecting a real ticket."""
    client = get_client()
    with console.status('Fetching ticket sample...'):
        try:
            ticket = client.get_ticket(ticket_id) if ticket_id else client.get_ticket_sample()
        except FreshserviceError as e:
            console.print(f'[red]API error:[/red] {e}')
            sys.exit(1)

    if not ticket:
        console.print('[yellow]No tickets found.[/yellow]')
        return

    console.print(f'[dim]Fields from ticket #{ticket.get("id", "?")}:[/dim]\n')

    table = Table(show_header=True, header_style='bold', box=None, pad_edge=False)
    table.add_column('Field', style='cyan', no_wrap=True)
    table.add_column('Value')
    table.add_column('Custom', no_wrap=True)

    custom_fields = ticket.pop('custom_fields', {}) or {}
    skip = {'description', 'description_text'}

    for key, value in sorted(ticket.items()):
        if key in skip:
            continue
        display = str(value) if value is not None else ''
        if len(display) > 80:
            display = display[:77] + '...'
        table.add_row(key, display, '')

    for key, value in sorted(custom_fields.items()):
        display = str(value) if value is not None else ''
        if len(display) > 80:
            display = display[:77] + '...'
        table.add_row(key, display, 'yes')

    console.print(table)


if __name__ == '__main__':
    cli()
