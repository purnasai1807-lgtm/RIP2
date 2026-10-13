"""Create any missing CampusRipple tables without dropping existing college data.

Revision ID: 20261011_01
Revises:
"""
from alembic import op
import sqlalchemy as sa
revision = '20261011_01'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # This baseline is deliberately additive for legacy deployments: create only missing tables.
    # Existing tables/rows are preserved. Subsequent schema changes belong in new revisions.
    from app import db
    from app import models  # register all models in metadata
    bind = op.get_bind()
    db.metadata.create_all(bind=bind, checkfirst=True)
    inspector = sa.inspect(bind)
    if 'user' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('user')}
        if 'reset_token_hash' not in columns:
            op.add_column('user', sa.Column('reset_token_hash', sa.String(length=64), nullable=True))
        if 'reset_token_expires_at' not in columns:
            op.add_column('user', sa.Column('reset_token_expires_at', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    # Baseline owns no existing user data; intentionally non-destructive.
    pass
