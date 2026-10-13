"""Add academic calendar, service request, substitution, invigilation and notifications.

Revision ID: 20261012_04
Revises: 20261011_03
"""
from alembic import op
import sqlalchemy as sa

revision = '20261012_04'
down_revision = '20261011_03'
branch_labels = None
depends_on = None


def upgrade():
    # Additive only: creates the new tables without dropping or rewriting college records.
    from app import db
    from app import models  # noqa: F401 - register new models in metadata
    db.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    # Intentionally non-destructive. New workflow data may already be in active use;
    # operators should archive/export it and perform an explicit reviewed removal if needed.
    pass
