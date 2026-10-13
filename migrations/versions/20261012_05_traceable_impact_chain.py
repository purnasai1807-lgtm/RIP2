"""Store explicit causal parent links and longer source labels for impact items.

Revision ID: 20261012_05
Revises: 20261012_04
"""
from alembic import op
import sqlalchemy as sa

revision = '20261012_05'
down_revision = '20261012_04'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column['name']: column for column in sa.inspect(bind).get_columns('impact')}
    if 'parent_activity' not in columns:
        with op.batch_alter_table('impact') as batch_op:
            batch_op.add_column(sa.Column('parent_activity', sa.String(length=140), nullable=False, server_default='Proposed change'))
    # The additive baseline may have created tables from current metadata on a fresh DB.
    # Only widen the source column when the live schema actually needs it.
    source = next((column for column in sa.inspect(bind).get_columns('impact') if column['name'] == 'source'), None)
    if source and getattr(source['type'], 'length', None) != 120:
        with op.batch_alter_table('impact') as batch_op:
            batch_op.alter_column('source', existing_type=source['type'], type_=sa.String(length=120), existing_nullable=False)


def downgrade():
    # Preserve causal metadata during rollback; shrinking source could truncate provenance.
    pass
