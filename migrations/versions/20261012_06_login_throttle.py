"""Add persistent, privacy-preserving login throttling records.

Revision ID: 20261012_06
Revises: 20261012_05
"""
from alembic import op
import sqlalchemy as sa

revision = '20261012_06'
down_revision = '20261012_05'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'login_attempt' not in inspector.get_table_names():
        op.create_table(
            'login_attempt',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('email_digest', sa.String(length=64), nullable=False),
            sa.Column('ip_digest', sa.String(length=64), nullable=False),
            sa.Column('succeeded', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('attempted_at', sa.DateTime(timezone=True), nullable=False),
        )
    indexes = {index['name'] for index in sa.inspect(bind).get_indexes('login_attempt')}
    if 'ix_login_attempt_email_digest' not in indexes:
        op.create_index('ix_login_attempt_email_digest', 'login_attempt', ['email_digest'])
    if 'ix_login_attempt_ip_digest' not in indexes:
        op.create_index('ix_login_attempt_ip_digest', 'login_attempt', ['ip_digest'])
    if 'ix_login_attempt_attempted_at' not in indexes:
        op.create_index('ix_login_attempt_attempted_at', 'login_attempt', ['attempted_at'])


def downgrade():
    # Keep throttling history during rollback; an operator can remove it explicitly if needed.
    pass
