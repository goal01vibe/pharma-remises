"""Create audit_logs table for comprehensive audit trail

Revision ID: 012
Revises: 011
Create Date: 2025-12-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, INET, UUID

# revision identifiers
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_id', UUID(), server_default=sa.text('gen_random_uuid()'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('user_email', sa.String(255), nullable=True),
        sa.Column('ip_address', INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('old_values', JSONB(), nullable=True),
        sa.Column('new_values', JSONB(), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.Column('status', sa.String(20), server_default='success', nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True)
    )

    # Create indexes for frequent queries
    op.execute("""
        CREATE INDEX idx_audit_created
        ON audit_logs(created_at DESC);
    """)

    op.execute("""
        CREATE INDEX idx_audit_action
        ON audit_logs(action);
    """)

    op.execute("""
        CREATE INDEX idx_audit_resource
        ON audit_logs(resource_type, resource_id);
    """)

    op.execute("""
        CREATE INDEX idx_audit_user
        ON audit_logs(user_email);
    """)

    op.execute("""
        CREATE INDEX idx_audit_status
        ON audit_logs(status);
    """)

    op.execute("""
        CREATE INDEX idx_audit_metadata
        ON audit_logs USING gin(metadata);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_audit_metadata;")
    op.execute("DROP INDEX IF EXISTS idx_audit_status;")
    op.execute("DROP INDEX IF EXISTS idx_audit_user;")
    op.execute("DROP INDEX IF EXISTS idx_audit_resource;")
    op.execute("DROP INDEX IF EXISTS idx_audit_action;")
    op.execute("DROP INDEX IF EXISTS idx_audit_created;")
    op.drop_table('audit_logs')
