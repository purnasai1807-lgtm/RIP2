"""Add human-reviewed impact feedback.

Revision ID: 20261012_09
Revises: 20261012_08
"""
from alembic import op
import sqlalchemy as sa

revision = '20261012_09'
down_revision = '20261012_08'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'impact_feedback' not in inspector.get_table_names():
        op.create_table(
            'impact_feedback',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('impact_id', sa.Integer(), sa.ForeignKey('impact.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
            sa.Column('assessment', sa.String(length=20), nullable=False),
            sa.Column('observed_outcome', sa.String(length=1200), nullable=False, server_default=''),
            sa.Column('analysis_version', sa.String(length=40), nullable=False, server_default='unknown'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint('impact_id', 'user_id', name='uq_impact_feedback_user'),
        )
    inspector = sa.inspect(bind)
    existing_indexes = {i['name'] for i in inspector.get_indexes('impact_feedback')}
    for name, column in [('ix_impact_feedback_impact_id','impact_id'), ('ix_impact_feedback_user_id','user_id'), ('ix_impact_feedback_assessment','assessment'), ('ix_impact_feedback_created_at','created_at')]:
        if name not in existing_indexes:
            op.create_index(name, 'impact_feedback', [column])


def downgrade():
    op.drop_table('impact_feedback')
