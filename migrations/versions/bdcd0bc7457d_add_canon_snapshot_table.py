"""add_canon_snapshot_table

Revision ID: bdcd0bc7457d
Revises: f15b07ed0981
Create Date: 2026-10-23 10:02:26.141439

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bdcd0bc7457d'
down_revision: Union[str, Sequence[str], None] = 'f15b07ed0981'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add canon_snapshot table for projection snapshots."""
    # Canon snapshot table for materialized state projections
    op.create_table(
        'canon_snapshot',
        sa.Column('project_id', sa.String(length=255), nullable=False),
        sa.Column('branch_name', sa.String(length=255), nullable=False),
        sa.Column('snapshot_id', sa.String(length=64), nullable=False),
        sa.Column('commit_id', sa.String(length=64), nullable=False),
        sa.Column('reducer_version', sa.String(length=32), nullable=False),
        sa.Column('schema_version', sa.String(length=32), nullable=False),
        sa.Column('state_digest', sa.String(length=64), nullable=False),
        sa.Column('snapshot_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('project_id', 'branch_name', 'snapshot_id', name='pk_canon_snapshot'),
        sa.ForeignKeyConstraint(['project_id'], ['project.project_id'], name='fk_canon_snapshot_project'),
        sa.ForeignKeyConstraint(['project_id', 'branch_name', 'commit_id'], ['canon_commit.project_id', 'canon_commit.branch_name', 'canon_commit.commit_id'], name='fk_canon_snapshot_commit')
    )

    # Index for looking up snapshots by commit
    op.create_index(
        'ix_canon_snapshot_commit',
        'canon_snapshot',
        ['project_id', 'branch_name', 'commit_id']
    )


def downgrade() -> None:
    """Downgrade schema - remove canon_snapshot table."""
    op.drop_index('ix_canon_snapshot_commit', table_name='canon_snapshot')
    op.drop_table('canon_snapshot')
