"""Phase 9 outcome review and continuous improvement."""
from alembic import op
import sqlalchemy as sa

revision = '20261013_15'
down_revision = '20261013_14'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'scenario_outcome_review',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scenario_id', sa.Integer(), sa.ForeignKey('scenario.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('outcome', sa.String(20), nullable=False),
        sa.Column('effectiveness', sa.Integer(), nullable=False),
        sa.Column('lessons_learned', sa.String(2000), nullable=False, server_default=''),
        sa.Column('follow_up', sa.String(1200), nullable=False, server_default=''),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('scenario_id', 'user_id', name='uq_scenario_outcome_review_user'),
    )
    op.create_index('ix_scenario_outcome_review_scenario_id', 'scenario_outcome_review', ['scenario_id'])
    op.create_index('ix_scenario_outcome_review_user_id', 'scenario_outcome_review', ['user_id'])
    op.create_index('ix_scenario_outcome_review_reviewed_at', 'scenario_outcome_review', ['reviewed_at'])

def downgrade():
    op.drop_table('scenario_outcome_review')
