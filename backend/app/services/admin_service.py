"""
Admin Service

Business logic layer for administrative operations including user lifecycle management,
system metrics aggregation, and system health monitoring.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import func, desc, asc, and_, or_
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models.user import User
from ..models.user_session import UserSession
from ..models.task import Task, TaskStatus
from ..models.category import Category
from ..models.task_history import TaskHistory


class AdminServiceError(Exception):
    """Base exception for admin service errors."""
    
    def __init__(self, message: str, status_code: int = 400, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or 'ADMIN_ERROR'
        super().__init__(self.message)


class UserNotFoundError(AdminServiceError):
    """Raised when a user is not found."""
    
    def __init__(self, user_id: str):
        super().__init__(
            message=f"User {user_id} not found",
            status_code=404,
            error_code='USER_NOT_FOUND'
        )


class CannotDeleteAdminError(AdminServiceError):
    """Raised when attempting to delete the last admin user."""
    
    def __init__(self):
        super().__init__(
            message="Cannot delete the last admin user",
            status_code=403,
            error_code='CANNOT_DELETE_LAST_ADMIN'
        )


class AdminService:
    """
    Service class for administrative operations.
    
    Provides methods for:
    - User lifecycle management (activation/deactivation, hard delete)
    - System metrics aggregation
    - System health monitoring
    """
    
    @staticmethod
    def get_users(
        page: int = 1,
        per_page: int = 20,
        is_active: Optional[bool] = None,
        is_admin: Optional[bool] = None,
        search_query: Optional[str] = None,
        sort_by: str = 'created_at',
        sort_order: str = 'desc'
    ) -> Dict[str, Any]:
        """
        Get paginated list of users with filtering and sorting.
        
        Args:
            page: Page number (1-based)
            per_page: Items per page
            is_active: Filter by active status
            is_admin: Filter by admin status
            search_query: Search in username and email
            sort_by: Field to sort by
            sort_order: 'asc' or 'desc'
            
        Returns:
            dict: Paginated results with users and metadata
        """
        from sqlalchemy import select
        
        # Build base query
        stmt = select(User)
        
        # Apply filters
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        
        if is_admin is not None:
            stmt = stmt.where(User.is_admin == is_admin)
        
        if search_query:
            search_pattern = f"%{search_query}%"
            stmt = stmt.where(
                or_(
                    User.username.ilike(search_pattern),
                    User.email.ilike(search_pattern)
                )
            )
        
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.session.execute(count_stmt).scalar() or 0
        
        # Apply sorting
        sort_column = getattr(User, sort_by, User.created_at)
        if sort_order == 'desc':
            stmt = stmt.order_by(desc(sort_column))
        else:
            stmt = stmt.order_by(asc(sort_column))
        
        # Apply pagination
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        users = db.session.execute(stmt).scalars().all()
        
        # Get additional stats for each user
        user_data = []
        for user in users:
            user_dict = user.to_dict(include_sensitive=False)
            
            # Add task counts
            task_counts = db.session.query(
                Task.status,
                func.count(Task.id)
            ).filter(
                Task.user_id == user.id
            ).group_by(
                Task.status
            ).all()
            
            user_dict['task_stats'] = {
                'total': sum(count for _, count in task_counts),
                'active': sum(count for status, count in task_counts if status == TaskStatus.ACTIVE),
                'completed': sum(count for status, count in task_counts if status == TaskStatus.COMPLETED),
                'archived': sum(count for status, count in task_counts if status == TaskStatus.ARCHIVED)
            }
            
            # Add session count
            user_dict['active_sessions'] = db.session.query(
                func.count(UserSession.id)
            ).filter(
                UserSession.user_id == user.id,
                UserSession.is_active() == True
            ).scalar() or 0
            
            user_data.append(user_dict)
        
        return {
            'users': user_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        }
    
    @staticmethod
    def get_user_by_id(user_id: str) -> Dict[str, Any]:
        """
        Get detailed user information by ID.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            dict: User data with statistics
            
        Raises:
            UserNotFoundError: If user not found
        """
        user = db.session.get(User, user_id)
        
        if not user:
            raise UserNotFoundError(user_id)
        
        user_dict = user.to_dict(include_sensitive=False)
        
        # Add comprehensive stats
        user_dict['stats'] = AdminService._get_user_stats(user_id)
        
        # Add recent sessions
        recent_sessions = db.session.query(UserSession).filter(
            UserSession.user_id == user_id
        ).order_by(
            desc(UserSession.created_at)
        ).limit(10).all()
        
        user_dict['recent_sessions'] = [
            session.to_dict(include_tokens=False) for session in recent_sessions
        ]
        
        return user_dict
    
    @staticmethod
    def _get_user_stats(user_id: str) -> Dict[str, Any]:
        """
        Get statistics for a specific user.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            dict: User statistics
        """
        # Task counts by status
        task_counts = db.session.query(
            Task.status,
            func.count(Task.id)
        ).filter(
            Task.user_id == user_id
        ).group_by(
            Task.status
        ).all()
        
        task_stats = {
            'total': sum(count for _, count in task_counts),
            'active': sum(count for status, count in task_counts if status == TaskStatus.ACTIVE),
            'completed': sum(count for status, count in task_counts if status == TaskStatus.COMPLETED),
            'archived': sum(count for status, count in task_counts if status == TaskStatus.ARCHIVED)
        }
        
        # Category count
        category_count = db.session.query(
            func.count(Category.id)
        ).filter(
            Category.user_id == user_id
        ).scalar() or 0
        
        # Get active sessions for this user
        active_sessions = db.session.query(
            func.count(UserSession.id)
        ).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True
        ).scalar() or 0
        
        # Recent activity (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_activity = db.session.query(
            func.count(TaskHistory.id)
        ).filter(
            TaskHistory.timestamp >= thirty_days_ago
        ).scalar() or 0
        
        return {
            'tasks': task_stats,
            'categories': category_count,
            'active_sessions': active_sessions,
            'recent_activity': recent_activity
        }
    
    @staticmethod
    def activate_user(user_id: str) -> Dict[str, Any]:
        """
        Activate a user account.
        
        Args:
            user_id: UUID of the user to activate
            
        Returns:
            dict: Updated user data
            
        Raises:
            UserNotFoundError: If user not found
        """
        user = db.session.get(User, user_id)
        
        if not user:
            raise UserNotFoundError(user_id)
        
        if user.is_active:
            return {
                'success': True,
                'message': 'User is already active',
                'user': user.to_dict(include_sensitive=False)
            }
        
        user.is_active = True
        # User model doesn't have updated_at field, changes are tracked via session
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise AdminServiceError(
                message=f"Failed to activate user: {str(e)}",
                status_code=500,
                error_code='ACTIVATION_FAILED'
            )
        
        return {
            'success': True,
            'message': 'User activated successfully',
            'user': user.to_dict(include_sensitive=False)
        }
    
    @staticmethod
    def deactivate_user(user_id: str) -> Dict[str, Any]:
        """
        Deactivate a user account.
        
        Invalidates all active sessions for the user.
        
        Args:
            user_id: UUID of the user to deactivate
            
        Returns:
            dict: Updated user data
            
        Raises:
            UserNotFoundError: If user not found
        """
        user = db.session.get(User, user_id)
        
        if not user:
            raise UserNotFoundError(user_id)
        
        if not user.is_active:
            return {
                'success': True,
                'message': 'User is already inactive',
                'user': user.to_dict(include_sensitive=False)
            }
        
        user.is_active = False
        
        # Invalidate all sessions
        sessions = db.session.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active() == True
        ).all()
        
        for session in sessions:
            session.invalidate()
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise AdminServiceError(
                message=f"Failed to deactivate user: {str(e)}",
                status_code=500,
                error_code='DEACTIVATION_FAILED'
            )
        
        return {
            'success': True,
            'message': 'User deactivated successfully',
            'sessions_invalidated': len(sessions),
            'user': user.to_dict(include_sensitive=False)
        }
    
    @staticmethod
    def toggle_user_activation(user_id: str) -> Dict[str, Any]:
        """
        Toggle user activation status.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            dict: Updated user data
            
        Raises:
            UserNotFoundError: If user not found
        """
        user = db.session.get(User, user_id)
        
        if not user:
            raise UserNotFoundError(user_id)
        
        if user.is_active:
            return AdminService.deactivate_user(user_id)
        else:
            return AdminService.activate_user(user_id)
    
    @staticmethod
    def hard_delete_user(user_id: str) -> Dict[str, Any]:
        """
        Permanently delete a user and all associated data.
        
        This operation:
        - Deletes all user sessions
        - Deletes all tasks (cascade deletes task_tags and task_history)
        - Deletes all categories
        - Deletes the user record
        
        Args:
            user_id: UUID of the user to delete
            
        Returns:
            dict: Deletion summary
            
        Raises:
            UserNotFoundError: If user not found
            CannotDeleteAdminError: If attempting to delete the last admin
        """
        user = db.session.get(User, user_id)
        
        if not user:
            raise UserNotFoundError(user_id)
        # Check if user is the last admin
        # Get admin users
        admin_users = db.session.query(
            func.count(User.id)
        ).filter(
            User.is_admin == True,
            User.is_active == True
        ).scalar() or 0
            
            if admin_count <= 1:
                raise CannotDeleteAdminError()
        
        # Collect deletion stats before deletion
        task_count = db.session.query(
            func.count(Task.id)
        ).filter(
            Task.user_id == user_id
        ).scalar() or 0
        
        category_count = db.session.query(
            func.count(Category.id)
        ).filter(
            Category.user_id == user_id
        ).scalar() or 0
        
        session_count = db.session.query(
            func.count(UserSession.id)
        ).filter(
            UserSession.user_id == user_id
        ).scalar() or 0
        
        # Delete the user - cascade will handle related records
        try:
            db.session.delete(user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise AdminServiceError(
                message=f"Failed to delete user: {str(e)}",
                status_code=500,
                error_code='DELETION_FAILED'
            )
        
        return {
            'success': True,
            'message': 'User deleted successfully',
            'deleted': {
                'user_id': user_id,
                'tasks': task_count,
                'categories': category_count,
                'sessions': session_count
            }
        }
    
    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """
        Get comprehensive system metrics.
        
        Returns:
            dict: System-wide statistics
        """
        now = datetime.utcnow()
        
        # User metrics
        total_users = db.session.query(func.count(User.id)).scalar() or 0
        active_users = db.session.query(func.count(User.id)).filter(
            User.is_active == True
        ).scalar() or 0
        inactive_users = total_users - active_users
        admin_users = db.session.query(func.count(User.id)).filter(
            User.is_admin == True
        ).scalar() or 0
        
        # New users in last 7 and 30 days
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)
        
        new_users_7d = db.session.query(func.count(User.id)).filter(
            User.created_at >= seven_days_ago
        ).scalar() or 0
        
        new_users_30d = db.session.query(func.count(User.id)).filter(
            User.created_at >= thirty_days_ago
        ).scalar() or 0
        
        # Task metrics
        total_tasks = db.session.query(func.count(Task.id)).scalar() or 0
        
        task_status_counts = db.session.query(
            Task.status,
            func.count(Task.id)
        ).group_by(Task.status).all()
        
        tasks_by_status = {
            status.value if hasattr(status, 'value') else status: count
            for status, count in task_status_counts
        }
        
        # Task priority distribution
        task_priority_counts = db.session.query(
            Task.priority,
            func.count(Task.id)
        ).group_by(Task.priority).all()
        
        tasks_by_priority = {
            priority.value if hasattr(priority, 'value') else priority: count
            for priority, count in task_priority_counts
        }
        # Get overdue tasks
        overdue_tasks = db.session.query(
            Task
        ).filter(
            Task.due_date < datetime.utcnow(),
            Task.status != TaskStatus.COMPLETED
        ).count()
        # Tasks created recently
        tasks_created_7d = db.session.query(func.count(Task.id)).filter(
            Task.created_at >= seven_days_ago
        ).scalar() or 0
        
        tasks_created_30d = db.session.query(func.count(Task.id)).filter(
            Task.created_at >= thirty_days_ago
        ).scalar() or 0
        
        # Category metrics
        total_categories = db.session.query(func.count(Category.id)).scalar() or 0
        
        # Session metrics
        total_sessions = db.session.query(func.count(UserSession.id)).scalar() or 0
        active_sessions = db.session.query(func.count(UserSession.id)).filter(
            UserSession.is_valid == True,
            UserSession.expires_at > now
        ).scalar() or 0
        expired_sessions = total_sessions - active_sessions
        
        # Recent activity (task history)
        recent_activity = db.session.query(func.count(TaskHistory.id)).filter(
            TaskHistory.timestamp >= seven_days_ago
        ).scalar() or 0
        
        # Activity by action type
        activity_by_action = db.session.query(
            TaskHistory.action,
            func.count(TaskHistory.id)
        ).filter(
            TaskHistory.timestamp >= seven_days_ago
        ).group_by(TaskHistory.action).all()
        
        activity_breakdown = {
            action: count for action, count in activity_by_action
        }
        
        return {
            'users': {
                'total': total_users,
                'active': active_users,
                'inactive': inactive_users,
                'admins': admin_users,
                'new_last_7_days': new_users_7d,
                'new_last_30_days': new_users_30d
            },
            'tasks': {
                'total': total_tasks,
                'by_status': tasks_by_status,
                'by_priority': tasks_by_priority,
                'overdue': overdue_tasks,
                'created_last_7_days': tasks_created_7d,
                'created_last_30_days': tasks_created_30d
            },
            'categories': {
                'total': total_categories
            },
            'sessions': {
                'total': total_sessions,
                'active': active_sessions,
                'expired': expired_sessions
            },
            'activity': {
                'total_last_7_days': recent_activity,
                'by_action': activity_breakdown
            },
            'generated_at': now.isoformat()
        }
    
    @staticmethod
    def get_system_health() -> Dict[str, Any]:
        """
        Get detailed system health status.
        
        Returns:
            dict: System health information
        """
        now = datetime.utcnow()
        health_data = {
            'status': 'healthy',
            'timestamp': now.isoformat(),
            'checks': {}
        }
        
        # Database connectivity check
        try:
            db.session.execute('SELECT 1')
            health_data['checks']['database'] = {
                'status': 'pass',
                'message': 'Database connection successful'
            }
        except Exception as e:
            health_data['checks']['database'] = {
                'status': 'fail',
                'message': f'Database connection failed: {str(e)}'
            }
            health_data['status'] = 'unhealthy'
        
        # Database statistics
        try:
            table_stats = {}
            
            # Get row counts for main tables
            table_stats['users'] = db.session.query(func.count(User.id)).scalar() or 0
            table_stats['tasks'] = db.session.query(func.count(Task.id)).scalar() or 0
            table_stats['categories'] = db.session.query(func.count(Category.id)).scalar() or 0
            table_stats['sessions'] = db.session.query(func.count(UserSession.id)).scalar() or 0
            table_stats['task_history'] = db.session.query(func.count(TaskHistory.id)).scalar() or 0
            
            health_data['checks']['database']['stats'] = table_stats
        except Exception as e:
            health_data['checks']['database']['stats_error'] = str(e)
        
        # Session health check
        try:
            expired_sessions = db.session.query(func.count(UserSession.id)).filter(
                UserSession.expires_at < now,
                UserSession.is_valid == True
            ).scalar() or 0
            
            health_data['checks']['sessions'] = {
                'status': 'pass',
                'expired_but_valid': expired_sessions,
                'message': f'{expired_sessions} expired sessions need cleanup' if expired_sessions > 0 else 'All sessions healthy'
            }
            
            if expired_sessions > 100:
                health_data['checks']['sessions']['status'] = 'warn'
                health_data['status'] = 'degraded'
        except Exception as e:
            health_data['checks']['sessions'] = {
                'status': 'fail',
                'message': f'Session check failed: {str(e)}'
            }
        
        # User health check
        try:
            users_without_tasks = db.session.query(User.id).outerjoin(
                Task, User.id == Task.user_id
            ).group_by(User.id).having(
                func.count(Task.id) == 0
            ).count()
            
            health_data['checks']['users'] = {
                'status': 'pass',
                'users_without_tasks': users_without_tasks
            }
        except Exception as e:
            health_data['checks']['users'] = {
                'status': 'fail',
                'message': f'User check failed: {str(e)}'
            }
        
        # Task health check
        try:
            orphaned_tasks = db.session.query(func.count(Task.id)).filter(
                ~Task.user_id.in_(
                    db.session.query(User.id)
                )
            ).scalar() or 0
            
            health_data['checks']['tasks'] = {
                'status': 'pass',
                'orphaned': orphaned_tasks
            }
            
            if orphaned_tasks > 0:
                health_data['checks']['tasks']['status'] = 'warn'
                if health_data['status'] == 'healthy':
                    health_data['status'] = 'degraded'
        except Exception as e:
            health_data['checks']['tasks'] = {
                'status': 'fail',
                'message': f'Task check failed: {str(e)}'
            }
        
        return health_data
    
    @staticmethod
    def cleanup_expired_sessions() -> Dict[str, Any]:
        """
        Clean up expired sessions from the database.
        
        Returns:
            dict: Cleanup results
        """
        now = datetime.utcnow()
        
        # Find expired sessions
        expired_sessions = db.session.query(UserSession).filter(
            UserSession.expires_at < now,
            UserSession.is_valid == True
        ).all()
        
        count = 0
        for session in expired_sessions:
            session.invalidate()
            count += 1
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise AdminServiceError(
                message=f"Failed to cleanup sessions: {str(e)}",
                status_code=500,
                error_code='CLEANUP_FAILED'
            )
        
        return {
            'success': True,
            'message': f'Cleaned up {count} expired sessions',
            'sessions_cleaned': count
        }
    
    @staticmethod
    def get_recent_activity(
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get recent system activity from task history.
        
        Args:
            limit: Number of records to return
            offset: Offset for pagination
            
        Returns:
            dict: Recent activity records
        """
        from sqlalchemy import select
        
        # Build query with user info
        stmt = select(
            TaskHistory,
            User.username,
            Task.title
        ).outerjoin(
            User, TaskHistory.user_id == User.id
        ).outerjoin(
            Task, TaskHistory.task_id == Task.id
        ).order_by(
            desc(TaskHistory.timestamp)
        ).limit(limit).offset(offset)
        
        results = db.session.execute(stmt).all()
        
        activity_records = []
        for history, username, task_title in results:
            record = history.to_dict()
            record['username'] = username
            record['task_title'] = task_title
            activity_records.append(record)
        
        # Get total count
        total = db.session.query(func.count(TaskHistory.id)).scalar() or 0
        
        return {
            'activity': activity_records,
            'total': total,
            'limit': limit,
            'offset': offset
        }
