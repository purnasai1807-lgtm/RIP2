"""Persist canonical decision inputs and result hashes for reproducible analysis.

Revision ID: 20261013_12
Revises: 20261013_11
"""
from alembic import op
import sqlalchemy as sa

revision = '20261013_12'
down_revision = '20261013_11'
branch_labels = None
depends_on = None


def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('scenario')}
    if 'analysis_inputs_json' not in columns:
        op.add_column('scenario', sa.Column('analysis_inputs_json', sa.Text(), nullable=True))
    if 'analysis_input_hash' not in columns:
        op.add_column('scenario', sa.Column('analysis_input_hash', sa.String(length=64), nullable=True))
    if 'analysis_result_hash' not in columns:
        op.add_column('scenario', sa.Column('analysis_result_hash', sa.String(length=64), nullable=True))


def downgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('scenario')}
    for name in ('analysis_result_hash', 'analysis_input_hash', 'analysis_inputs_json'):
        if name in columns:
            op.drop_column('scenario', name)
