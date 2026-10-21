"""create_canon_persistence_schema

Revision ID: f15b07ed0981
Revises: 
Create Date: 2026-10-20 23:32:33.474107

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f15b07ed0981'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Project scope boundary table
    op.create_table(
        'project',
        sa.Column('project_id', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('project_id', name='pk_project')
    )

    # Canon commit table with project/branch scope
    op.create_table(
        'canon_commit',
        sa.Column('project_id', sa.String(length=255), nullable=False),
        sa.Column('branch_name', sa.String(length=255), nullable=False),
        sa.Column('commit_id', sa.String(length=64), nullable=False),
        sa.Column('parent_commit_id', sa.String(length=64), nullable=True),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('changeset', sa.JSON(), nullable=False),
        sa.Column('permit_ref', sa.String(length=255), nullable=True),
        sa.Column('committed_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('project_id', 'branch_name', 'commit_id', name='pk_canon_commit'),
        sa.ForeignKeyConstraint(['project_id'], ['project.project_id'], name='fk_canon_commit_project'),
        sa.ForeignKeyConstraint(['project_id', 'branch_name', 'parent_commit_id'], ['canon_commit.project_id', 'canon_commit.branch_name', 'canon_commit.commit_id'], name='fk_canon_commit_parent'),
        sa.UniqueConstraint('project_id', 'branch_name', 'idempotency_key', name='uq_canon_commit_idempotency')
    )

    # Partial unique index for root commit (parent_commit_id IS NULL) per project/branch
    op.create_index(
        'uq_canon_commit_root',
        'canon_commit',
        ['project_id', 'branch_name'],
        unique=True,
        postgresql_where=sa.text('parent_commit_id IS NULL')
    )

    # Branch head table with CAS semantics
    op.create_table(
        'branch_head',
        sa.Column('project_id', sa.String(length=255), nullable=False),
        sa.Column('branch_name', sa.String(length=255), nullable=False),
        sa.Column('head_commit_id', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('project_id', 'branch_name', name='pk_branch_head'),
        sa.ForeignKeyConstraint(['project_id'], ['project.project_id'], name='fk_branch_head_project'),
        sa.ForeignKeyConstraint(['project_id', 'branch_name', 'head_commit_id'], ['canon_commit.project_id', 'canon_commit.branch_name', 'canon_commit.commit_id'], name='fk_branch_head_commit')
    )

    # Canon event table with project/branch scope
    op.create_table(
        'canon_event',
        sa.Column('project_id', sa.String(length=255), nullable=False),
        sa.Column('branch_name', sa.String(length=255), nullable=False),
        sa.Column('event_id', sa.String(length=64), nullable=False),
        sa.Column('commit_id', sa.String(length=64), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('event_data', sa.JSON(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('project_id', 'branch_name', 'event_id', name='pk_canon_event'),
        sa.ForeignKeyConstraint(['project_id'], ['project.project_id'], name='fk_canon_event_project'),
        sa.ForeignKeyConstraint(['project_id', 'branch_name', 'commit_id'], ['canon_commit.project_id', 'canon_commit.branch_name', 'canon_commit.commit_id'], name='fk_canon_event_commit')
    )

    # Execution control table for permit/fencing version control
    op.create_table(
        'execution_control',
        sa.Column('project_id', sa.String(length=255), nullable=False),
        sa.Column('branch_name', sa.String(length=255), nullable=False),
        sa.Column('execution_version', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('project_id', 'branch_name', name='pk_execution_control'),
        sa.ForeignKeyConstraint(['project_id'], ['project.project_id'], name='fk_execution_control_project')
    )

    # Artifact content table for content-addressed storage
    op.create_table(
        'artifact_content',
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('content_data', sa.LargeBinary(), nullable=False),
        sa.Column('stored_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('content_hash', name='pk_artifact_content')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('artifact_content')
    op.drop_table('execution_control')
    op.drop_table('canon_event')
    op.drop_table('branch_head')
    op.drop_index('uq_canon_commit_root', table_name='canon_commit')
    op.drop_table('canon_commit')
    op.drop_table('project')
