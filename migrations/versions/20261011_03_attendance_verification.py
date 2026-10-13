"""Add staff verification metadata for attendance records.

Revision ID: 20261011_03
Revises: 20261011_02
"""
from alembic import op
import sqlalchemy as sa
revision = '20261011_03'
down_revision = '20261011_02'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    if 'attendance_record' not in sa.inspect(bind).get_table_names():
        return
    cols = {c['name'] for c in sa.inspect(bind).get_columns('attendance_record')}
    if 'verified_by' not in cols:
        op.add_column('attendance_record', sa.Column('verified_by', sa.Integer(), nullable=True))
        op.create_foreign_key('fk_attendance_record_verified_by_user', 'attendance_record', 'user', ['verified_by'], ['id'])
    if 'verified_at' not in cols:
        op.add_column('attendance_record', sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))
    # Historical self-check-ins are deliberately not auto-promoted to official attendance.
    op.execute("UPDATE attendance_record SET status = 'Unverified' WHERE status = 'Present' AND verified_by IS NULL")

def downgrade():
    bind = op.get_bind()
    if 'attendance_record' not in sa.inspect(bind).get_table_names(): return
    cols = {c['name'] for c in sa.inspect(bind).get_columns('attendance_record')}
    if 'verified_at' in cols: op.drop_column('attendance_record', 'verified_at')
    if 'verified_by' in cols:
        op.drop_constraint('fk_attendance_record_verified_by_user', 'attendance_record', type_='foreignkey')
        op.drop_column('attendance_record', 'verified_by')
