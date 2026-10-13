"""Add Phase 7 mitigation and recovery task tracking.

Revision ID: 20261013_14
Revises: 20261013_13
"""
from alembic import op
import sqlalchemy as sa
revision = '20261013_14'
down_revision = '20261013_13'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('mitigation_action',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scenario_id', sa.Integer(), sa.ForeignKey('scenario.id', ondelete='CASCADE'), nullable=False),
        sa.Column('impact_id', sa.Integer(), sa.ForeignKey('impact.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('title', sa.String(160), nullable=False),
        sa.Column('description', sa.String(1600), nullable=False, server_default=''),
        sa.Column('owner_name', sa.String(120), nullable=False, server_default='Unassigned'),
        sa.Column('priority', sa.String(12), nullable=False, server_default='Medium'),
        sa.Column('status', sa.String(20), nullable=False, server_default='Open'),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completion_note', sa.String(1200), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    for col in ('scenario_id','impact_id','created_by_id','status'):
        op.create_index(f'ix_mitigation_action_{col}', 'mitigation_action', [col])

def downgrade():
    op.drop_table('mitigation_action')
