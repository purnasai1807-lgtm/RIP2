"""Add time-aware evidence and uncertainty tracking to decisions.

Revision ID: 20261013_13
Revises: 20261013_12
"""
from alembic import op
import sqlalchemy as sa

revision = '20261013_13'
down_revision = '20261013_12'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scenario_evidence',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scenario_id', sa.Integer(), sa.ForeignKey('scenario.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('label', sa.String(length=140), nullable=False),
        sa.Column('source_type', sa.String(length=32), nullable=False, server_default='Manual'),
        sa.Column('source_ref', sa.String(length=240), nullable=False, server_default=''),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='Unverified'),
        sa.Column('confidence', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.String(length=1200), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    for col in ('scenario_id', 'created_by_id', 'status'):
        op.create_index(f'ix_scenario_evidence_{col}', 'scenario_evidence', [col])


def downgrade():
    op.drop_table('scenario_evidence')
