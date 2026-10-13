"""Add incident reporting and append-only incident update history.

Revision ID: 20261014_11
Revises: 20261013_10
"""
from alembic import op
import sqlalchemy as sa

revision = '20261013_11'
down_revision = '20261013_10'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('campus_incident',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('incident_code', sa.String(24), nullable=False),
        sa.Column('title', sa.String(160), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('incident_type', sa.String(32), nullable=False, server_default='Other'),
        sa.Column('severity', sa.String(16), nullable=False, server_default='Medium'),
        sa.Column('status', sa.String(20), nullable=False, server_default='Reported'),
        sa.Column('location', sa.String(160), nullable=False, server_default=''),
        sa.Column('resource_id', sa.Integer(), sa.ForeignKey('campus_resource.id', ondelete='SET NULL'), nullable=True),
        sa.Column('activity_id', sa.Integer(), sa.ForeignKey('campus_activity.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reported_by_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('reported_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    for col in ('incident_code','title','incident_type','severity','status','resource_id','activity_id','reported_by_id','reported_at','started_at','resolved_at','last_updated_at'):
        op.create_index(f'ix_campus_incident_{col}', 'campus_incident', [col], unique=(col == 'incident_code'))
    op.create_table('incident_update',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('incident_id', sa.Integer(), sa.ForeignKey('campus_incident.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('update_type', sa.String(24), nullable=False, server_default='Note'),
        sa.Column('previous_status', sa.String(20), nullable=True),
        sa.Column('new_status', sa.String(20), nullable=True),
        sa.Column('previous_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('new_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('note', sa.String(2000), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    for col in ('incident_id','user_id','created_at'):
        op.create_index(f'ix_incident_update_{col}', 'incident_update', [col])


def downgrade():
    op.drop_table('incident_update')
    op.drop_table('campus_incident')
