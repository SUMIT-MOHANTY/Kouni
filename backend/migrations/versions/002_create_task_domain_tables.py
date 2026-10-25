"""
Create task domain tables (categories, tasks, task_tags, task_history)

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create task domain tables with indexes."""
    
    # Create categories table
    op.create_table(
        'categories',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
    )
    
    # Create indexes on categories table
    op.create_index('ix_categories_name', 'categories', ['name'])
    op.create_index('ix_categories_user_id', 'categories', ['user_id'])
    
    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('active', 'completed', 'archived', name='task_status'), nullable=False, server_default='active'),
        sa.Column('priority', sa.Enum('low', 'medium', 'high', name='task_priority'), nullable=False, server_default='medium'),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now())
    )
    
    # Create indexes on tasks table
    op.create_index('ix_tasks_title', 'tasks', ['title'])
    op.create_index('ix_tasks_status', 'tasks', ['status'])
    op.create_index('ix_tasks_priority', 'tasks', ['priority'])
    op.create_index('ix_tasks_due_date', 'tasks', ['due_date'])
    op.create_index('ix_tasks_user_id', 'tasks', ['user_id'])
    op.create_index('ix_tasks_user_status', 'tasks', ['user_id', 'status'])
    op.create_index('ix_tasks_user_priority', 'tasks', ['user_id', 'priority'])
    op.create_index('ix_tasks_user_due_date', 'tasks', ['user_id', 'due_date'])
    
    # Create task_tags junction table
    op.create_table(
        'task_tags',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category_id', sa.String(36), sa.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
    )
    
    # Create indexes on task_tags table
    op.create_index('ix_task_tags_task_id', 'task_tags', ['task_id'])
    op.create_index('ix_task_tags_category_id', 'task_tags', ['category_id'])
    op.create_index('ix_task_tags_task_category', 'task_tags', ['task_id', 'category_id'], unique=True)
    
    # Create task_history table
    op.create_table(
        'task_history',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('field_changes', sa.Text(), nullable=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now())
    )
    
    # Create indexes on task_history table
    op.create_index('ix_task_history_task_id', 'task_history', ['task_id'])
    op.create_index('ix_task_history_action', 'task_history', ['action'])
    op.create_index('ix_task_history_user_id', 'task_history', ['user_id'])
    op.create_index('ix_task_history_timestamp', 'task_history', ['timestamp'])
    op.create_index('ix_task_history_task_timestamp', 'task_history', ['task_id', 'timestamp'])


def downgrade() -> None:
    """Drop task domain tables."""
    # Drop task_history table (with cascade, drops indexes too)
    op.drop_table('task_history')
    
    # Drop task_tags table (with cascade, drops indexes too)
    op.drop_table('task_tags')
    
    # Drop tasks table (with cascade, drops indexes too)
    op.drop_table('tasks')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS task_status')
    op.execute('DROP TYPE IF EXISTS task_priority')
    
    # Drop categories table (with cascade, drops indexes too)
    op.drop_table('categories')
