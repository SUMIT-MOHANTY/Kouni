"""
Task Service

Business logic layer for task management with audit logging and optimistic locking.
Provides CRUD operations, status transitions, and automatic history tracking.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import and_, or_, desc, asc
from sqlalchemy.orm import joinedload
from ..extensions import db
from ..models import Task, TaskStatus, TaskPriority, TaskHistory, HistoryAction, TaskTag, Category


class TaskServiceError(Exception):
    """Base exception for task service errors."""
    pass


class TaskNotFoundError(TaskServiceError):
    """Raised when a task is not found."""
    pass


class CategoryNotFoundError(TaskServiceError):
    """Raised when a category is not found."""
    pass


class OptimisticLockError(TaskServiceError):
    """Raised when optimistic locking fails."""
    pass


class TaskService:
    """Service class for task management operations."""
    
    @staticmethod
    def create_task(
        user_id: str,
        title: str,
        description: Optional[str] = None,
        status: TaskStatus = TaskStatus.ACTIVE,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: Optional[datetime] = None,
        category_ids: Optional[List[str]] = None
    ) -> Task:
        """
        Create a new task with optional categories.
        
        Args:
            user_id: UUID of the task owner
            title: Task title
            description: Optional task description
            status: Task status (default: ACTIVE)
            priority: Task priority (default: MEDIUM)
            due_date: Optional due date
            category_ids: Optional list of category UUIDs to associate
            
        Returns:
            Task: The created task
            
        Raises:
            CategoryNotFoundError: If a category is not found or doesn't belong to user
        """
        # Create the task
        task = Task(
            user_id=user_id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=due_date,
            version=1
        )
        
        db.session.add(task)
        db.session.flush()  # Get the task ID without committing
        
        # Add categories if provided
        if category_ids:
            for category_id in category_ids:
                from ..models import Category
                from sqlalchemy import select
                category = db.session.execute(
                    select(Category).where(Category.id == category_id, Category.user_id == user_id)
                ).scalar_one_or_none()
                
                if not category:
                    db.session.rollback()
                    raise CategoryNotFoundError(
                        f"Category {category_id} not found or does not belong to user"
                    )
                
                task_tag = TaskTag(task_id=task.id, category_id=category_id)
                db.session.add(task_tag)
        
        # Create history entry
        history = TaskHistory(
            task_id=task.id,
            action=HistoryAction.CREATE,
            user_id=user_id,
            field_changes=None
        )
        db.session.add(history)
        
        db.session.commit()
        return task
    
    @staticmethod
    def get_task_by_id(task_id: str, user_id: str) -> Optional[Task]:
        """
        Get a task by ID with user ownership check.
        
        Args:
            task_id: UUID of the task
            user_id: UUID of the user (for ownership check)
            
        Returns:
            Task or None: The task if found and owned by user
        """
        task = db.session.get(Task, task_id)
        if task and task.user_id == user_id:
            return task
        return None
    
    @staticmethod
    def get_tasks(
        user_id: str,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        category_id: Optional[str] = None,
        due_date_from: Optional[datetime] = None,
        due_date_to: Optional[datetime] = None,
        search_query: Optional[str] = None,
        sort_by: str = 'created_at',
        sort_order: str = 'desc',
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Get tasks with filtering, sorting, and pagination.
        
        Args:
            user_id: UUID of the task owner
            status: Filter by status
            priority: Filter by priority
            category_id: Filter by category
            due_date_from: Filter by due date >=
            due_date_to: Filter by due date <=
            search_query: Search in title and description
            sort_by: Field to sort by
            sort_order: 'asc' or 'desc'
            page: Page number (1-based)
            per_page: Items per page
            
        Returns:
            dict: Paginated results with tasks, total count, and pagination info
        """
        from sqlalchemy import select, func
        
        # Build the base query with filters
        stmt = select(Task).where(Task.user_id == user_id)
        
        # Apply filters - use explicit Task model references
        if status is not None:
            stmt = stmt.where(Task.status == status)
        
        if priority is not None:
            stmt = stmt.where(Task.priority == priority)
        
        if category_id:
            # Use exists subquery to filter tasks by category through TaskTag
            from sqlalchemy import select as sa_select
            task_tag_subquery = sa_select(TaskTag.task_id).where(
                TaskTag.category_id == category_id
            ).scalar_subquery()
            stmt = stmt.where(Task.id.in_(task_tag_subquery))
        
        if due_date_from:
            stmt = stmt.where(Task.due_date >= due_date_from)
        
        if due_date_to:
            stmt = stmt.where(Task.due_date <= due_date_to)
        
        if search_query:
            search_pattern = f"%{search_query}%"
            stmt = stmt.where(
                or_(
                    Task.title.ilike(search_pattern),
                    Task.description.ilike(search_pattern)
                )
            )
        
        # Get total count before applying pagination
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = db.session.execute(count_stmt).scalar()
        total = total_result or 0
        
        # Apply sorting
        sort_column = getattr(Task, sort_by, Task.created_at)
        if sort_order == 'desc':
            stmt = stmt.order_by(desc(sort_column))
        else:
            stmt = stmt.order_by(asc(sort_column))
        
        # Apply pagination
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        tasks = db.session.execute(stmt).scalars().all()
        
        return {
            'tasks': tasks,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        }
    
    @staticmethod
    def update_task(
        task_id: str,
        user_id: str,
        expected_version: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        due_date: Optional[datetime] = None,
        category_ids: Optional[List[str]] = None
    ) -> Task:
        """
        Update a task with optimistic locking.
        
        Args:
            task_id: UUID of the task
            user_id: UUID of the task owner
            expected_version: Expected current version for optimistic locking
            title: New title (optional)
            description: New description (optional)
            status: New status (optional)
            priority: New priority (optional)
            due_date: New due date (optional)
            category_ids: New list of category IDs (optional, replaces existing)
            
        Returns:
            Task: The updated task
            
        Raises:
            TaskNotFoundError: If task not found
            OptimisticLockError: If version mismatch (concurrent update)
            CategoryNotFoundError: If a category is not found
        """
        task = db.session.get(Task, task_id)
        
        if not task or task.user_id != user_id:
            raise TaskNotFoundError(f"Task {task_id} not found")
        
        # Check version for optimistic locking
        if task.version != expected_version:
            raise OptimisticLockError(
                f"Task was modified by another user. Expected version {expected_version}, "
                f"but current version is {task.version}"
            )
        
        # Track changes for history
        changes = {}
        
        # Update fields on Task model only
        if title is not None and title != task.title:
            changes['title'] = {'old': task.title, 'new': title}
            task.title = title
        
        if description is not None and description != task.description:
            changes['description'] = {'old': task.description, 'new': description}
            task.description = description
        
        if status is not None and status != task.status:
            changes['status'] = {'old': task.status.value, 'new': status.value}
            task.status = status
        
        if priority is not None and priority != task.priority:
            changes['priority'] = {'old': task.priority.value, 'new': priority.value}
            task.priority = priority
        
        if due_date is not None and due_date != task.due_date:
            changes['due_date'] = {
                'old': task.due_date.isoformat() if task.due_date else None,
                'new': due_date.isoformat() if due_date else None
            }
            task.due_date = due_date
        
        # Update categories if provided
        if category_ids is not None:
            # Get current category IDs from TaskTag
            from sqlalchemy import select
            current_tags_stmt = select(TaskTag).where(TaskTag.task_id == task.id)
            current_tags_result = db.session.execute(current_tags_stmt).scalars().all()
            current_category_ids = [tt.category_id for tt in current_tags_result if tt.category_id]
            
            # Calculate changes
            added = set(category_ids) - set(current_category_ids)
            removed = set(current_category_ids) - set(category_ids)
            
            if added or removed:
                # Validate new categories
                for cat_id in category_ids:
                    from ..models import Category
                    from sqlalchemy import select
                    category = db.session.execute(
                        select(Category).where(Category.id == cat_id)
                    ).scalar_one_or_none()
                    
                    if not category or category.user_id != user_id:
                        db.session.rollback()
                        raise CategoryNotFoundError(
                            f"Category {cat_id} not found or does not belong to user"
                        )
                
                # Remove old TaskTag associations
                from sqlalchemy import delete
                db.session.execute(delete(TaskTag).where(TaskTag.task_id == task.id))
                
                # Add new TaskTag associations
                for cat_id in category_ids:
                    new_task_tag = TaskTag(task_id=task.id, category_id=cat_id)
                    db.session.add(new_task_tag)
                
                changes['categories'] = {
                    'old': list(removed) if removed else None,
                    'new': list(added) if added else None
                }
        
        # Increment version (timestamp updated via onupdate)
        task.increment_version()
        db.session.add(task)
        
        # Create history entry if there were changes
        if changes:
            history = TaskHistory(
                task_id=task_id,
                action=HistoryAction.UPDATE,
                user_id=user_id
            )
            history.set_field_changes(changes)
            db.session.add(history)
        
        db.session.commit()
        return task
    
    @staticmethod
    def delete_task(task_id: str, user_id: str) -> None:
        """
        Delete a task and its associated data.
        
        Args:
            task_id: UUID of the task
            user_id: UUID of the task owner
            
        Raises:
            TaskNotFoundError: If task not found
        """
        task = db.session.get(Task, task_id)
        
        if not task or task.user_id != user_id:
            raise TaskNotFoundError(f"Task {task_id} not found")
        
        # Create history entry before deletion
        history = TaskHistory(
            task_id=task_id,
            action=HistoryAction.DELETE,
            user_id=user_id,
            field_changes={'deleted_task': {'title': task.title, 'id': task.id}}
        )
        history.set_field_changes(history.field_changes)
        db.session.add(history)
        
        # Delete the task (cascade will handle related records)
        db.session.delete(task)
        db.session.commit()
    
    @staticmethod
    def complete_task(task_id: str, user_id: str, expected_version: int) -> Task:
        """
        Mark a task as completed.
        
        Args:
            task_id: UUID of the task
            user_id: UUID of the task owner
            expected_version: Expected current version for optimistic locking
            
        Returns:
            Task: The updated task
            
        Raises:
            TaskNotFoundError: If task not found
            OptimisticLockError: If version mismatch
        """
        task = db.session.get(Task, task_id)
        
        if not task or task.user_id != user_id:
            raise TaskNotFoundError(f"Task {task_id} not found")
        
        if task.version != expected_version:
            raise OptimisticLockError(
                f"Task was modified by another user. Expected version {expected_version}, "
                f"but current version is {task.version}"
            )
        
        old_status = task.status.value
        task.complete()
        db.session.add(task)
        
        # Create history entry
        history = TaskHistory(
            task_id=task_id,
            action=HistoryAction.COMPLETE,
            user_id=user_id
        )
        history.set_field_changes({
            'status': {'old': old_status, 'new': TaskStatus.COMPLETED.value}
        })
        db.session.add(history)
        
        db.session.commit()
        return task
    
    @staticmethod
    def uncomplete_task(task_id: str, user_id: str, expected_version: int) -> Task:
        """
        Mark a completed task as active.
        
        Args:
            task_id: UUID of the task
            user_id: UUID of the task owner
            expected_version: Expected current version for optimistic locking
            
        Returns:
            Task: The updated task
            
        Raises:
            TaskNotFoundError: If task not found
            OptimisticLockError: If version mismatch
        """
        task = db.session.get(Task, task_id)
        
        if not task or task.user_id != user_id:
            raise TaskNotFoundError(f"Task {task_id} not found")
        
        if task.version != expected_version:
            raise OptimisticLockError(
                f"Task was modified by another user. Expected version {expected_version}, "
                f"but current version is {task.version}"
            )
        
        old_status = task.status.value
        task.uncomplete()
        db.session.add(task)
        
        # Create history entry
        history = TaskHistory(
            task_id=task_id,
            action=HistoryAction.UNCOMPLETE,
            user_id=user_id
        )
        history.set_field_changes({
            'status': {'old': old_status, 'new': TaskStatus.ACTIVE.value}
        })
        db.session.add(history)
        
        db.session.commit()
        return task
    
    @staticmethod
    def archive_task(task_id: str, user_id: str, expected_version: int) -> Task:
        """
        Archive a task.
        
        Args:
            task_id: UUID of the task
            user_id: UUID of the task owner
            expected_version: Expected current version for optimistic locking
            
        Returns:
            Task: The updated task
            
        Raises:
            TaskNotFoundError: If task not found
            OptimisticLockError: If version mismatch
        """
        task = db.session.get(Task, task_id)
        
        if not task or task.user_id != user_id:
            raise TaskNotFoundError(f"Task {task_id} not found")
        
        if task.version != expected_version:
            raise OptimisticLockError(
                f"Task was modified by another user. Expected version {expected_version}, "
                f"but current version is {task.version}"
            )
        
        old_status = task.status.value
        task.archive()
        db.session.add(task)
        
        # Create history entry
        history = TaskHistory(
            task_id=task_id,
            action=HistoryAction.ARCHIVE,
            user_id=user_id
        )
        history.set_field_changes({
            'status': {'old': old_status, 'new': TaskStatus.ARCHIVED.value}
        })
        db.session.add(history)
        
        db.session.commit()
        return task
    
    @staticmethod
    def get_task_history(
        task_id: str,
        user_id: str,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Get task history with pagination.
        
        Args:
            task_id: UUID of the task
            user_id: UUID of the task owner
            page: Page number (1-based)
            per_page: Items per page
            
        Returns:
            dict: Paginated history entries
            
        Raises:
            TaskNotFoundError: If task not found
        """
        from sqlalchemy import select, func
        
        # Query Task model explicitly
        task_result = db.session.execute(
            select(Task).where(Task.id == task_id)
        )
        task = task_result.scalar_one_or_none()
        
        if not task or task.user_id != user_id:
            raise TaskNotFoundError(f"Task {task_id} not found")
        
        # Build query for history
        history_stmt = select(TaskHistory).where(TaskHistory.task_id == task_id).order_by(
            desc(TaskHistory.timestamp)
        )
        
        # Get total count
        count_stmt = select(func.count()).select_from(history_stmt.subquery())
        total = db.session.execute(count_stmt).scalar()
        
        # Apply pagination
        history_stmt = history_stmt.offset((page - 1) * per_page).limit(per_page)
        history_entries = db.session.execute(history_stmt).scalars().all()
        
        return {
            'history': history_entries,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        }
    
    @staticmethod
    def bulk_complete_tasks(task_ids: List[str], user_id: str) -> Dict[str, Any]:
        """
        Complete multiple tasks at once.
        
        Args:
            task_ids: List of task UUIDs
            user_id: UUID of the task owner
            
        Returns:
            dict: Results with success count and errors
        """
        results = {'completed': [], 'failed': []}
        
        for tid in task_ids:
            try:
                # Get Task by ID
                t = db.session.get(Task, tid)
                if t and t.user_id == user_id:
                    old_status_val = t.status.value
                    t.complete()
                    db.session.add(t)
                    
                    # Create TaskHistory entry
                    hist = TaskHistory(
                        task_id=tid,
                        action=HistoryAction.COMPLETE,
                        user_id=user_id
                    )
                    hist.set_field_changes({
                        'status': {'old': old_status_val, 'new': TaskStatus.COMPLETED.value}
                    })
                    db.session.add(hist)
                    
                    results['completed'].append(tid)
                else:
                    results['failed'].append({'id': tid, 'error': 'Task not found'})
            except Exception as e:
                results['failed'].append({'id': tid, 'error': str(e)})
        
        db.session.commit()
        return results
    
    @staticmethod
    def bulk_delete_tasks(task_ids: List[str], user_id: str) -> Dict[str, Any]:
        """
        Delete multiple tasks at once.
        
        Args:
            task_ids: List of task UUIDs
            user_id: UUID of the task owner
            
        Returns:
            dict: Results with success count and errors
        """
        results = {'deleted': [], 'failed': []}
        
        for task_id in task_ids:
            try:
                task = db.session.get(Task, task_id)
                if task and task.user_id == user_id:
                    # Create history entry before deletion
                    history = TaskHistory(
                        task_id=task_id,
                        action=HistoryAction.DELETE,
                        user_id=user_id
                    )
                    history.set_field_changes({
                        'deleted_task': {'title': task.title, 'id': task.id}
                    })
                    db.session.add(history)
                    
                    db.session.delete(task)
                    results['deleted'].append(task_id)
                else:
                    results['failed'].append({'id': task_id, 'error': 'Task not found'})
            except Exception as e:
                results['failed'].append({'id': task_id, 'error': str(e)})
        
        db.session.commit()
        return results
