"""Add Phase 1 campus activities, resources, dependencies and constraints.

Revision ID: 20261013_10
Revises: 20261012_09
"""
from alembic import op
import sqlalchemy as sa

revision = '20261013_10'
down_revision = '20261012_09'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('campus_activity',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(32), nullable=False),
        sa.Column('name', sa.String(140), nullable=False),
        sa.Column('activity_type', sa.String(32), nullable=False, server_default='Class'),
        sa.Column('location', sa.String(120), nullable=False, server_default=''),
        sa.Column('expected_attendance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('criticality', sa.String(16), nullable=False, server_default='Medium'),
        sa.Column('status', sa.String(20), nullable=False, server_default='Scheduled'),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_campus_activity_code', 'campus_activity', ['code'], unique=True)
    op.create_index('ix_campus_activity_name', 'campus_activity', ['name'])
    op.create_table('campus_resource',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(32), nullable=False),
        sa.Column('name', sa.String(140), nullable=False),
        sa.Column('resource_type', sa.String(32), nullable=False, server_default='Room'),
        sa.Column('location', sa.String(120), nullable=False, server_default=''),
        sa.Column('capacity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='Available'),
        sa.Column('notes', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_campus_resource_code', 'campus_resource', ['code'], unique=True)
    op.create_index('ix_campus_resource_name', 'campus_resource', ['name'])
    op.create_table('activity_dependency',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source_activity_id', sa.Integer(), sa.ForeignKey('campus_activity.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_resource_id', sa.Integer(), sa.ForeignKey('campus_resource.id', ondelete='CASCADE'), nullable=True),
        sa.Column('target_activity_id', sa.Integer(), sa.ForeignKey('campus_activity.id', ondelete='CASCADE'), nullable=True),
        sa.Column('dependency_type', sa.String(24), nullable=False, server_default='requires'),
        sa.Column('importance', sa.String(16), nullable=False, server_default='Required'),
        sa.Column('notes', sa.String(500), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('(target_resource_id IS NOT NULL AND target_activity_id IS NULL) OR (target_resource_id IS NULL AND target_activity_id IS NOT NULL)', name='ck_activity_dependency_one_target'),
        sa.UniqueConstraint('source_activity_id', 'target_resource_id', 'target_activity_id', name='uq_activity_dependency_target'))
    op.create_index('ix_activity_dependency_source_activity_id', 'activity_dependency', ['source_activity_id'])
    op.create_index('ix_activity_dependency_target_resource_id', 'activity_dependency', ['target_resource_id'])
    op.create_index('ix_activity_dependency_target_activity_id', 'activity_dependency', ['target_activity_id'])
    op.create_table('resource_constraint',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('resource_id', sa.Integer(), sa.ForeignKey('campus_resource.id', ondelete='CASCADE'), nullable=False),
        sa.Column('constraint_type', sa.String(32), nullable=False),
        sa.Column('operator', sa.String(12), nullable=False, server_default='<='),
        sa.Column('limit_value', sa.String(120), nullable=False),
        sa.Column('unit', sa.String(24), nullable=False, server_default=''),
        sa.Column('is_hard_constraint', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('notes', sa.String(500), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_resource_constraint_resource_id', 'resource_constraint', ['resource_id'])


def downgrade():
    op.drop_table('resource_constraint')
    op.drop_table('activity_dependency')
    op.drop_table('campus_resource')
    op.drop_table('campus_activity')
