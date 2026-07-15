"""Create durable conversations, tickets, and audit events.

Revision ID: 20260713_0001
Revises:
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260713_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_sessions",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("current_service", sa.String(length=64), nullable=True),
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "tenant_id",
            "session_id",
            name="pk_conversation_sessions",
        ),
    )
    op.create_index(
        "ix_conversation_sessions_updated_at",
        "conversation_sessions",
        ["updated_at"],
    )

    op.create_table(
        "tickets",
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("ticket_number", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_session_id", sa.String(length=128), nullable=False),
        sa.Column("source_draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_draft_version", sa.Integer(), nullable=False),
        sa.Column("service_key", sa.String(length=64), nullable=False),
        sa.Column("assigned_department", sa.String(length=64), nullable=False),
        sa.Column("requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "additional_features",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("customer_notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("ticket_id", name="pk_tickets"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_tickets_tenant_id_idempotency_key",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "ticket_number",
            name="uq_tickets_tenant_id_ticket_number",
        ),
    )
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"])
    op.create_index(
        "ix_tickets_source_session_id",
        "tickets",
        ["source_session_id"],
    )
    op.create_index(
        "ix_tickets_tenant_id_status",
        "tickets",
        ["tenant_id", "status"],
    )

    op.create_table(
        "ticket_audit_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.ticket_id"],
            name="fk_ticket_audit_events_ticket_id_tickets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_ticket_audit_events"),
    )
    op.create_index(
        "ix_ticket_audit_events_occurred_at",
        "ticket_audit_events",
        ["occurred_at"],
    )
    op.create_index(
        "ix_ticket_audit_events_ticket_id",
        "ticket_audit_events",
        ["ticket_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ticket_audit_events_ticket_id",
        table_name="ticket_audit_events",
    )
    op.drop_index(
        "ix_ticket_audit_events_occurred_at",
        table_name="ticket_audit_events",
    )
    op.drop_table("ticket_audit_events")

    op.drop_index("ix_tickets_tenant_id_status", table_name="tickets")
    op.drop_index("ix_tickets_source_session_id", table_name="tickets")
    op.drop_index("ix_tickets_created_at", table_name="tickets")
    op.drop_table("tickets")

    op.drop_index(
        "ix_conversation_sessions_updated_at",
        table_name="conversation_sessions",
    )
    op.drop_table("conversation_sessions")