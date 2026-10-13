"""Add optional email verification and official timetable sync provenance.

Revision ID: 20261012_07
Revises: 20261012_06
"""
from alembic import op
import sqlalchemy as sa

revision = '20261012_07'
down_revision = '20261012_06'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    user_cols = {c['name'] for c in inspector.get_columns('user')}
    if 'email_verified_at' not in user_cols:
        op.add_column('user', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    if 'email_verification_token_hash' not in user_cols:
        op.add_column('user', sa.Column('email_verification_token_hash', sa.String(length=64), nullable=True))
    if 'email_verification_expires_at' not in user_cols:
        op.add_column('user', sa.Column('email_verification_expires_at', sa.DateTime(timezone=True), nullable=True))
    if 'ix_user_email_verification_token_hash' not in {i['name'] for i in inspector.get_indexes('user')}:
        op.create_index('ix_user_email_verification_token_hash', 'user', ['email_verification_token_hash'])
    timetable_cols = {c['name'] for c in inspector.get_columns('timetable_entry')}
    if 'source_system' not in timetable_cols:
        op.add_column('timetable_entry', sa.Column('source_system', sa.String(length=40), nullable=False, server_default='manual'))
    if 'source_record_id' not in timetable_cols:
        op.add_column('timetable_entry', sa.Column('source_record_id', sa.String(length=100), nullable=True))
    if 'source_synced_at' not in timetable_cols:
        op.add_column('timetable_entry', sa.Column('source_synced_at', sa.DateTime(timezone=True), nullable=True))
    if 'ix_timetable_entry_source_record_id' not in {i['name'] for i in inspector.get_indexes('timetable_entry')}:
        op.create_index('ix_timetable_entry_source_record_id', 'timetable_entry', ['source_record_id'])
    if 'integration_sync_run' not in inspector.get_table_names():
        op.create_table('integration_sync_run',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('integration', sa.String(length=40), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('records_received', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('records_created', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('records_updated', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('message', sa.String(length=1000), nullable=False, server_default=''),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True))
        op.create_index('ix_integration_sync_run_integration', 'integration_sync_run', ['integration'])
        op.create_index('ix_integration_sync_run_status', 'integration_sync_run', ['status'])


def downgrade():
    op.drop_index('ix_integration_sync_run_status', table_name='integration_sync_run')
    op.drop_index('ix_integration_sync_run_integration', table_name='integration_sync_run')
    op.drop_table('integration_sync_run')
    op.drop_index('ix_timetable_entry_source_record_id', table_name='timetable_entry')
    op.drop_column('timetable_entry', 'source_synced_at')
    op.drop_column('timetable_entry', 'source_record_id')
    op.drop_column('timetable_entry', 'source_system')
    op.drop_index('ix_user_email_verification_token_hash', table_name='user')
    op.drop_column('user', 'email_verification_expires_at')
    op.drop_column('user', 'email_verification_token_hash')
    op.drop_column('user', 'email_verified_at')
