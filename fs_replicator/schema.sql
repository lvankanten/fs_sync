-- Freshservice Replicator Schema
-- Target database: FS
-- Run via: python replicator.py --setup

IF OBJECT_ID('sync_log', 'U') IS NULL
CREATE TABLE sync_log (
    entity          NVARCHAR(50)        NOT NULL,
    last_synced_at  DATETIMEOFFSET(0)   NULL,
    last_run_at     DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    rows_affected   INT                 NOT NULL DEFAULT 0,
    status          NVARCHAR(20)        NOT NULL,
    error_message   NVARCHAR(MAX)       NULL,
    CONSTRAINT PK_sync_log PRIMARY KEY (entity)
);

IF OBJECT_ID('agents', 'U') IS NULL
CREATE TABLE agents (
    id                                              BIGINT              NOT NULL,
    first_name                                      NVARCHAR(100)       NULL,
    last_name                                       NVARCHAR(100)       NULL,
    email                                           NVARCHAR(200)       NULL,
    job_title                                       NVARCHAR(200)       NULL,
    time_zone                                       NVARCHAR(100)       NULL,
    vip_user                                        BIT                 NULL,
    address                                         NVARCHAR(500)       NULL,
    location_id                                     BIGINT              NULL,
    location_name                                   NVARCHAR(200)       NULL,
    background_information                          NVARCHAR(MAX)       NULL,
    reporting_manager_id                            BIGINT              NULL,
    active                                          BIT                 NULL,
    has_logged_in                                   BIT                 NULL,
    last_active_at                                  DATETIMEOFFSET(0)   NULL,
    last_login_at                                   DATETIMEOFFSET(0)   NULL,
    occasional                                      BIT                 NULL,
    auto_assign_tickets                             BIT                 NULL,
    auto_assign_status_changed_at                   DATETIMEOFFSET(0)   NULL,
    can_see_all_tickets_from_associated_departments BIT                 NULL,
    api_key_enabled                                 BIT                 NULL,
    work_schedule_id                                BIGINT              NULL,
    language                                        NVARCHAR(10)        NULL,
    time_format                                     NVARCHAR(10)        NULL,
    roles_json                                      NVARCHAR(MAX)       NULL,
    member_of_json                                  NVARCHAR(MAX)       NULL,
    observer_of_json                                NVARCHAR(MAX)       NULL,
    member_of_pending_approval_json                 NVARCHAR(MAX)       NULL,
    observer_of_pending_approval_json               NVARCHAR(MAX)       NULL,
    workspace_ids_json                              NVARCHAR(MAX)       NULL,
    department_ids_json                             NVARCHAR(MAX)       NULL,
    workload_configs_json                           NVARCHAR(MAX)       NULL,
    created_at                                      DATETIMEOFFSET(0)   NULL,
    updated_at                                      DATETIMEOFFSET(0)   NULL,
    replicated_at                                   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_agents PRIMARY KEY (id)
);

IF OBJECT_ID('requesters', 'U') IS NULL
CREATE TABLE requesters (
    id                      BIGINT              NOT NULL,
    first_name              NVARCHAR(100)       NULL,
    last_name               NVARCHAR(100)       NULL,
    primary_email           NVARCHAR(200)       NULL,
    job_title               NVARCHAR(200)       NULL,
    time_zone               NVARCHAR(100)       NULL,
    vip_user                BIT                 NULL,
    address                 NVARCHAR(500)       NULL,
    location_id             BIGINT              NULL,
    location_name           NVARCHAR(200)       NULL,
    background_information  NVARCHAR(MAX)       NULL,
    reporting_manager_id    BIGINT              NULL,
    department_ids_json     NVARCHAR(MAX)       NULL,
    can_see_all_tickets_from_associated_departments BIT NULL,
    has_logged_in           BIT                 NULL,
    secondary_emails        NVARCHAR(MAX)       NULL,
    active                  BIT                 NULL,
    created_at              DATETIMEOFFSET(0)   NULL,
    updated_at              DATETIMEOFFSET(0)   NULL,
    replicated_at           DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_requesters PRIMARY KEY (id)
);

IF OBJECT_ID('agent_groups', 'U') IS NULL
CREATE TABLE agent_groups (
    id                  BIGINT              NOT NULL,
    name                NVARCHAR(200)       NULL,
    description         NVARCHAR(MAX)       NULL,
    escalate_to         BIGINT              NULL,
    unassigned_for      NVARCHAR(50)        NULL,
    auto_ticket_assign  BIT                 NULL,
    restricted          BIT                 NULL,
    workspace_id        BIGINT              NULL,
    business_hours_id   BIGINT              NULL,
    approval_required   BIT                 NULL,
    ocs_schedule_id     BIGINT              NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_agent_groups PRIMARY KEY (id)
);

IF OBJECT_ID('agent_group_members', 'U') IS NULL
CREATE TABLE agent_group_members (
    group_id    BIGINT NOT NULL,
    agent_id    BIGINT NOT NULL,
    CONSTRAINT PK_agent_group_members PRIMARY KEY (group_id, agent_id)
);

IF OBJECT_ID('requester_groups', 'U') IS NULL
CREATE TABLE requester_groups (
    id              BIGINT              NOT NULL,
    name            NVARCHAR(200)       NULL,
    description     NVARCHAR(MAX)       NULL,
    created_at      DATETIMEOFFSET(0)   NULL,
    updated_at      DATETIMEOFFSET(0)   NULL,
    replicated_at   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_requester_groups PRIMARY KEY (id)
);

IF OBJECT_ID('requester_group_members', 'U') IS NULL
CREATE TABLE requester_group_members (
    group_id        BIGINT NOT NULL,
    requester_id    BIGINT NOT NULL,
    CONSTRAINT PK_requester_group_members PRIMARY KEY (group_id, requester_id)
);

IF OBJECT_ID('tickets', 'U') IS NULL
CREATE TABLE tickets (
    id                  BIGINT              NOT NULL,
    display_id          INT                 NULL,
    subject             NVARCHAR(500)       NULL,
    description_text    NVARCHAR(MAX)       NULL,
    status              SMALLINT            NULL,
    priority            SMALLINT            NULL,
    urgency             SMALLINT            NULL,
    impact              SMALLINT            NULL,
    source              SMALLINT            NULL,
    ticket_type         NVARCHAR(100)       NULL,
    category            NVARCHAR(200)       NULL,
    sub_category        NVARCHAR(200)       NULL,
    item_category       NVARCHAR(200)       NULL,
    tags                NVARCHAR(500)       NULL,
    department_id       BIGINT              NULL,
    responder_id        BIGINT              NULL,
    group_id            BIGINT              NULL,
    requester_id        BIGINT              NULL,
    workspace_id        BIGINT              NULL,
    fr_escalated        BIT                 NULL,
    is_escalated        BIT                 NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    due_by              DATETIMEOFFSET(0)   NULL,
    fr_due_by           DATETIMEOFFSET(0)   NULL,
    resolved_at         DATETIMEOFFSET(0)   NULL,
    closed_at           DATETIMEOFFSET(0)   NULL,
    resolution_notes    NVARCHAR(MAX)       NULL,
    custom_fields_json  NVARCHAR(MAX)       NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_tickets PRIMARY KEY (id)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_tickets_updated_at' AND object_id = OBJECT_ID('tickets'))
    CREATE INDEX IX_tickets_updated_at ON tickets (updated_at);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_tickets_status' AND object_id = OBJECT_ID('tickets'))
    CREATE INDEX IX_tickets_status ON tickets (status);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_tickets_requester_id' AND object_id = OBJECT_ID('tickets'))
    CREATE INDEX IX_tickets_requester_id ON tickets (requester_id);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_tickets_responder_id' AND object_id = OBJECT_ID('tickets'))
    CREATE INDEX IX_tickets_responder_id ON tickets (responder_id);

IF OBJECT_ID('conversations', 'U') IS NULL
CREATE TABLE conversations (
    id              BIGINT              NOT NULL,
    ticket_id       BIGINT              NOT NULL,
    body_text       NVARCHAR(MAX)       NULL,
    source          SMALLINT            NULL,
    is_private      BIT                 NULL,
    incoming        BIT                 NULL,
    user_id         BIGINT              NULL,
    created_at      DATETIMEOFFSET(0)   NULL,
    updated_at      DATETIMEOFFSET(0)   NULL,
    replicated_at   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_conversations PRIMARY KEY (id),
    CONSTRAINT FK_conversations_tickets FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_conversations_ticket_id' AND object_id = OBJECT_ID('conversations'))
    CREATE INDEX IX_conversations_ticket_id ON conversations (ticket_id);

-- Activity audit log per ticket. API returns no IDs on individual activities,
-- so we synthesize a surrogate PK and DELETE+INSERT per ticket on each sync.
IF OBJECT_ID('ticket_activities', 'U') IS NULL
CREATE TABLE ticket_activities (
    id              BIGINT              IDENTITY(1,1) NOT NULL,
    ticket_id       BIGINT              NOT NULL,
    actor_id        BIGINT              NULL,
    actor_name      NVARCHAR(200)       NULL,
    actor_is_agent  BIT                 NULL,
    content         NVARCHAR(MAX)       NULL,
    sub_contents    NVARCHAR(MAX)       NULL,
    created_at      DATETIMEOFFSET(0)   NULL,
    replicated_at   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_ticket_activities PRIMARY KEY (id),
    CONSTRAINT FK_ticket_activities_tickets FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ticket_activities_ticket_id' AND object_id = OBJECT_ID('ticket_activities'))
    CREATE INDEX IX_ticket_activities_ticket_id ON ticket_activities (ticket_id);

IF OBJECT_ID('ticket_tasks', 'U') IS NULL
CREATE TABLE ticket_tasks (
    id                  BIGINT              NOT NULL,
    ticket_id           BIGINT              NOT NULL,
    agent_id            BIGINT              NULL,
    status              SMALLINT            NULL,
    due_date            DATETIMEOFFSET(0)   NULL,
    notify_before       INT                 NULL,
    title               NVARCHAR(500)       NULL,
    description         NVARCHAR(MAX)       NULL,
    planned_start_date  DATETIMEOFFSET(0)   NULL,
    planned_end_date    DATETIMEOFFSET(0)   NULL,
    planned_effort      NVARCHAR(50)        NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    closed_at           DATETIMEOFFSET(0)   NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_ticket_tasks PRIMARY KEY (id),
    CONSTRAINT FK_ticket_tasks_tickets FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ticket_tasks_ticket_id' AND object_id = OBJECT_ID('ticket_tasks'))
    CREATE INDEX IX_ticket_tasks_ticket_id ON ticket_tasks (ticket_id);

IF OBJECT_ID('ticket_time_entries', 'U') IS NULL
CREATE TABLE ticket_time_entries (
    id              BIGINT              NOT NULL,
    ticket_id       BIGINT              NOT NULL,
    agent_id        BIGINT              NULL,
    time_spent      NVARCHAR(20)        NULL,
    billable        BIT                 NULL,
    note            NVARCHAR(MAX)       NULL,
    start_time      DATETIMEOFFSET(0)   NULL,
    timer_running   BIT                 NULL,
    created_at      DATETIMEOFFSET(0)   NULL,
    updated_at      DATETIMEOFFSET(0)   NULL,
    replicated_at   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_ticket_time_entries PRIMARY KEY (id),
    CONSTRAINT FK_ticket_time_entries_tickets FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_ticket_time_entries_ticket_id' AND object_id = OBJECT_ID('ticket_time_entries'))
    CREATE INDEX IX_ticket_time_entries_ticket_id ON ticket_time_entries (ticket_id);

IF OBJECT_ID('departments', 'U') IS NULL
CREATE TABLE departments (
    id              BIGINT              NOT NULL,
    name            NVARCHAR(200)       NULL,
    description     NVARCHAR(MAX)       NULL,
    head_user_id    BIGINT              NULL,
    prime_user_id   BIGINT              NULL,
    domains         NVARCHAR(MAX)       NULL,
    created_at      DATETIMEOFFSET(0)   NULL,
    updated_at      DATETIMEOFFSET(0)   NULL,
    replicated_at   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_departments PRIMARY KEY (id)
);

IF OBJECT_ID('locations', 'U') IS NULL
CREATE TABLE locations (
    id                  BIGINT              NOT NULL,
    name                NVARCHAR(200)       NULL,
    parent_location_id  BIGINT              NULL,
    contact_name        NVARCHAR(200)       NULL,
    email               NVARCHAR(200)       NULL,
    phone               NVARCHAR(50)        NULL,
    address_line1       NVARCHAR(500)       NULL,
    city                NVARCHAR(200)       NULL,
    state               NVARCHAR(200)       NULL,
    zip_code            NVARCHAR(50)        NULL,
    country             NVARCHAR(200)       NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_locations PRIMARY KEY (id)
);

IF OBJECT_ID('sla_policies', 'U') IS NULL
CREATE TABLE sla_policies (
    id                  BIGINT              NOT NULL,
    name                NVARCHAR(200)       NULL,
    description         NVARCHAR(MAX)       NULL,
    is_default          BIT                 NULL,
    active              BIT                 NULL,
    deleted             BIT                 NULL,
    position            INT                 NULL,
    parent_entity       NVARCHAR(50)        NULL,
    workspace_id        BIGINT              NULL,
    applicable_to_json  NVARCHAR(MAX)       NULL,
    sla_targets_json    NVARCHAR(MAX)       NULL,
    escalation_json     NVARCHAR(MAX)       NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_sla_policies PRIMARY KEY (id)
);

-- Migrate sla_policies created before the sla_targets fix:
-- the API field is sla_targets (plural, an array), not sla_target; also capture parent_entity/workspace_id/deleted.
IF EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'sla_policies' AND COLUMN_NAME = 'sla_target_json')
    EXEC sp_rename 'sla_policies.sla_target_json', 'sla_targets_json', 'COLUMN'

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'sla_policies' AND COLUMN_NAME = 'parent_entity')
    ALTER TABLE sla_policies ADD parent_entity NVARCHAR(50) NULL, workspace_id BIGINT NULL, deleted BIT NULL

IF OBJECT_ID('problems', 'U') IS NULL
CREATE TABLE problems (
    id                  BIGINT              NOT NULL,
    display_id          INT                 NULL,
    subject             NVARCHAR(500)       NULL,
    description_text    NVARCHAR(MAX)       NULL,
    status              SMALLINT            NULL,
    priority            SMALLINT            NULL,
    impact              SMALLINT            NULL,
    category            NVARCHAR(200)       NULL,
    sub_category        NVARCHAR(200)       NULL,
    item_category       NVARCHAR(200)       NULL,
    department_id       BIGINT              NULL,
    agent_id            BIGINT              NULL,
    group_id            BIGINT              NULL,
    requester_id        BIGINT              NULL,
    workspace_id        BIGINT              NULL,
    due_by              DATETIMEOFFSET(0)   NULL,
    planned_start_date  DATETIMEOFFSET(0)   NULL,
    planned_end_date    DATETIMEOFFSET(0)   NULL,
    planned_effort      NVARCHAR(50)        NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    closed_at           DATETIMEOFFSET(0)   NULL,
    custom_fields_json  NVARCHAR(MAX)       NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_problems PRIMARY KEY (id)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_problems_updated_at' AND object_id = OBJECT_ID('problems'))
    CREATE INDEX IX_problems_updated_at ON problems (updated_at);

IF OBJECT_ID('problem_conversations', 'U') IS NULL
CREATE TABLE problem_conversations (
    id              BIGINT              NOT NULL,
    problem_id      BIGINT              NOT NULL,
    body_text       NVARCHAR(MAX)       NULL,
    source          SMALLINT            NULL,
    is_private      BIT                 NULL,
    incoming        BIT                 NULL,
    user_id         BIGINT              NULL,
    created_at      DATETIMEOFFSET(0)   NULL,
    updated_at      DATETIMEOFFSET(0)   NULL,
    replicated_at   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_problem_conversations PRIMARY KEY (id),
    CONSTRAINT FK_problem_conversations_problems FOREIGN KEY (problem_id) REFERENCES problems(id)
);

IF OBJECT_ID('problem_tasks', 'U') IS NULL
CREATE TABLE problem_tasks (
    id                  BIGINT              NOT NULL,
    problem_id          BIGINT              NOT NULL,
    agent_id            BIGINT              NULL,
    status              SMALLINT            NULL,
    due_date            DATETIMEOFFSET(0)   NULL,
    notify_before       INT                 NULL,
    title               NVARCHAR(500)       NULL,
    description         NVARCHAR(MAX)       NULL,
    planned_start_date  DATETIMEOFFSET(0)   NULL,
    planned_end_date    DATETIMEOFFSET(0)   NULL,
    planned_effort      NVARCHAR(50)        NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    closed_at           DATETIMEOFFSET(0)   NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_problem_tasks PRIMARY KEY (id),
    CONSTRAINT FK_problem_tasks_problems FOREIGN KEY (problem_id) REFERENCES problems(id)
);

IF OBJECT_ID('problem_time_entries', 'U') IS NULL
CREATE TABLE problem_time_entries (
    id              BIGINT              NOT NULL,
    problem_id      BIGINT              NOT NULL,
    agent_id        BIGINT              NULL,
    time_spent      NVARCHAR(20)        NULL,
    billable        BIT                 NULL,
    note            NVARCHAR(MAX)       NULL,
    start_time      DATETIMEOFFSET(0)   NULL,
    timer_running   BIT                 NULL,
    created_at      DATETIMEOFFSET(0)   NULL,
    updated_at      DATETIMEOFFSET(0)   NULL,
    replicated_at   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_problem_time_entries PRIMARY KEY (id),
    CONSTRAINT FK_problem_time_entries_problems FOREIGN KEY (problem_id) REFERENCES problems(id)
);

IF OBJECT_ID('changes', 'U') IS NULL
CREATE TABLE changes (
    id                  BIGINT              NOT NULL,
    display_id          INT                 NULL,
    subject             NVARCHAR(500)       NULL,
    description_text    NVARCHAR(MAX)       NULL,
    status              SMALLINT            NULL,
    priority            SMALLINT            NULL,
    impact              SMALLINT            NULL,
    risk                SMALLINT            NULL,
    change_type         SMALLINT            NULL,
    approval_status     SMALLINT            NULL,
    category            NVARCHAR(200)       NULL,
    sub_category        NVARCHAR(200)       NULL,
    item_category       NVARCHAR(200)       NULL,
    department_id       BIGINT              NULL,
    agent_id            BIGINT              NULL,
    group_id            BIGINT              NULL,
    requester_id        BIGINT              NULL,
    workspace_id        BIGINT              NULL,
    planned_start_date  DATETIMEOFFSET(0)   NULL,
    planned_end_date    DATETIMEOFFSET(0)   NULL,
    planned_effort      NVARCHAR(50)        NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    custom_fields_json  NVARCHAR(MAX)       NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_changes PRIMARY KEY (id)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_changes_updated_at' AND object_id = OBJECT_ID('changes'))
    CREATE INDEX IX_changes_updated_at ON changes (updated_at);

IF OBJECT_ID('change_conversations', 'U') IS NULL
CREATE TABLE change_conversations (
    id              BIGINT              NOT NULL,
    change_id       BIGINT              NOT NULL,
    body_text       NVARCHAR(MAX)       NULL,
    source          SMALLINT            NULL,
    is_private      BIT                 NULL,
    incoming        BIT                 NULL,
    user_id         BIGINT              NULL,
    created_at      DATETIMEOFFSET(0)   NULL,
    updated_at      DATETIMEOFFSET(0)   NULL,
    replicated_at   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_change_conversations PRIMARY KEY (id),
    CONSTRAINT FK_change_conversations_changes FOREIGN KEY (change_id) REFERENCES changes(id)
);

IF OBJECT_ID('change_tasks', 'U') IS NULL
CREATE TABLE change_tasks (
    id                  BIGINT              NOT NULL,
    change_id           BIGINT              NOT NULL,
    agent_id            BIGINT              NULL,
    status              SMALLINT            NULL,
    due_date            DATETIMEOFFSET(0)   NULL,
    notify_before       INT                 NULL,
    title               NVARCHAR(500)       NULL,
    description         NVARCHAR(MAX)       NULL,
    planned_start_date  DATETIMEOFFSET(0)   NULL,
    planned_end_date    DATETIMEOFFSET(0)   NULL,
    planned_effort      NVARCHAR(50)        NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    closed_at           DATETIMEOFFSET(0)   NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_change_tasks PRIMARY KEY (id),
    CONSTRAINT FK_change_tasks_changes FOREIGN KEY (change_id) REFERENCES changes(id)
);

IF OBJECT_ID('change_time_entries', 'U') IS NULL
CREATE TABLE change_time_entries (
    id              BIGINT              NOT NULL,
    change_id       BIGINT              NOT NULL,
    agent_id        BIGINT              NULL,
    time_spent      NVARCHAR(20)        NULL,
    billable        BIT                 NULL,
    note            NVARCHAR(MAX)       NULL,
    start_time      DATETIMEOFFSET(0)   NULL,
    timer_running   BIT                 NULL,
    created_at      DATETIMEOFFSET(0)   NULL,
    updated_at      DATETIMEOFFSET(0)   NULL,
    replicated_at   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_change_time_entries PRIMARY KEY (id),
    CONSTRAINT FK_change_time_entries_changes FOREIGN KEY (change_id) REFERENCES changes(id)
);

IF OBJECT_ID('releases', 'U') IS NULL
CREATE TABLE releases (
    id                  BIGINT              NOT NULL,
    display_id          INT                 NULL,
    subject             NVARCHAR(500)       NULL,
    description_text    NVARCHAR(MAX)       NULL,
    status              SMALLINT            NULL,
    priority            SMALLINT            NULL,
    impact              SMALLINT            NULL,
    release_type        SMALLINT            NULL,
    category            NVARCHAR(200)       NULL,
    sub_category        NVARCHAR(200)       NULL,
    item_category       NVARCHAR(200)       NULL,
    department_id       BIGINT              NULL,
    agent_id            BIGINT              NULL,
    group_id            BIGINT              NULL,
    workspace_id        BIGINT              NULL,
    planned_start_date  DATETIMEOFFSET(0)   NULL,
    planned_end_date    DATETIMEOFFSET(0)   NULL,
    planned_effort      NVARCHAR(50)        NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    custom_fields_json  NVARCHAR(MAX)       NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_releases PRIMARY KEY (id)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_releases_updated_at' AND object_id = OBJECT_ID('releases'))
    CREATE INDEX IX_releases_updated_at ON releases (updated_at);

IF OBJECT_ID('release_conversations', 'U') IS NULL
CREATE TABLE release_conversations (
    id              BIGINT              NOT NULL,
    release_id      BIGINT              NOT NULL,
    body_text       NVARCHAR(MAX)       NULL,
    source          SMALLINT            NULL,
    is_private      BIT                 NULL,
    incoming        BIT                 NULL,
    user_id         BIGINT              NULL,
    created_at      DATETIMEOFFSET(0)   NULL,
    updated_at      DATETIMEOFFSET(0)   NULL,
    replicated_at   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_release_conversations PRIMARY KEY (id),
    CONSTRAINT FK_release_conversations_releases FOREIGN KEY (release_id) REFERENCES releases(id)
);

IF OBJECT_ID('release_tasks', 'U') IS NULL
CREATE TABLE release_tasks (
    id                  BIGINT              NOT NULL,
    release_id          BIGINT              NOT NULL,
    agent_id            BIGINT              NULL,
    status              SMALLINT            NULL,
    due_date            DATETIMEOFFSET(0)   NULL,
    notify_before       INT                 NULL,
    title               NVARCHAR(500)       NULL,
    description         NVARCHAR(MAX)       NULL,
    planned_start_date  DATETIMEOFFSET(0)   NULL,
    planned_end_date    DATETIMEOFFSET(0)   NULL,
    planned_effort      NVARCHAR(50)        NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    closed_at           DATETIMEOFFSET(0)   NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_release_tasks PRIMARY KEY (id),
    CONSTRAINT FK_release_tasks_releases FOREIGN KEY (release_id) REFERENCES releases(id)
);

IF OBJECT_ID('release_time_entries', 'U') IS NULL
CREATE TABLE release_time_entries (
    id              BIGINT              NOT NULL,
    release_id      BIGINT              NOT NULL,
    agent_id        BIGINT              NULL,
    time_spent      NVARCHAR(20)        NULL,
    billable        BIT                 NULL,
    note            NVARCHAR(MAX)       NULL,
    start_time      DATETIMEOFFSET(0)   NULL,
    timer_running   BIT                 NULL,
    created_at      DATETIMEOFFSET(0)   NULL,
    updated_at      DATETIMEOFFSET(0)   NULL,
    replicated_at   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_release_time_entries PRIMARY KEY (id),
    CONSTRAINT FK_release_time_entries_releases FOREIGN KEY (release_id) REFERENCES releases(id)
);

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'releases' AND COLUMN_NAME = 'impact')
    ALTER TABLE releases ADD impact SMALLINT NULL

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'ticket_tasks' AND COLUMN_NAME = 'planned_start_date')
    ALTER TABLE ticket_tasks ADD planned_start_date DATETIMEOFFSET(0) NULL, planned_end_date DATETIMEOFFSET(0) NULL, planned_effort NVARCHAR(50) NULL

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'problem_tasks' AND COLUMN_NAME = 'planned_start_date')
    ALTER TABLE problem_tasks ADD planned_start_date DATETIMEOFFSET(0) NULL, planned_end_date DATETIMEOFFSET(0) NULL, planned_effort NVARCHAR(50) NULL

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'change_tasks' AND COLUMN_NAME = 'planned_start_date')
    ALTER TABLE change_tasks ADD planned_start_date DATETIMEOFFSET(0) NULL, planned_end_date DATETIMEOFFSET(0) NULL, planned_effort NVARCHAR(50) NULL

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'release_tasks' AND COLUMN_NAME = 'planned_start_date')
    ALTER TABLE release_tasks ADD planned_start_date DATETIMEOFFSET(0) NULL, planned_end_date DATETIMEOFFSET(0) NULL, planned_effort NVARCHAR(50) NULL

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'sync_log' AND COLUMN_NAME = 'cursor_id')
    ALTER TABLE sync_log ADD cursor_id BIGINT NULL

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'sync_log' AND COLUMN_NAME = 'backfill_completed_at')
    ALTER TABLE sync_log ADD backfill_completed_at DATETIMEOFFSET(0) NULL

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'agents' AND COLUMN_NAME = 'location_id')
    ALTER TABLE agents ADD location_id BIGINT NULL

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'requesters' AND COLUMN_NAME = 'location_id')
    ALTER TABLE requesters ADD location_id BIGINT NULL

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'agent_groups' AND COLUMN_NAME = 'auto_ticket_assign')
    ALTER TABLE agent_groups ADD auto_ticket_assign BIT NULL, restricted BIT NULL, workspace_id BIGINT NULL, business_hours_id BIGINT NULL, approval_required BIT NULL, ocs_schedule_id BIGINT NULL

IF OBJECT_ID('ticket_workload', 'U') IS NULL
CREATE TABLE ticket_workload (
    ticket_id           BIGINT              NOT NULL,
    planned_effort      NVARCHAR(50)        NULL,
    planned_start_date  DATETIMEOFFSET(0)   NULL,
    planned_end_date    DATETIMEOFFSET(0)   NULL,
    last_checked_at     DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_ticket_workload PRIMARY KEY (ticket_id),
    CONSTRAINT FK_ticket_workload_tickets FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);

IF EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'tickets' AND COLUMN_NAME = 'planned_effort')
    ALTER TABLE tickets DROP COLUMN planned_effort, planned_start_date, planned_end_date

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'requesters' AND COLUMN_NAME = 'can_see_all_tickets_from_associated_departments')
    ALTER TABLE requesters ADD
        can_see_all_tickets_from_associated_departments BIT NULL,
        has_logged_in BIT NULL,
        secondary_emails NVARCHAR(MAX) NULL

-- Back out the short-lived soft-delete column. Decision (2026-06-20): hard-delete in
-- the replica so consumers don't need an `AND deleted=0` filter. Removes already-flagged
-- phantom rows + their child rows, then drops the column and its default constraint.
IF EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'tickets' AND COLUMN_NAME = 'deleted')
BEGIN
    DELETE FROM ticket_activities WHERE ticket_id IN (SELECT id FROM tickets WHERE deleted = 1);
    DELETE FROM ticket_time_entries WHERE ticket_id IN (SELECT id FROM tickets WHERE deleted = 1);
    DELETE FROM ticket_tasks WHERE ticket_id IN (SELECT id FROM tickets WHERE deleted = 1);
    DELETE FROM conversations WHERE ticket_id IN (SELECT id FROM tickets WHERE deleted = 1);
    DELETE FROM ticket_workload WHERE ticket_id IN (SELECT id FROM tickets WHERE deleted = 1);
    DELETE FROM tickets WHERE deleted = 1;
    ALTER TABLE tickets DROP CONSTRAINT DF_tickets_deleted;
    ALTER TABLE tickets DROP COLUMN deleted;
END

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'agents' AND COLUMN_NAME = 'has_logged_in')
    ALTER TABLE agents ADD
        has_logged_in BIT NULL,
        last_active_at DATETIMEOFFSET(0) NULL,
        last_login_at DATETIMEOFFSET(0) NULL,
        occasional BIT NULL,
        auto_assign_tickets BIT NULL,
        auto_assign_status_changed_at DATETIMEOFFSET(0) NULL,
        can_see_all_tickets_from_associated_departments BIT NULL,
        api_key_enabled BIT NULL,
        work_schedule_id BIGINT NULL,
        [language] NVARCHAR(10) NULL,
        time_format NVARCHAR(10) NULL,
        roles_json NVARCHAR(MAX) NULL,
        member_of_json NVARCHAR(MAX) NULL,
        observer_of_json NVARCHAR(MAX) NULL,
        member_of_pending_approval_json NVARCHAR(MAX) NULL,
        observer_of_pending_approval_json NVARCHAR(MAX) NULL,
        workspace_ids_json NVARCHAR(MAX) NULL,
        department_ids_json NVARCHAR(MAX) NULL,
        workload_configs_json NVARCHAR(MAX) NULL

-- ─── NewGen Projects (pm/ namespace) ──────────────────────────────────────────
-- API: GET /api/v2/pm/projects, /api/v2/pm/projects/{id}/tasks, /api/v2/pm/projects/{id}/memberships
-- Project status_id values (per UI): 1=Yet to start, 2=In progress, 3=Completed (+ On hold/Cancelled)
-- Project priority_id values (per UI): 1=High, 2=Medium, 3=Low
-- Task status_id is a separate per-template-defined enum (large IDs like 1000143449); no metadata endpoint, store the ID as-is.

IF OBJECT_ID('projects', 'U') IS NULL
CREATE TABLE projects (
    id                  BIGINT              NOT NULL,
    name                NVARCHAR(500)       NULL,
    [key]               NVARCHAR(50)        NULL,
    description         NVARCHAR(MAX)       NULL,
    status_id           BIGINT              NULL,
    priority_id         BIGINT              NULL,
    sprint_duration     INT                 NULL,
    project_type        SMALLINT            NULL,
    start_date          DATE                NULL,
    end_date            DATE                NULL,
    archived            BIT                 NULL,
    visibility          SMALLINT            NULL,
    manager_id          BIGINT              NULL,
    custom_fields_json  NVARCHAR(MAX)       NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_projects PRIMARY KEY (id)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_projects_updated_at' AND object_id = OBJECT_ID('projects'))
    CREATE INDEX IX_projects_updated_at ON projects (updated_at);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_projects_manager_id' AND object_id = OBJECT_ID('projects'))
    CREATE INDEX IX_projects_manager_id ON projects (manager_id);

IF OBJECT_ID('project_tasks', 'U') IS NULL
CREATE TABLE project_tasks (
    id                  BIGINT              NOT NULL,
    project_id          BIGINT              NOT NULL,
    title               NVARCHAR(500)       NULL,
    description         NVARCHAR(MAX)       NULL,
    status_id           BIGINT              NULL,
    priority_id         BIGINT              NULL,
    type_id             BIGINT              NULL,
    display_key         NVARCHAR(100)       NULL,
    reporter_id         BIGINT              NULL,
    assignee_id         BIGINT              NULL,
    planned_start_date  DATETIMEOFFSET(0)   NULL,
    planned_end_date    DATETIMEOFFSET(0)   NULL,
    planned_effort      NVARCHAR(50)        NULL,
    planned_duration    NVARCHAR(50)        NULL,
    version_id          BIGINT              NULL,
    parent_id           BIGINT              NULL,
    story_points        INT                 NULL,
    sprint_id           BIGINT              NULL,
    custom_fields_json  NVARCHAR(MAX)       NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_project_tasks PRIMARY KEY (id),
    CONSTRAINT FK_project_tasks_projects FOREIGN KEY (project_id) REFERENCES projects(id)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_project_tasks_project_id' AND object_id = OBJECT_ID('project_tasks'))
    CREATE INDEX IX_project_tasks_project_id ON project_tasks (project_id);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_project_tasks_assignee_id' AND object_id = OBJECT_ID('project_tasks'))
    CREATE INDEX IX_project_tasks_assignee_id ON project_tasks (assignee_id);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_project_tasks_updated_at' AND object_id = OBJECT_ID('project_tasks'))
    CREATE INDEX IX_project_tasks_updated_at ON project_tasks (updated_at);

IF OBJECT_ID('project_members', 'U') IS NULL
CREATE TABLE project_members (
    id                  BIGINT              NOT NULL,
    project_id          BIGINT              NOT NULL,
    user_id             BIGINT              NULL,
    access_type         SMALLINT            NULL,
    manage_settings     BIT                 NULL,
    project_manager     BIT                 NULL,
    created_at          DATETIMEOFFSET(0)   NULL,
    updated_at          DATETIMEOFFSET(0)   NULL,
    replicated_at       DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_project_members PRIMARY KEY (id),
    CONSTRAINT FK_project_members_projects FOREIGN KEY (project_id) REFERENCES projects(id)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_project_members_project_id' AND object_id = OBJECT_ID('project_members'))
    CREATE INDEX IX_project_members_project_id ON project_members (project_id);

-- Agent roles lookup. Resolves the role_id values embedded in agents.roles_json
-- (which only carry role_id + assignment_scope) to human-readable names.
-- Reference entity: small dataset, full reload every run. `default` is a SQL
-- reserved word so the API's `default` flag is stored as is_default (cf. sla_policies).
IF OBJECT_ID('roles', 'U') IS NULL
CREATE TABLE roles (
    id              BIGINT              NOT NULL,
    name            NVARCHAR(200)       NULL,
    description     NVARCHAR(MAX)       NULL,
    is_default      BIT                 NULL,
    role_type       SMALLINT            NULL,
    scopes_json     NVARCHAR(MAX)       NULL,
    created_at      DATETIMEOFFSET(0)   NULL,
    updated_at      DATETIMEOFFSET(0)   NULL,
    replicated_at   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT PK_roles PRIMARY KEY (id)
);
