"""
Initial migration baseline.

This is the initial migration that establishes the migration infrastructure.
No actual schema changes are made in this migration - it serves as a baseline
for future migrations.

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema - Initial baseline.
    
    This migration establishes the baseline for the database schema.
    Future migrations will add actual tables and relationships.
    """
    # This is a baseline migration - no schema changes needed
    # Tables will be created via SQLAlchemy's create_all in development
    # or via subsequent Alembic migrations in production
    pass


def downgrade() -> None:
    """
    Downgrade schema - Revert to empty state.
    
    Since this is the baseline migration, downgrading removes nothing.
    Future migrations will handle table drops.
    """
    # Baseline migration - nothing to downgrade
    pass
