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
    id                      BIGINT              NOT NULL,
    first_name              NVARCHAR(100)       NULL,
    last_name               NVARCHAR(100)       NULL,
    email                   NVARCHAR(200)       NULL,
    job_title               NVARCHAR(200)       NULL,
    time_zone               NVARCHAR(100)       NULL,
    vip_user                BIT                 NULL,
    address                 NVARCHAR(500)       NULL,
    location_name           NVARCHAR(200)       NULL,
    background_information  NVARCHAR(MAX)       NULL,
    reporting_manager_id    BIGINT              NULL,
    active                  BIT                 NULL,
    created_at              DATETIMEOFFSET(0)   NULL,
    updated_at              DATETIMEOFFSET(0)   NULL,
    replicated_at           DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
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
    id              BIGINT              NOT NULL,
    name            NVARCHAR(200)       NULL,
    description     NVARCHAR(MAX)       NULL,
    escalate_to     BIGINT              NULL,
    unassigned_for  NVARCHAR(50)        NULL,
    created_at      DATETIMEOFFSET(0)   NULL,
    updated_at      DATETIMEOFFSET(0)   NULL,
    replicated_at   DATETIMEOFFSET(0)   NOT NULL DEFAULT SYSDATETIMEOFFSET(),
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
    planned_start_date  DATETIMEOFFSET(0)   NULL,
    planned_end_date    DATETIMEOFFSET(0)   NULL,
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
