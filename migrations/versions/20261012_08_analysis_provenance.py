"""Store analysis version, timestamp, and evidence references.

Revision ID: 20261012_08
Revises: 20261012_07
"""
from alembic import op
import sqlalchemy as sa

revision = '20261012_08'
down_revision = '20261012_07'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    scenario_cols = {c['name'] for c in sa.inspect(bind).get_columns('scenario')}
    if 'analysis_version' not in scenario_cols:
        op.add_column('scenario', sa.Column('analysis_version', sa.String(length=40), nullable=True))
    if 'analyzed_at' not in scenario_cols:
        op.add_column('scenario', sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=True))
    impact_cols = {c['name'] for c in sa.inspect(bind).get_columns('impact')}
    if 'evidence_ref' not in impact_cols:
        op.add_column('impact', sa.Column('evidence_ref', sa.String(length=160), nullable=True))


def downgrade():
    op.drop_column('impact', 'evidence_ref')
    op.drop_column('scenario', 'analyzed_at')
    op.drop_column('scenario', 'analysis_version')
