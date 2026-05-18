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
    department_id           BIGINT              NULL,
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
