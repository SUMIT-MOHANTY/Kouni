"""
Auth Service Unit Tests

Comprehensive unit tests for the AuthService class covering:
- User registration
- User authentication (login)
- JWT token generation and validation
- Session lifecycle management
- Password operations
- User profile retrieval
"""
import pytest
import jwt
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from backend.app.services.auth_service import AuthService, AuthError
from backend.app.models.user import User
from backend.app.models.user_session import UserSession
from backend.app.extensions import db


class TestAuthServiceRegistration:
    """Test cases for user registration."""
    
    def test_register_user_success(self, app, db_session):
        """Test successful user registration."""
        with app.app_context():
            user, message = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            assert user is not None
            assert user.username == 'testuser'
            assert user.email == 'test@example.com'
            assert user.is_active is True
            assert user.is_admin is False
            assert user.check_password('TestPass123!') is True
            assert message == 'User registered successfully'
    
    def test_register_user_duplicate_username(self, app, db_session):
        """Test registration with duplicate username."""
        with app.app_context():
            # Create first user
            AuthService.register_user(
                username='testuser',
                email='test1@example.com',
                password='TestPass123!'
            )
            
            # Try to create second user with same username
            with pytest.raises(AuthError) as exc_info:
                AuthService.register_user(
                    username='testuser',
                    email='test2@example.com',
                    password='TestPass123!'
                )
            
            assert exc_info.value.status_code == 409
            assert exc_info.value.error_code == 'USERNAME_EXISTS'
    
    def test_register_user_duplicate_email(self, app, db_session):
        """Test registration with duplicate email."""
        with app.app_context():
            # Create first user
            AuthService.register_user(
                username='testuser1',
                email='test@example.com',
                password='TestPass123!'
            )
            
            # Try to create second user with same email
            with pytest.raises(AuthError) as exc_info:
                AuthService.register_user(
                    username='testuser2',
                    email='test@example.com',
                    password='TestPass123!'
                )
            
            assert exc_info.value.status_code == 409
            assert exc_info.value.error_code == 'EMAIL_EXISTS'
    
    def test_register_user_weak_password(self, app, db_session):
        """Test registration with weak password."""
        with app.app_context():
            with pytest.raises(AuthError) as exc_info:
                AuthService.register_user(
                    username='testuser',
                    email='test@example.com',
                    password='weak'
                )
            
            assert exc_info.value.status_code == 422
            assert exc_info.value.error_code == 'VALIDATION_ERROR'
    
    def test_register_user_invalid_email(self, app, db_session):
        """Test registration with invalid email."""
        with app.app_context():
            with pytest.raises(AuthError) as exc_info:
                AuthService.register_user(
                    username='testuser',
                    email='invalid-email',
                    password='TestPass123!'
                )
            
            assert exc_info.value.status_code == 422
            assert exc_info.value.error_code == 'VALIDATION_ERROR'
    
    def test_register_user_invalid_username(self, app, db_session):
        """Test registration with invalid username."""
        with app.app_context():
            with pytest.raises(AuthError) as exc_info:
                AuthService.register_user(
                    username='ab',  # Too short
                    email='test@example.com',
                    password='TestPass123!'
                )
            
            assert exc_info.value.status_code == 422
            assert exc_info.value.error_code == 'VALIDATION_ERROR'


class TestAuthServiceAuthentication:
    """Test cases for user authentication."""
    
    def test_authenticate_user_success(self, app, db_session):
        """Test successful user authentication."""
        with app.app_context():
            # Create user
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            # Authenticate with username
            authenticated_user = AuthService.authenticate_user('testuser', 'TestPass123!')
            assert authenticated_user.id == user.id
            
            # Authenticate with email
            authenticated_user = AuthService.authenticate_user('test@example.com', 'TestPass123!')
            assert authenticated_user.id == user.id
    
    def test_authenticate_user_wrong_password(self, app, db_session):
        """Test authentication with wrong password."""
        with app.app_context():
            AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            with pytest.raises(AuthError) as exc_info:
                AuthService.authenticate_user('testuser', 'WrongPass123!')
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.error_code == 'INVALID_CREDENTIALS'
    
    def test_authenticate_user_nonexistent(self, app, db_session):
        """Test authentication with non-existent user."""
        with app.app_context():
            with pytest.raises(AuthError) as exc_info:
                AuthService.authenticate_user('nonexistent', 'TestPass123!')
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.error_code == 'INVALID_CREDENTIALS'
    
    def test_authenticate_user_inactive(self, app, db_session):
        """Test authentication with inactive user account."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            # Deactivate user
            user.is_active = False
            db.session.commit()
            
            with pytest.raises(AuthError) as exc_info:
                AuthService.authenticate_user('testuser', 'TestPass123!')
            
            assert exc_info.value.status_code == 403
            assert exc_info.value.error_code == 'ACCOUNT_DEACTIVATED'
    
    def test_authenticate_user_missing_credentials(self, app, db_session):
        """Test authentication with missing credentials."""
        with app.app_context():
            with pytest.raises(AuthError) as exc_info:
                AuthService.authenticate_user('', '')
            
            assert exc_info.value.status_code == 400
            assert exc_info.value.error_code == 'MISSING_CREDENTIALS'


class TestAuthServiceTokenGeneration:
    """Test cases for JWT token generation."""
    
    def test_generate_token_success(self, app, db_session):
        """Test successful token generation."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            tokens = AuthService.generate_token(user)
            
            assert 'access_token' in tokens
            assert 'refresh_token' in tokens
            assert 'expires_in' in tokens
            assert 'token_type' in tokens
            assert tokens['token_type'] == 'Bearer'
            assert tokens['expires_in'] > 0
    
    def test_generate_token_contains_correct_payload(self, app, db_session):
        """Test that generated token contains correct payload."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            tokens = AuthService.generate_token(user, session_id='test-session-id')
            
            # Decode access token
            access_payload = jwt.decode(
                tokens['access_token'],
                app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )
            
            assert access_payload['user_id'] == user.id
            assert access_payload['session_id'] == 'test-session-id'
            assert access_payload['type'] == 'access'
            
            # Decode refresh token
            refresh_payload = jwt.decode(
                tokens['refresh_token'],
                app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )
            
            assert refresh_payload['user_id'] == user.id
            assert refresh_payload['session_id'] == 'test-session-id'
            assert refresh_payload['type'] == 'refresh'
    
    def test_generate_token_expiration(self, app, db_session):
        """Test that tokens have correct expiration times."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            tokens = AuthService.generate_token(user)
            
            access_payload = jwt.decode(
                tokens['access_token'],
                app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )
            refresh_payload = jwt.decode(
                tokens['refresh_token'],
                app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )
            
            # Check that tokens have expiration
            assert 'exp' in access_payload
            assert 'exp' in refresh_payload
            
            # Refresh token should expire later than access token
            assert refresh_payload['exp'] > access_payload['exp']


class TestAuthServiceTokenValidation:
    """Test cases for JWT token validation."""
    
    def test_validate_token_success(self, app, db_session):
        """Test successful token validation."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            tokens = AuthService.generate_token(user)
            payload = AuthService.validate_token(tokens['access_token'], token_type='access')
            
            assert payload['user_id'] == user.id
            assert payload['type'] == 'access'
    
    def test_validate_token_expired(self, app, db_session):
        """Test validation of expired token."""
        with app.app_context():
            # Create an expired token manually
            expired_payload = {
                'user_id': 'test-user-id',
                'type': 'access',
                'exp': datetime.utcnow() - timedelta(hours=1),
                'iat': datetime.utcnow() - timedelta(hours=2)
            }
            
            expired_token = jwt.encode(
                expired_payload,
                app.config['JWT_SECRET_KEY'],
                algorithm='HS256'
            )
            
            with pytest.raises(AuthError) as exc_info:
                AuthService.validate_token(expired_token)
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.error_code == 'TOKEN_EXPIRED'
    
    def test_validate_token_invalid(self, app, db_session):
        """Test validation of invalid token."""
        with app.app_context():
            with pytest.raises(AuthError) as exc_info:
                AuthService.validate_token('invalid-token')
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.error_code == 'INVALID_TOKEN'
    
    def test_validate_token_wrong_type(self, app, db_session):
        """Test validation with wrong token type."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            tokens = AuthService.generate_token(user)
            
            # Try to validate access token as refresh token
            with pytest.raises(AuthError) as exc_info:
                AuthService.validate_token(tokens['access_token'], token_type='refresh')
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.error_code == 'INVALID_TOKEN_TYPE'


class TestAuthServiceSessionManagement:
    """Test cases for session lifecycle management."""
    
    def test_create_session_success(self, app, db_session):
        """Test successful session creation."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            session, tokens = AuthService.create_session(
                user,
                ip_address='127.0.0.1',
                user_agent='TestAgent/1.0'
            )
            
            assert session is not None
            assert session.user_id == user.id
            assert session.token == tokens['access_token']
            assert session.refresh_token == tokens['refresh_token']
            assert session.ip_address == '127.0.0.1'
            assert session.user_agent == 'TestAgent/1.0'
            assert session.is_valid is True
    
    def test_invalidate_session_success(self, app, db_session):
        """Test successful session invalidation."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            session, _ = AuthService.create_session(user)
            session_id = session.id
            
            # Invalidate session
            result = AuthService.invalidate_session(session_id)
            assert result is True
            
            # Verify session is invalidated
            db.session.refresh(session)
            assert session.is_valid is False
    
    def test_invalidate_session_not_found(self, app, db_session):
        """Test invalidation of non-existent session."""
        with app.app_context():
            result = AuthService.invalidate_session('non-existent-session-id')
            assert result is False
    
    def test_invalidate_all_user_sessions(self, app, db_session):
        """Test invalidating all sessions for a user."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            # Create multiple sessions
            session1, _ = AuthService.create_session(user)
            session2, _ = AuthService.create_session(user)
            session3, _ = AuthService.create_session(user)
            
            # Invalidate all sessions
            count = AuthService.invalidate_all_user_sessions(user.id)
            assert count == 3
            
            # Verify all sessions are invalidated
            for session in [session1, session2, session3]:
                db.session.refresh(session)
                assert session.is_valid is False
    
    def test_invalidate_all_user_sessions_except_one(self, app, db_session):
        """Test invalidating all sessions except one."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            # Create multiple sessions
            session1, _ = AuthService.create_session(user)
            session2, _ = AuthService.create_session(user)
            session3, _ = AuthService.create_session(user)
            
            # Invalidate all sessions except session2
            count = AuthService.invalidate_all_user_sessions(user.id, except_session_id=session2.id)
            assert count == 2
            
            # Verify session2 is still valid
            db.session.refresh(session2)
            assert session2.is_valid is True
    
    def test_refresh_token_success(self, app, db_session):
        """Test successful token refresh."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            session, tokens = AuthService.create_session(user)
            old_access_token = tokens['access_token']
            
            # Refresh token
            new_session, new_tokens = AuthService.refresh_token(tokens['refresh_token'])
            
            assert new_session.id == session.id
            assert new_tokens['access_token'] != old_access_token
            assert 'refresh_token' in new_tokens
    
    def test_refresh_token_invalid(self, app, db_session):
        """Test refresh with invalid token."""
        with app.app_context():
            with pytest.raises(AuthError) as exc_info:
                AuthService.refresh_token('invalid-refresh-token')
            
            assert exc_info.value.status_code == 401
    
    def test_cleanup_expired_sessions(self, app, db_session):
        """Test cleanup of expired sessions."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            # Create a session
            session, _ = AuthService.create_session(user)
            
            # Manually expire the session
            session.expires_at = datetime.utcnow() - timedelta(hours=1)
            db.session.commit()
            
            # Cleanup expired sessions
            count = AuthService.cleanup_expired_sessions()
            assert count == 1
            
            # Verify session is invalidated
            db.session.refresh(session)
            assert session.is_valid is False


class TestAuthServicePasswordOperations:
    """Test cases for password operations."""
    
    def test_change_password_success(self, app, db_session):
        """Test successful password change."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='OldPass123!'
            )
            
            # Change password
            result = AuthService.change_password(
                user,
                current_password='OldPass123!',
                new_password='NewPass456!'
            )
            
            assert result is True
            
            # Verify new password works
            db.session.refresh(user)
            assert user.check_password('NewPass123!') is False
            assert user.check_password('NewPass456!') is True
    
    def test_change_password_wrong_current(self, app, db_session):
        """Test password change with wrong current password."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='OldPass123!'
            )
            
            with pytest.raises(AuthError) as exc_info:
                AuthService.change_password(
                    user,
                    current_password='WrongPass123!',
                    new_password='NewPass456!'
                )
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.error_code == 'INVALID_CURRENT_PASSWORD'
    
    def test_change_password_weak_new(self, app, db_session):
        """Test password change with weak new password."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='OldPass123!'
            )
            
            with pytest.raises(AuthError) as exc_info:
                AuthService.change_password(
                    user,
                    current_password='OldPass123!',
                    new_password='weak'
                )
            
            assert exc_info.value.status_code == 422
            assert exc_info.value.error_code == 'VALIDATION_ERROR'
    
    def test_change_password_same_as_current(self, app, db_session):
        """Test password change with same password."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='OldPass123!'
            )
            
            with pytest.raises(AuthError) as exc_info:
                AuthService.change_password(
                    user,
                    current_password='OldPass123!',
                    new_password='OldPass123!'
                )
            
            assert exc_info.value.status_code == 422
            assert exc_info.value.error_code == 'VALIDATION_ERROR'


class TestAuthServiceUserProfile:
    """Test cases for user profile operations."""
    
    def test_get_user_profile(self, app, db_session):
        """Test getting user profile."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            profile = AuthService.get_user_profile(user)
            
            assert profile['id'] == user.id
            assert profile['username'] == 'testuser'
            assert profile['email'] == 'test@example.com'
            assert profile['is_active'] is True
            assert profile['is_admin'] is False
            assert 'created_at' in profile
            assert 'updated_at' in profile
            assert 'active_sessions' in profile
    
    def test_get_user_sessions(self, app, db_session):
        """Test getting user sessions."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            # Create sessions
            AuthService.create_session(user)
            AuthService.create_session(user)
            
            sessions = AuthService.get_user_sessions(user.id)
            assert len(sessions) == 2
    
    def test_get_user_sessions_include_expired(self, app, db_session):
        """Test getting user sessions including expired ones."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            # Create sessions
            session1, _ = AuthService.create_session(user)
            session2, _ = AuthService.create_session(user)
            
            # Expire one session
            session1.expires_at = datetime.utcnow() - timedelta(hours=1)
            db.session.commit()
            
            # Get only valid sessions
            valid_sessions = AuthService.get_user_sessions(user.id, include_expired=False)
            assert len(valid_sessions) == 1
            
            # Get all sessions including expired
            all_sessions = AuthService.get_user_sessions(user.id, include_expired=True)
            assert len(all_sessions) == 2


class TestPasswordHashing:
    """Test cases for password hashing functionality."""
    
    def test_password_hashing(self, app, db_session):
        """Test that passwords are properly hashed."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            # Password hash should not be the plain password
            assert user.password_hash != 'TestPass123!'
            
            # Password hash should be a valid hash format
            assert user.password_hash.startswith('pbkdf2:sha256:')
    
    def test_password_verification(self, app, db_session):
        """Test password verification."""
        with app.app_context():
            user, _ = AuthService.register_user(
                username='testuser',
                email='test@example.com',
                password='TestPass123!'
            )
            
            # Correct password should verify
            assert user.check_password('TestPass123!') is True
            
            # Wrong password should not verify
            assert user.check_password('WrongPass123!') is False
            
            # Similar password should not verify
            assert user.check_password('testpass123!') is False  # Different case
            assert user.check_password('TestPass123') is False   # Missing special char
