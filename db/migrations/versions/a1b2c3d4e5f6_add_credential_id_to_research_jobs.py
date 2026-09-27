"""add_credential_id_to_research_jobs

Adds credential_id column to research_jobs for Phase 3 Credential Broker.
Nullable so existing rows are unaffected; populated on new job creation.

Revision ID: a1b2c3d4e5f6
Revises: 9a1b2c3d4e5f
Create Date: 2026-09-27 09:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'research_jobs',
        sa.Column('credential_id', sa.String(), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_column('research_jobs', 'credential_id')
