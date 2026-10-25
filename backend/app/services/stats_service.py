"""
Stats Service

Business logic layer for dashboard statistics and task analytics.
Provides aggregation methods for task counts, overdue tasks, priority distribution,
and other dashboard metrics.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import func, and_, or_, case
from sqlalchemy.orm import Session
from ..extensions import db
from ..models import Task, TaskStatus, TaskPriority, Category, TaskHistory, HistoryAction


class StatsServiceError(Exception):
    """Base exception for stats service errors."""
    pass


class StatsService:
    """Service class for dashboard statistics and task analytics."""
    
    @staticmethod
    def get_dashboard_stats(user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive dashboard statistics for a user.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            dict: Dashboard statistics including task counts, overdue tasks,
                  priority distribution, and recent activity
        """
        stats = {
            'total_tasks': StatsService.get_total_task_count(user_id),
            'tasks_by_status': StatsService.get_tasks_by_status(user_id),
            'tasks_by_priority': StatsService.get_tasks_by_priority(user_id),
            'overdue_tasks': StatsService.get_overdue_tasks_count(user_id),
            'tasks_due_soon': StatsService.get_tasks_due_soon_count(user_id),
            'category_distribution': StatsService.get_category_distribution(user_id),
            'recent_activity': StatsService.get_recent_activity(user_id),
            'completion_rate': StatsService.get_completion_rate(user_id),
            'productivity_trend': StatsService.get_productivity_trend(user_id)
        }
        
        return stats
    
    @staticmethod
    def get_total_task_count(user_id: str) -> int:
        """
        Get total number of tasks for a user.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            int: Total task count
        """
        from sqlalchemy import select, func
        return db.session.execute(
            select(func.count(Task.id)).where(Task.user_id == user_id)
        ).scalar()
    
    @staticmethod
    def get_tasks_by_status(user_id: str) -> Dict[str, int]:
        """
        Get task counts grouped by status.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            dict: Task counts by status (active, completed, archived)
        """
        from sqlalchemy import select, func
        result = db.session.execute(
            select(Task.status, func.count(Task.id).label('count'))
            .where(Task.user_id == user_id)
            .group_by(Task.status)
        ).all()
        
        # Initialize with all statuses at 0
        status_counts: Dict[str, int] = {
            TaskStatus.ACTIVE.value: 0,
            TaskStatus.COMPLETED.value: 0,
            TaskStatus.ARCHIVED.value: 0
        }
        
        # Update with actual counts
        for task_status, count in result:
            if hasattr(task_status, 'value'):
                status_counts[task_status.value] = count
            else:
                status_counts[str(task_status)] = count
        
        return status_counts
    
    @staticmethod
    def get_tasks_by_priority(user_id: str) -> Dict[str, int]:
        """
        Get task counts grouped by priority.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            dict: Task counts by priority (low, medium, high)
        """
        from sqlalchemy import select, func
        result = db.session.execute(
            select(Task.priority, func.count(Task.id).label('count'))
            .where(Task.user_id == user_id)
            .group_by(Task.priority)
        ).all()
        
        # Initialize with all priorities at 0
        priority_counts: Dict[str, int] = {
            TaskPriority.LOW.value: 0,
            TaskPriority.MEDIUM.value: 0,
            TaskPriority.HIGH.value: 0
        }
        
        # Update with actual counts
        for task_priority, count in result:
            if hasattr(task_priority, 'value'):
                priority_counts[task_priority.value] = count
            else:
                priority_counts[str(task_priority)] = count
        
        return priority_counts
    
    @staticmethod
    def get_overdue_tasks_count(user_id: str) -> int:
        """
        Get count of overdue tasks for a user.
        
        A task is overdue if:
        - It has a due date in the past
        - Its status is not completed
        
        Args:
            user_id: UUID of the user
            
        Returns:
            int: Number of overdue tasks
        """
        now = datetime.utcnow()
        
        from sqlalchemy import select, func, and_
        return db.session.execute(
            select(func.count(Task.id)).where(
                and_(
                    Task.user_id == user_id,
                    Task.due_date < now,
                    Task.status != TaskStatus.COMPLETED,
                    Task.due_date.isnot(None)
                )
            )
        ).scalar()
    
    @staticmethod
    def get_overdue_tasks(user_id: str, limit: int = 10) -> List[Task]:
        """
        Get list of overdue tasks for a user.
        
        Args:
            user_id: UUID of the user
            limit: Maximum number of tasks to return
            
        Returns:
            list: Overdue tasks ordered by due date
        """
        now = datetime.utcnow()
        
        from sqlalchemy import select, and_
        return db.session.execute(
            select(Task).where(
                and_(
                    Task.user_id == user_id,
                    Task.due_date < now,
                    Task.status != TaskStatus.COMPLETED,
                    Task.due_date.isnot(None)
                )
            ).order_by(Task.due_date.asc()).limit(limit)
        ).scalars().all()
    
    @staticmethod
    def get_tasks_due_soon_count(user_id: str, days: int = 7) -> int:
        """
        Get count of tasks due within the specified number of days.
        
        Args:
            user_id: UUID of the user
            days: Number of days to look ahead (default: 7)
            
        Returns:
            int: Number of tasks due soon
        """
        now = datetime.utcnow()
        future = now + timedelta(days=days)
        
        from sqlalchemy import select, func, and_
        return db.session.execute(
            select(func.count(Task.id)).where(
                and_(
                    Task.user_id == user_id,
                    Task.due_date >= now,
                    Task.due_date <= future,
                    Task.status != TaskStatus.COMPLETED,
                    Task.due_date.isnot(None)
                )
            )
        ).scalar()
    
    @staticmethod
    def get_tasks_due_soon(user_id: str, days: int = 7, limit: int = 10) -> List[Task]:
        """
        Get list of tasks due within the specified number of days.
        
        Args:
            user_id: UUID of the user
            days: Number of days to look ahead (default: 7)
            limit: Maximum number of tasks to return
            
        Returns:
            list: Tasks due soon ordered by due date
        """
        now = datetime.utcnow()
        future = now + timedelta(days=days)
        
        from sqlalchemy import select, and_
        return db.session.execute(
            select(Task).where(
                and_(
                    Task.user_id == user_id,
                    Task.due_date >= now,
                    Task.due_date <= future,
                    Task.status != TaskStatus.COMPLETED,
                    Task.due_date.isnot(None)
                )
            ).order_by(Task.due_date.asc()).limit(limit)
        ).scalars().all()
    
    @staticmethod
    def get_category_distribution(user_id: str) -> List[Dict[str, Any]]:
        """
        Get task distribution across categories.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            list: Category distribution with task counts
        """
        from ..models import TaskTag
        
        from sqlalchemy import select, func, outerjoin
        # Get all categories for the user with task counts
        result = db.session.execute(
            select(
                Category.id,
                Category.name,
                Category.color,
                func.count(TaskTag.id).label('task_count')
            ).outerjoin(TaskTag, Category.id == TaskTag.category_id)
            .where(Category.user_id == user_id)
            .group_by(Category.id, Category.name, Category.color)
            .order_by(func.count(TaskTag.id).desc())
        ).all()
        
        return [
            {
                'id': cat_id,
                'name': name,
                'color': color,
                'task_count': task_count
            }
            for cat_id, name, color, task_count in result
        ]
    
    @staticmethod
    def get_recent_activity(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent task activity for a user.
        
        Args:
            user_id: UUID of the user
            limit: Maximum number of activities to return
            
        Returns:
            list: Recent activity entries
        """
        from sqlalchemy import select
        activities = db.session.execute(
            select(TaskHistory).where(TaskHistory.user_id == user_id)
            .order_by(TaskHistory.timestamp.desc())
            .limit(limit)
        ).scalars().all()
        
        return [
            {
                'id': activity.id,
                'task_id': activity.task_id,
                'action': activity.action,
                'timestamp': activity.timestamp.isoformat() if activity.timestamp else None,
                'field_changes': activity.get_field_changes()
            }
            for activity in activities
        ]
    
    @staticmethod
    def get_completion_rate(user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Calculate task completion rate over a period.
        
        Args:
            user_id: UUID of the user
            days: Number of days to analyze (default: 30)
            
        Returns:
            dict: Completion statistics
        """
        since = datetime.utcnow() - timedelta(days=days)
        
        from sqlalchemy import select, func, and_
        # Get tasks created in the period
        created_count = db.session.execute(
            select(func.count(Task.id)).where(
                and_(Task.user_id == user_id, Task.created_at >= since)
            )
        ).scalar()
        
        # Get tasks completed in the period
        completed_count = db.session.execute(
            select(func.count(TaskHistory.id)).where(
                and_(
                    TaskHistory.user_id == user_id,
                    TaskHistory.action == HistoryAction.COMPLETE,
                    TaskHistory.timestamp >= since
                )
            )
        ).scalar()
        
        # Calculate rate
        rate = (completed_count / created_count * 100) if created_count > 0 else 0
        
        return {
            'period_days': days,
            'tasks_created': created_count,
            'tasks_completed': completed_count,
            'completion_rate': round(rate, 2),
            'completion_percentage': f"{round(rate, 1)}%"
        }
    
    @staticmethod
    def get_productivity_trend(user_id: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get daily task completion trend for the specified period.
        
        Args:
            user_id: UUID of the user
            days: Number of days to analyze (default: 7)
            
        Returns:
            list: Daily completion counts
        """
        since = datetime.utcnow() - timedelta(days=days)
        
        from sqlalchemy import select, func, and_
        # Get completions grouped by day
        result = db.session.execute(
            select(
                func.date(TaskHistory.timestamp).label('date'),
                func.count(TaskHistory.id).label('count')
            ).where(
                and_(
                    TaskHistory.user_id == user_id,
                    TaskHistory.action == HistoryAction.COMPLETE,
                    TaskHistory.timestamp >= since
                )
            ).group_by(func.date(TaskHistory.timestamp))
            .order_by(func.date(TaskHistory.timestamp).asc())
        ).all()
        
        # Build a complete list with all days
        trend = []
        for i in range(days):
            date = (datetime.utcnow() - timedelta(days=days-1-i)).date()
            count = next((r[1] for r in result if r[0] == date), 0)
            trend.append({
                'date': date.isoformat(),
                'completed': count
            })
        
        return trend
    
    @staticmethod
    def get_priority_breakdown(user_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed breakdown of tasks by priority.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            dict: Priority breakdown with counts and percentages
        """
        from sqlalchemy import select, func
        total = db.session.execute(
            select(func.count(Task.id)).where(Task.user_id == user_id)
        ).scalar()
        
        if total == 0:
            return {
                'low': {'count': 0, 'percentage': 0},
                'medium': {'count': 0, 'percentage': 0},
                'high': {'count': 0, 'percentage': 0}
            }
        
        by_priority = StatsService.get_tasks_by_priority(user_id)
        
        return {
            priority: {
                'count': count,
                'percentage': round(count / total * 100, 2) if total > 0 else 0
            }
            for priority, count in by_priority.items()
        }
    
    @staticmethod
    def get_status_breakdown(user_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed breakdown of tasks by status.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            dict: Status breakdown with counts and percentages
        """
        from sqlalchemy import select, func
        total = db.session.execute(
            select(func.count(Task.id)).where(Task.user_id == user_id)
        ).scalar()
        
        if total == 0:
            return {
                'active': {'count': 0, 'percentage': 0},
                'completed': {'count': 0, 'percentage': 0},
                'archived': {'count': 0, 'percentage': 0}
            }
        
        by_status = StatsService.get_tasks_by_status(user_id)
        
        return {
            status: {
                'count': count,
                'percentage': round(count / total * 100, 2) if total > 0 else 0
            }
            for status, count in by_status.items()
        }
    
    @staticmethod
    def get_quick_stats(user_id: str) -> Dict[str, Any]:
        """
        Get quick overview statistics for dashboard widgets.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            dict: Quick stats summary
        """
        now = datetime.utcnow()
        
        from sqlalchemy import select, func
        # Active tasks
        active_count = db.session.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.ACTIVE
            )
        ).scalar()
        
        from sqlalchemy import select, func, and_
        # Completed today
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        completed_today = db.session.execute(
            select(func.count(TaskHistory.id)).where(
                and_(
                    TaskHistory.user_id == user_id,
                    TaskHistory.action == HistoryAction.COMPLETE,
                    TaskHistory.timestamp >= today_start
                )
            )
        ).scalar()
        
        # Overdue tasks
        overdue_count = db.session.execute(
            select(func.count(Task.id)).where(
                and_(
                    Task.user_id == user_id,
                    Task.due_date < now,
                    Task.status != TaskStatus.COMPLETED,
                    Task.due_date.isnot(None)
                )
            )
        ).scalar()
        
        # High priority tasks
        high_priority_count = db.session.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.priority == TaskPriority.HIGH,
                Task.status == TaskStatus.ACTIVE
            )
        ).scalar()
        
        return {
            'active_tasks': active_count,
            'completed_today': completed_today,
            'overdue_tasks': overdue_count,
            'high_priority_tasks': high_priority_count
        }
