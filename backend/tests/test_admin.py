"""
Admin API Tests

Comprehensive pytest tests for admin endpoints including:
- User listing with pagination and filtering
- User activation/deactivation
- User hard delete with cascade
- System health checks
- System metrics aggregation
- Admin-only authorization enforcement
"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.user_session import UserSession
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.category import Category
from app.models.task_history import TaskHistory, HistoryAction
from app.services.auth_service import AuthService


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def admin_user(app):
    """Create an admin user."""
    with app.app_context():
        user = User(
            username='admin_test',
            email='admin@test.com',
            is_admin=True,
            is_active=True
        )
        user.set_password('admin123')
        db.session.add(user)
        db.session.commit()
        return user


@pytest.fixture
def regular_user(app):
    """Create a regular user."""
    with app.app_context():
        user = User(
            username='regular_test',
            email='regular@test.com',
            is_admin=False,
            is_active=True
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        return user


@pytest.fixture
def inactive_user(app):
    """Create an inactive user."""
    with app.app_context():
        user = User(
            username='inactive_test',
            email='inactive@test.com',
            is_admin=False,
            is_active=False
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        return user


@pytest.fixture
def admin_token(client, admin_user):
    """Get admin access token."""
    response = client.post('/api/auth/login', json={
        'username': 'admin_test',
        'password': 'admin123'
    })
    return response.json['data']['access_token']


@pytest.fixture
def regular_token(client, regular_user):
    """Get regular user access token."""
    response = client.post('/api/auth/login', json={
        'username': 'regular_test',
        'password': 'password123'
    })
    return response.json['data']['access_token']


@pytest.fixture
def sample_data(app, regular_user):
    """Create sample tasks and categories for testing."""
    with app.app_context():
        # Create categories
        cat1 = Category(name='Work', color='#FF5733', user_id=regular_user.id)
        cat2 = Category(name='Personal', color='#33FF57', user_id=regular_user.id)
        db.session.add_all([cat1, cat2])
        db.session.flush()
        
        # Create tasks
        task1 = Task(
            user_id=regular_user.id,
            title='Active Task',
            description='Test description',
            status=TaskStatus.ACTIVE,
            priority=TaskPriority.HIGH,
            due_date=datetime.utcnow() + timedelta(days=1),
            version=1
        )
        task2 = Task(
            user_id=regular_user.id,
            title='Completed Task',
            description='Completed test',
            status=TaskStatus.COMPLETED,
            priority=TaskPriority.MEDIUM,
            version=1
        )
        task3 = Task(
            user_id=regular_user.id,
            title='Archived Task',
            description='Archived test',
            status=TaskStatus.ARCHIVED,
            priority=TaskPriority.LOW,
            version=1
        )
        db.session.add_all([task1, task2, task3])
        db.session.flush()
        
        # Create task history
        history = TaskHistory(
            task_id=task1.id,
            action=HistoryAction.CREATE,
            user_id=regular_user.id
        )
        db.session.add(history)
        db.session.commit()
        
        return {'categories': [cat1, cat2], 'tasks': [task1, task2, task3]}


# =============================================================================
# Authorization Tests
# =============================================================================

class TestAdminAuthorization:
    """Test admin-only access enforcement."""
    
    def test_list_users_requires_auth(self, client):
        """Test that listing users requires authentication."""
        response = client.get('/api/admin/users')
        assert response.status_code == 401
        assert response.json['success'] is False
        assert 'Unauthorized' in response.json['error'] or 'Authentication required' in response.json['message']
    
    def test_list_users_requires_admin(self, client, regular_token):
        """Test that listing users requires admin privileges."""
        response = client.get(
            '/api/admin/users',
            headers={'Authorization': f'Bearer {regular_token}'}
        )
        assert response.status_code == 403
        assert response.json['success'] is False
        assert 'Forbidden' in response.json['error'] or 'Admin privileges required' in response.json['message']
    
    def test_get_user_requires_admin(self, client, regular_token, regular_user):
        """Test that getting user details requires admin."""
        response = client.get(
            f'/api/admin/users/{regular_user.id}',
            headers={'Authorization': f'Bearer {regular_token}'}
        )
        assert response.status_code == 403
    
    def test_update_user_requires_admin(self, client, regular_token, regular_user):
        """Test that updating user requires admin."""
        response = client.put(
            f'/api/admin/users/{regular_user.id}',
            headers={'Authorization': f'Bearer {regular_token}'},
            json={'is_active': False}
        )
        assert response.status_code == 403
    
    def test_delete_user_requires_admin(self, client, regular_token, regular_user):
        """Test that deleting user requires admin."""
        response = client.delete(
            f'/api/admin/users/{regular_user.id}',
            headers={'Authorization': f'Bearer {regular_token}'}
        )
        assert response.status_code == 403
    
    def test_health_requires_admin(self, client, regular_token):
        """Test that health check requires admin."""
        response = client.get(
            '/api/admin/health',
            headers={'Authorization': f'Bearer {regular_token}'}
        )
        assert response.status_code == 403
    
    def test_metrics_requires_admin(self, client, regular_token):
        """Test that metrics requires admin."""
        response = client.get(
            '/api/admin/metrics',
            headers={'Authorization': f'Bearer {regular_token}'}
        )
        assert response.status_code == 403


# =============================================================================
# User List Tests
# =============================================================================

class TestAdminUserList:
    """Test user listing endpoints."""
    
    def test_list_users_success(self, client, admin_token, admin_user, regular_user, inactive_user):
        """Test successful user listing."""
        response = client.get(
            '/api/admin/users',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert response.json['success'] is True
        assert 'users' in response.json
        assert 'total' in response.json
        assert response.json['total'] >= 3  # admin + regular + inactive
    
    def test_list_users_pagination(self, client, admin_token):
        """Test user listing with pagination."""
        response = client.get(
            '/api/admin/users?page=1&per_page=2',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert len(response.json['users']) <= 2
        assert response.json['per_page'] == 2
    
    def test_list_users_filter_by_active(self, client, admin_token):
        """Test filtering users by active status."""
        response = client.get(
            '/api/admin/users?is_active=true',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        for user in response.json['users']:
            assert user['is_active'] is True
    
    def test_list_users_filter_by_admin(self, client, admin_token):
        """Test filtering users by admin status."""
        response = client.get(
            '/api/admin/users?is_admin=true',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        for user in response.json['users']:
            assert user['is_admin'] is True
    
    def test_list_users_search(self, client, admin_token):
        """Test searching users."""
        response = client.get(
            '/api/admin/users?search=admin',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        # Should find admin user
        assert any('admin' in user['username'].lower() for user in response.json['users'])
    
    def test_list_users_sorting(self, client, admin_token):
        """Test user sorting."""
        response = client.get(
            '/api/admin/users?sort_by=username&sort_order=asc',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        usernames = [user['username'] for user in response.json['users']]
        assert usernames == sorted(usernames)
    
    def test_list_users_includes_stats(self, client, admin_token, sample_data):
        """Test that user list includes task stats."""
        response = client.get(
            '/api/admin/users',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        for user in response.json['users']:
            assert 'task_stats' in user
            assert 'total' in user['task_stats']
            assert 'active_sessions' in user


# =============================================================================
# User Detail Tests
# =============================================================================

class TestAdminUserDetail:
    """Test user detail endpoint."""
    
    def test_get_user_success(self, client, admin_token, regular_user):
        """Test getting user details."""
        response = client.get(
            f'/api/admin/users/{regular_user.id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert response.json['success'] is True
        assert response.json['user']['id'] == regular_user.id
        assert response.json['user']['username'] == regular_user.username
    
    def test_get_user_not_found(self, client, admin_token):
        """Test getting non-existent user."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f'/api/admin/users/{fake_id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 404
        assert response.json['success'] is False
    
    def test_get_user_includes_stats(self, client, admin_token, regular_user, sample_data):
        """Test that user details include statistics."""
        response = client.get(
            f'/api/admin/users/{regular_user.id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert 'stats' in response.json['user']
        assert 'tasks' in response.json['user']['stats']
        assert 'categories' in response.json['user']['stats']
    
    def test_get_user_includes_sessions(self, client, admin_token, regular_user):
        """Test that user details include recent sessions."""
        response = client.get(
            f'/api/admin/users/{regular_user.id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert 'recent_sessions' in response.json['user']


# =============================================================================
# User Activation Tests
# =============================================================================

class TestAdminUserActivation:
    """Test user activation/deactivation."""
    
    def test_deactivate_user_success(self, client, admin_token, regular_user):
        """Test deactivating a user."""
        response = client.put(
            f'/api/admin/users/{regular_user.id}',
            headers={'Authorization': f'Bearer {admin_token}'},
            json={'is_active': False}
        )
        assert response.status_code == 200
        assert response.json['success'] is True
        assert response.json['user']['is_active'] is False
    
    def test_activate_user_success(self, client, admin_token, inactive_user):
        """Test activating a user."""
        response = client.put(
            f'/api/admin/users/{inactive_user.id}',
            headers={'Authorization': f'Bearer {admin_token}'},
            json={'is_active': True}
        )
        assert response.status_code == 200
        assert response.json['success'] is True
        assert response.json['user']['is_active'] is True
    
    def test_deactivate_user_invalidates_sessions(self, client, app, admin_token, regular_user):
        """Test that deactivating a user invalidates their sessions."""
        # Create a session for the user
        with app.app_context():
            session = UserSession(
                user_id=regular_user.id,
                token='test_token',
                refresh_token='test_refresh',
                expires_at=datetime.utcnow() + timedelta(days=7),
                is_valid=True
            )
            db.session.add(session)
            db.session.commit()
        
        # Deactivate user
        response = client.put(
            f'/api/admin/users/{regular_user.id}',
            headers={'Authorization': f'Bearer {admin_token}'},
            json={'is_active': False}
        )
        assert response.status_code == 200
        
        # Verify session is invalidated
        with app.app_context():
            session = db.session.query(UserSession).filter_by(user_id=regular_user.id).first()
            assert session.is_valid is False
    
    def test_activate_user_not_found(self, client, admin_token):
        """Test activating non-existent user."""
        fake_id = str(uuid.uuid4())
        response = client.put(
            f'/api/admin/users/{fake_id}',
            headers={'Authorization': f'Bearer {admin_token}'},
            json={'is_active': True}
        )
        assert response.status_code == 404
    
    def test_activate_user_missing_field(self, client, admin_token, regular_user):
        """Test activation without is_active field."""
        response = client.put(
            f'/api/admin/users/{regular_user.id}',
            headers={'Authorization': f'Bearer {admin_token}'},
            json={}
        )
        assert response.status_code == 400
        assert 'is_active' in response.json['message'].lower() or 'required' in response.json['message'].lower()


# =============================================================================
# User Delete Tests
# =============================================================================

class TestAdminUserDelete:
    """Test user hard delete with cascade."""
    
    def test_delete_user_success(self, client, app, admin_token, regular_user):
        """Test deleting a user."""
        user_id = regular_user.id
        
        response = client.delete(
            f'/api/admin/users/{user_id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert response.json['success'] is True
        
        # Verify user is deleted
        with app.app_context():
            user = db.session.query(User).filter_by(id=user_id).first()
            assert user is None
    
    def test_delete_user_cascades_to_tasks(self, client, app, admin_token, regular_user, sample_data):
        """Test that deleting a user cascades to tasks."""
        user_id = regular_user.id
        task_ids = [task.id for task in sample_data['tasks']]
        
        response = client.delete(
            f'/api/admin/users/{user_id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        
        # Verify tasks are deleted
        with app.app_context():
            for task_id in task_ids:
                task = db.session.query(Task).filter_by(id=task_id).first()
                assert task is None
    
    def test_delete_user_cascades_to_categories(self, client, app, admin_token, regular_user, sample_data):
        """Test that deleting a user cascades to categories."""
        user_id = regular_user.id
        category_ids = [cat.id for cat in sample_data['categories']]
        
        response = client.delete(
            f'/api/admin/users/{user_id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        
        # Verify categories are deleted
        with app.app_context():
            for cat_id in category_ids:
                category = db.session.query(Category).filter_by(id=cat_id).first()
                assert category is None
    
    def test_delete_user_cascades_to_sessions(self, client, app, admin_token, regular_user):
        """Test that deleting a user cascades to sessions."""
        user_id = regular_user.id
        
        # Create a session
        with app.app_context():
            session = UserSession(
                user_id=user_id,
                token='test_token',
                refresh_token='test_refresh',
                expires_at=datetime.utcnow() + timedelta(days=7),
                is_valid=True
            )
            db.session.add(session)
            db.session.commit()
            session_id = session.id
        
        response = client.delete(
            f'/api/admin/users/{user_id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        
        # Verify session is deleted
        with app.app_context():
            session = db.session.query(UserSession).filter_by(id=session_id).first()
            assert session is None
    
    def test_delete_user_not_found(self, client, admin_token):
        """Test deleting non-existent user."""
        fake_id = str(uuid.uuid4())
        response = client.delete(
            f'/api/admin/users/{fake_id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 404
    
    def test_cannot_delete_last_admin(self, client, app, admin_token, admin_user):
        """Test that the last admin cannot be deleted."""
        # Ensure this is the only admin
        with app.app_context():
            admin_count = db.session.query(User).filter_by(is_admin=True).count()
            if admin_count > 1:
                pytest.skip("Multiple admins exist, cannot test last admin deletion")
        
        response = client.delete(
            f'/api/admin/users/{admin_user.id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 403
        assert 'last admin' in response.json['message'].lower() or 'cannot delete' in response.json['message'].lower()


# =============================================================================
# Health Check Tests
# =============================================================================

class TestAdminHealth:
    """Test system health endpoint."""
    
    def test_health_check_success(self, client, admin_token):
        """Test successful health check."""
        response = client.get(
            '/api/admin/health',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert response.json['success'] is True
        assert 'status' in response.json
        assert 'timestamp' in response.json
        assert 'checks' in response.json
    
    def test_health_check_includes_database_status(self, client, admin_token):
        """Test that health check includes database status."""
        response = client.get(
            '/api/admin/health',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert 'database' in response.json['checks']
        assert 'status' in response.json['checks']['database']
    
    def test_health_check_includes_user_counts(self, client, admin_token):
        """Test that health check includes user counts."""
        response = client.get(
            '/api/admin/health',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert 'users' in response.json['checks']
        assert 'total' in response.json['checks']['users']


# =============================================================================
# Metrics Tests
# =============================================================================

class TestAdminMetrics:
    """Test system metrics endpoint."""
    
    def test_metrics_success(self, client, admin_token):
        """Test successful metrics retrieval."""
        response = client.get(
            '/api/admin/metrics',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert response.json['success'] is True
        assert 'metrics' in response.json
    
    def test_metrics_includes_user_counts(self, client, admin_token):
        """Test that metrics includes user counts."""
        response = client.get(
            '/api/admin/metrics',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert 'users' in response.json['metrics']
        assert 'total' in response.json['metrics']['users']
        assert 'active' in response.json['metrics']['users']
        assert 'admin' in response.json['metrics']['users']
    
    def test_metrics_includes_task_counts(self, client, admin_token, sample_data):
        """Test that metrics includes task counts."""
        response = client.get(
            '/api/admin/metrics',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert 'tasks' in response.json['metrics']
        assert 'total' in response.json['metrics']['tasks']
        assert 'by_status' in response.json['metrics']['tasks']
    
    def test_metrics_includes_recent_activity(self, client, admin_token):
        """Test that metrics includes recent activity."""
        response = client.get(
            '/api/admin/metrics',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert 'recent_activity' in response.json['metrics']
    
    def test_metrics_with_custom_days(self, client, admin_token):
        """Test metrics with custom days parameter."""
        response = client.get(
            '/api/admin/metrics?days=7',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        assert response.json['success'] is True
    
    def test_metrics_invalid_days(self, client, admin_token):
        """Test metrics with invalid days parameter."""
        response = client.get(
            '/api/admin/metrics?days=0',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        # Should still succeed with default value
        assert response.status_code == 200
    
    def test_metrics_days_too_high(self, client, admin_token):
        """Test metrics with days parameter exceeding maximum."""
        response = client.get(
            '/api/admin/metrics?days=500',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        # Should still succeed with clamped value
        assert response.status_code == 200


# =============================================================================
# Integration Tests
# =============================================================================

class TestAdminIntegration:
    """Integration tests for admin workflows."""
    
    def test_full_user_lifecycle(self, client, app, admin_token):
        """Test complete user lifecycle: create, deactivate, activate, delete."""
        # Create a new user
        with app.app_context():
            user = User(
                username='lifecycle_test',
                email='lifecycle@test.com',
                is_admin=False,
                is_active=True
            )
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()
            user_id = user.id
        
        # Deactivate user
        response = client.put(
            f'/api/admin/users/{user_id}',
            headers={'Authorization': f'Bearer {admin_token}'},
            json={'is_active': False}
        )
        assert response.status_code == 200
        assert response.json['user']['is_active'] is False
        
        # Activate user
        response = client.put(
            f'/api/admin/users/{user_id}',
            headers={'Authorization': f'Bearer {admin_token}'},
            json={'is_active': True}
        )
        assert response.status_code == 200
        assert response.json['user']['is_active'] is True
        
        # Delete user
        response = client.delete(
            f'/api/admin/users/{user_id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        
        # Verify deletion
        with app.app_context():
            user = db.session.query(User).filter_by(id=user_id).first()
            assert user is None
    
    def test_user_stats_accuracy(self, client, app, admin_token, regular_user):
        """Test that user statistics are accurate."""
        # Create known quantities of data
        with app.app_context():
            # Create categories
            cat1 = Category(name='Test1', user_id=regular_user.id)
            cat2 = Category(name='Test2', user_id=regular_user.id)
            db.session.add_all([cat1, cat2])
            db.session.flush()
            
            # Create tasks with different statuses
            task1 = Task(user_id=regular_user.id, title='Active', status=TaskStatus.ACTIVE, priority=TaskPriority.MEDIUM, version=1)
            task2 = Task(user_id=regular_user.id, title='Completed', status=TaskStatus.COMPLETED, priority=TaskPriority.MEDIUM, version=1)
            task3 = Task(user_id=regular_user.id, title='Archived', status=TaskStatus.ARCHIVED, priority=TaskPriority.MEDIUM, version=1)
            db.session.add_all([task1, task2, task3])
            db.session.commit()
        
        # Get user details
        response = client.get(
            f'/api/admin/users/{regular_user.id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        
        stats = response.json['user']['stats']
        assert stats['tasks']['total'] == 3
        assert stats['tasks']['active'] == 1
        assert stats['tasks']['completed'] == 1
        assert stats['tasks']['archived'] == 1
        assert stats['categories'] == 2
    
    def test_metrics_reflects_system_state(self, client, admin_token, sample_data):
        """Test that metrics accurately reflect system state."""
        response = client.get(
            '/api/admin/metrics',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert response.status_code == 200
        
        metrics = response.json['metrics']
        
        # Verify task counts
        assert metrics['tasks']['total'] >= 3
        assert metrics['tasks']['by_status']['active'] >= 1
        assert metrics['tasks']['by_status']['completed'] >= 1
        assert metrics['tasks']['by_status']['archived'] >= 1


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestAdminErrorHandling:
    """Test error handling in admin endpoints."""
    
    def test_invalid_user_id_format(self, client, admin_token):
        """Test with invalid user ID format."""
        response = client.get(
            '/api/admin/users/invalid-id',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        # Should return 404 for non-existent user
        assert response.status_code in [404, 400]
    
    def test_empty_request_body(self, client, admin_token, regular_user):
        """Test update with empty request body."""
        response = client.put(
            f'/api/admin/users/{regular_user.id}',
            headers={'Authorization': f'Bearer {admin_token}'},
            json={}
        )
        assert response.status_code == 400
    
    def test_invalid_json(self, client, admin_token, regular_user):
        """Test update with invalid JSON."""
        response = client.put(
            f'/api/admin/users/{regular_user.id}',
            headers={
                'Authorization': f'Bearer {admin_token}',
                'Content-Type': 'application/json'
            },
            data='invalid json'
        )
        assert response.status_code in [400, 500]


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestAdminEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_list_users_zero_per_page(self, client, admin_token):
        """Test listing with per_page=0."""
        response = client.get(
            '/api/admin/users?per_page=0',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        # Should handle gracefully
        assert response.status_code in [200, 400]
    
    def test_list_users_very_high_per_page(self, client, admin_token):
        """Test listing with very high per_page."""
        response = client.get(
            '/api/admin/users?per_page=10000',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        # Should clamp to maximum
        assert response.status_code == 200
        if 'per_page' in response.json:
            assert response.json['per_page'] <= 100
    
    def test_list_users_negative_page(self, client, admin_token):
        """Test listing with negative page number."""
        response = client.get(
            '/api/admin/users?page=-1',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        # Should handle gracefully
        assert response.status_code in [200, 400]
    
    def test_search_special_characters(self, client, admin_token):
        """Test search with special characters."""
        response = client.get(
            '/api/admin/users?search=%25%27%22',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        # Should handle without SQL injection
        assert response.status_code == 200
    
    def test_delete_self(self, client, app, admin_user):
        """Test admin attempting to delete themselves."""
        # Create another admin first
        with app.app_context():
            other_admin = User(
                username='other_admin',
                email='other@admin.com',
                is_admin=True,
                is_active=True
            )
            other_admin.set_password('admin123')
            db.session.add(other_admin)
            db.session.commit()
            
            # Login as other admin
            response = client.post('/api/auth/login', json={
                'username': 'other_admin',
                'password': 'admin123'
            })
            token = response.json['data']['access_token']
        
        # Try to delete self
        with app.app_context():
            other_admin = db.session.query(User).filter_by(username='other_admin').first()
            response = client.delete(
                f'/api/admin/users/{other_admin.id}',
                headers={'Authorization': f'Bearer {token}'}
            )
            # Should succeed if not the last admin
            assert response.status_code in [200, 403]
