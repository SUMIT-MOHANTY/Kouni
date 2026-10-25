"""
Demo Data Seeder

Auto-seed function for SQLite database that creates sample users, categories, 
and tasks with relationships on application startup. Only runs when using SQLite
and when the database is empty or configured to seed.
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from flask import current_app

from ..extensions import db
from ..models.user import User
from ..models.user_session import UserSession
from ..models.task import Task, TaskStatus, TaskPriority
from ..models.category import Category
from ..models.task_history import TaskHistory, HistoryAction
from ..models.task_tag import TaskTag


class DemoDataSeeder:
    """
    Seeder for demo/sample data in SQLite databases.
    
    Creates realistic sample data for development and testing:
    - Admin user with full privileges
    - Regular users with various activity levels
    - Categories with different colors
    - Tasks with various statuses, priorities, and due dates
    - Task history entries for audit trail
    """
    
    # Sample data configuration
    SAMPLE_USERS = [
        {
            'username': 'admin',
            'email': 'admin@example.com',
            'password': 'admin123',
            'is_admin': True,
            'is_active': True
        },
        {
            'username': 'john_doe',
            'email': 'john@example.com',
            'password': 'password123',
            'is_admin': False,
            'is_active': True
        },
        {
            'username': 'jane_smith',
            'email': 'jane@example.com',
            'password': 'password123',
            'is_admin': False,
            'is_active': True
        },
        {
            'username': 'inactive_user',
            'email': 'inactive@example.com',
            'password': 'password123',
            'is_admin': False,
            'is_active': False
        },
        {
            'username': 'power_user',
            'email': 'power@example.com',
            'password': 'password123',
            'is_admin': False,
            'is_active': True
        }
    ]
    
    SAMPLE_CATEGORIES = [
        {'name': 'Work', 'color': '#FF5733'},
        {'name': 'Personal', 'color': '#33FF57'},
        {'name': 'Shopping', 'color': '#3357FF'},
        {'name': 'Health', 'color': '#FF33F5'},
        {'name': 'Finance', 'color': '#33FFF5'},
        {'name': 'Education', 'color': '#F5FF33'},
        {'name': 'Travel', 'color': '#FF8C33'},
        {'name': 'Projects', 'color': '#8C33FF'}
    ]
    
    SAMPLE_TASKS = [
        # Admin tasks
        {
            'user_index': 0,
            'title': 'Review user registrations',
            'description': 'Check and approve pending user registrations',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.HIGH,
            'due_date_days': 1,
            'category_indices': [0, 7]
        },
        {
            'user_index': 0,
            'title': 'System backup verification',
            'description': 'Verify last night\'s database backups completed successfully',
            'status': TaskStatus.COMPLETED,
            'priority': TaskPriority.HIGH,
            'due_date_days': 0,
            'category_indices': [0]
        },
        {
            'user_index': 0,
            'title': 'Update security policies',
            'description': 'Review and update password policies and access controls',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.MEDIUM,
            'due_date_days': 7,
            'category_indices': [0, 4]
        },
        {
            'user_index': 0,
            'title': 'Quarterly report preparation',
            'description': 'Prepare system usage statistics for quarterly review',
            'status': TaskStatus.ARCHIVED,
            'priority': TaskPriority.MEDIUM,
            'due_date_days': -30,
            'category_indices': [0, 4]
        },
        
        # John Doe tasks
        {
            'user_index': 1,
            'title': 'Complete project proposal',
            'description': 'Finish writing the Q4 project proposal document',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.HIGH,
            'due_date_days': 3,
            'category_indices': [0, 7]
        },
        {
            'user_index': 1,
            'title': 'Team meeting preparation',
            'description': 'Prepare slides for Monday\'s team meeting',
            'status': TaskStatus.COMPLETED,
            'priority': TaskPriority.MEDIUM,
            'due_date_days': -2,
            'category_indices': [0]
        },
        {
            'user_index': 1,
            'title': 'Buy groceries',
            'description': 'Milk, eggs, bread, vegetables, and coffee',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.LOW,
            'due_date_days': 1,
            'category_indices': [1, 2]
        },
        {
            'user_index': 1,
            'title': 'Gym workout',
            'description': 'Cardio and strength training session',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.MEDIUM,
            'due_date_days': 0,
            'category_indices': [3]
        },
        {
            'user_index': 1,
            'title': 'Pay electricity bill',
            'description': 'Monthly utility payment due',
            'status': TaskStatus.COMPLETED,
            'priority': TaskPriority.HIGH,
            'due_date_days': -5,
            'category_indices': [4]
        },
        {
            'user_index': 1,
            'title': 'Learn Python async',
            'description': 'Complete async/await tutorial and exercises',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.MEDIUM,
            'due_date_days': 14,
            'category_indices': [5]
        },
        
        # Jane Smith tasks
        {
            'user_index': 2,
            'title': 'Doctor appointment',
            'description': 'Annual checkup with Dr. Johnson',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.HIGH,
            'due_date_days': 5,
            'category_indices': [3]
        },
        {
            'user_index': 2,
            'title': 'Plan vacation',
            'description': 'Research hotels and flights for summer vacation',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.LOW,
            'due_date_days': 30,
            'category_indices': [1, 6]
        },
        {
            'user_index': 2,
            'title': 'Submit expense report',
            'description': 'Compile and submit last month\'s business expenses',
            'status': TaskStatus.COMPLETED,
            'priority': TaskPriority.MEDIUM,
            'due_date_days': -3,
            'category_indices': [0, 4]
        },
        {
            'user_index': 2,
            'title': 'Book club reading',
            'description': 'Finish reading "The Great Gatsby" for book club',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.LOW,
            'due_date_days': 10,
            'category_indices': [1, 5]
        },
        {
            'user_index': 2,
            'title': 'Yoga class',
            'description': 'Evening yoga session at the community center',
            'status': TaskStatus.ARCHIVED,
            'priority': TaskPriority.LOW,
            'due_date_days': -10,
            'category_indices': [3]
        },
        
        # Power user tasks (many tasks to show pagination)
        {
            'user_index': 4,
            'title': 'Project Alpha sprint planning',
            'description': 'Plan tasks for the upcoming sprint',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.HIGH,
            'due_date_days': 2,
            'category_indices': [0, 7]
        },
        {
            'user_index': 4,
            'title': 'Code review - Authentication module',
            'description': 'Review pull request #234 for the auth service',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.HIGH,
            'due_date_days': 1,
            'category_indices': [0, 7]
        },
        {
            'user_index': 4,
            'title': 'Update documentation',
            'description': 'Update API documentation with new endpoints',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.MEDIUM,
            'due_date_days': 5,
            'category_indices': [0, 5]
        },
        {
            'user_index': 4,
            'title': 'Fix bug #456',
            'description': 'Resolve memory leak in task processing',
            'status': TaskStatus.COMPLETED,
            'priority': TaskPriority.HIGH,
            'due_date_days': -1,
            'category_indices': [0, 7]
        },
        {
            'user_index': 4,
            'title': 'Team lunch',
            'description': 'Organize Friday team lunch at the new restaurant',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.LOW,
            'due_date_days': 4,
            'category_indices': [1]
        },
        {
            'user_index': 4,
            'title': 'Investment portfolio review',
            'description': 'Review and rebalance investment portfolio',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.MEDIUM,
            'due_date_days': 7,
            'category_indices': [4]
        },
        {
            'user_index': 4,
            'title': 'Car maintenance',
            'description': 'Schedule oil change and tire rotation',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.MEDIUM,
            'due_date_days': 14,
            'category_indices': [1]
        },
        {
            'user_index': 4,
            'title': 'Online course - Advanced SQL',
            'description': 'Complete modules 5-8 of the SQL optimization course',
            'status': TaskStatus.ACTIVE,
            'priority': TaskPriority.LOW,
            'due_date_days': 21,
            'category_indices': [5]
        },
        {
            'user_index': 4,
            'title': 'Backup personal files',
            'description': 'Sync photos and documents to cloud storage',
            'status': TaskStatus.COMPLETED,
            'priority': TaskPriority.LOW,
            'due_date_days': -7,
            'category_indices': [1]
        },
        {
            'user_index': 4,
            'title': 'Research new laptop',
            'description': 'Compare specs and prices for new development laptop',
            'status': TaskStatus.ARCHIVED,
            'priority': TaskPriority.LOW,
            'due_date_days': -14,
            'category_indices': [2, 4]
        }
    ]
    
    @staticmethod
    def should_seed() -> bool:
        """
        Check if seeding should be performed.
        
        Seeding occurs when:
        - Using SQLite database
        - AUTO_SEED environment variable is set to 'true' or '1'
        - Or when explicitly called
        
        Returns:
            bool: True if seeding should be performed
        """
        database_url = os.environ.get('DATABASE_URL', '')
        auto_seed = os.environ.get('AUTO_SEED', 'false').lower() in ('true', '1', 'yes')
        
        # Only auto-seed SQLite databases
        is_sqlite = 'sqlite' in database_url.lower() or database_url == ''
        
        return is_sqlite and auto_seed
    
    @staticmethod
    def is_database_empty() -> bool:
        """
        Check if the database has any users.
        
        Returns:
            bool: True if no users exist
        """
        user_count = db.session.query(User).count()
        return user_count == 0
    
    @staticmethod
    def seed_users() -> list[User]:
        """
        Create sample users.
        
        Returns:
            list: List of created User objects
        """
        users = []
        
        for user_data in DemoDataSeeder.SAMPLE_USERS:
            user = User(
                username=user_data['username'],
                email=user_data['email'],
                is_admin=user_data['is_admin'],
                is_active=user_data['is_active']
            )
            user.set_password(user_data['password'])
            
            db.session.add(user)
            users.append(user)
        
        db.session.flush()
        
        if current_app:
            current_app.logger.info(f"Created {len(users)} sample users")
        
        return users
    
    @staticmethod
    def seed_categories(users: list[User]) -> list[Category]:
        """
        Create sample categories for each user.
        
        Args:
            users: List of User objects to create categories for
            
        Returns:
            list: List of created Category objects
        """
        categories = []
        
        # Create categories for each active user
        for user in users:
            if not user.is_active:
                continue
                
            for i, cat_data in enumerate(DemoDataSeeder.SAMPLE_CATEGORIES):
                # Skip some categories for variety
                if user.username == 'john_doe' and i > 5:
                    continue
                if user.username == 'jane_smith' and i % 2 == 1:
                    continue
                
                category = Category(
                    name=cat_data['name'],
                    color=cat_data['color'],
                    user_id=user.id
                )
                db.session.add(category)
                categories.append(category)
        
        db.session.flush()
        
        if current_app:
            current_app.logger.info(f"Created {len(categories)} sample categories")
        
        return categories
    
    @staticmethod
    def seed_tasks(users: list[User], categories: list[Category]) -> list[Task]:
        """
        Create sample tasks with category associations.
        
        Args:
            users: List of User objects
            categories: List of Category objects
            
        Returns:
            list: List of created Task objects
        """
        tasks = []
        
        # Group categories by user for easy lookup
        categories_by_user = {}
        for cat in categories:
            if cat.user_id not in categories_by_user:
                categories_by_user[cat.user_id] = []
            categories_by_user[cat.user_id].append(cat)
        
        for task_data in DemoDataSeeder.SAMPLE_TASKS:
            user = users[task_data['user_index']]
            
            # Calculate due date
            due_date = None
            if task_data['due_date_days'] is not None:
                due_date = datetime.utcnow() + timedelta(days=task_data['due_date_days'])
            
            task = Task(
                user_id=user.id,
                title=task_data['title'],
                description=task_data['description'],
                status=task_data['status'],
                priority=task_data['priority'],
                due_date=due_date,
                version=1
            )
            
            db.session.add(task)
            db.session.flush()  # Get task ID
            
            # Add category associations
            user_cats = categories_by_user.get(user.id, [])
            for cat_idx in task_data['category_indices']:
                if cat_idx < len(user_cats):
                    task_tag = TaskTag(
                        task_id=task.id,
                        category_id=user_cats[cat_idx].id
                    )
                    db.session.add(task_tag)
            
            # Create history entry
            history = TaskHistory(
                task_id=task.id,
                action=HistoryAction.CREATE,
                user_id=user.id,
                field_changes=None
            )
            db.session.add(history)
            
            # Add completion history for completed tasks
            if task_data['status'] == TaskStatus.COMPLETED:
                complete_history = TaskHistory(
                    task_id=task.id,
                    action=HistoryAction.COMPLETE,
                    user_id=user.id
                )
                complete_history.set_field_changes({
                    'status': {'old': TaskStatus.ACTIVE.value, 'new': TaskStatus.COMPLETED.value}
                })
                db.session.add(complete_history)
            
            # Add archive history for archived tasks
            if task_data['status'] == TaskStatus.ARCHIVED:
                archive_history = TaskHistory(
                    task_id=task.id,
                    action=HistoryAction.ARCHIVE,
                    user_id=user.id
                )
                archive_history.set_field_changes({
                    'status': {'old': TaskStatus.COMPLETED.value, 'new': TaskStatus.ARCHIVED.value}
                })
                db.session.add(archive_history)
            
            tasks.append(task)
        
        if current_app:
            current_app.logger.info(f"Created {len(tasks)} sample tasks")
        
        return tasks
    
    @staticmethod
    def seed() -> dict:
        """
        Run the complete seeding process.
        
        Creates users, categories, tasks, and history entries.
        
        Returns:
            dict: Summary of seeded data
        """
        if not DemoDataSeeder.is_database_empty():
            if current_app:
                current_app.logger.info("Database already contains data, skipping seed")
            return {
                'seeded': False,
                'reason': 'Database not empty',
                'users': 0,
                'categories': 0,
                'tasks': 0
            }
        
        try:
            # Create users
            users = DemoDataSeeder.seed_users()
            
            # Create categories
            categories = DemoDataSeeder.seed_categories(users)
            
            # Create tasks
            tasks = DemoDataSeeder.seed_tasks(users, categories)
            
            db.session.commit()
            
            result = {
                'seeded': True,
                'users': len(users),
                'categories': len(categories),
                'tasks': len(tasks)
            }
            
            if current_app:
                current_app.logger.info(f"Demo data seeded successfully: {result}")
            
            return result
            
        except Exception as e:
            db.session.rollback()
            if current_app:
                current_app.logger.error(f"Error seeding demo data: {str(e)}")
            raise
    
    @staticmethod
    def seed_if_enabled() -> Optional[dict]:
        """
        Seed data if auto-seeding is enabled and conditions are met.
        
        Returns:
            dict or None: Seeding result if performed, None otherwise
        """
        if DemoDataSeeder.should_seed():
            return DemoDataSeeder.seed()
        return None


def seed_demo_data() -> Optional[dict]:
    """
    Convenience function to seed demo data.
    
    This is the main entry point for seeding demo data.
    It checks if seeding should be performed and executes the seeding process.
    
    Returns:
        dict or None: Seeding result if performed, None otherwise
        
    Example:
        from app.seeds.demo_data import seed_demo_data
        
        # In app initialization:
        with app.app_context():
            seed_demo_data()
    """
    return DemoDataSeeder.seed_if_enabled()


def force_seed_demo_data() -> dict:
    """
    Force seed demo data regardless of environment settings.
    
    Use this for manual seeding or in tests.
    
    Returns:
        dict: Seeding result
        
    Example:
        from app.seeds.demo_data import force_seed_demo_data
        
        # Force seed (will fail if database not empty):
        result = force_seed_demo_data()
    """
    return DemoDataSeeder.seed()
