"""
Authentication API Integration Tests

Integration tests for the authentication API endpoints covering:
- User registration (POST /api/auth/register)
- User login (POST /api/auth/login)
- User logout (POST /api/auth/logout)
- Token refresh (POST /api/auth/refresh)
- Password change (POST /api/auth/password-change)
- Profile retrieval (GET /api/auth/profile)

Tests verify JWT Bearer token authentication flows and edge cases.
"""
import json
import pytest
from datetime import datetime, timedelta

from backend.app.extensions import db
from backend.app.models.user import User
from backend.app.models.user_session import UserSession
from backend.app.services.auth_service import AuthService


class TestAuthRegistration:
    """Integration tests for user registration endpoint."""
    
    def test_register_success(self, client):
        """Test successful user registration."""
        response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'newuser',
                'email': 'newuser@example.com',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'user' in data['data']
        assert data['data']['user']['username'] == 'newuser'
        assert data['data']['user']['email'] == 'newuser@example.com'
        assert 'password' not in str(data)
    
    def test_register_duplicate_username(self, client):
        """Test registration with duplicate username."""
        # Create first user
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'email': 'first@example.com',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        # Try to create second user with same username
        response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'testuser',
                'email': 'second@example.com',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 409
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'USERNAME_EXISTS' in data.get('error_code', '') or 'already exists' in data.get('message', '').lower()
    
    def test_register_duplicate_email(self, client):
        """Test registration with duplicate email."""
        # Create first user
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'userone',
                'email': 'duplicate@example.com',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        # Try to create second user with same email
        response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'usertwo',
                'email': 'duplicate@example.com',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 409
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'EMAIL_EXISTS' in data.get('error_code', '') or 'already registered' in data.get('message', '').lower()
    
    def test_register_weak_password(self, client):
        """Test registration with weak password."""
        response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'weakuser',
                'email': 'weak@example.com',
                'password': '123'  # Too weak
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_register_invalid_email(self, client):
        """Test registration with invalid email format."""
        response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'baduser',
                'email': 'not-an-email',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_register_missing_fields(self, client):
        """Test registration with missing required fields."""
        response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'incomplete'
                # Missing email and password
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False


class TestAuthLogin:
    """Integration tests for user login endpoint."""
    
    @pytest.fixture
    def registered_user(self, client):
        """Create a registered user for login tests."""
        response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'logintest',
                'email': 'login@example.com',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        return json.loads(response.data)['data']['user']
    
    def test_login_with_username(self, client, registered_user):
        """Test login using username."""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'logintest',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'tokens' in data['data']
        assert 'access_token' in data['data']['tokens']
        assert 'refresh_token' in data['data']['tokens']
        assert data['data']['tokens']['token_type'] == 'Bearer'
    
    def test_login_with_email(self, client, registered_user):
        """Test login using email."""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'email': 'login@example.com',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'tokens' in data['data']
    
    def test_login_invalid_credentials(self, client, registered_user):
        """Test login with wrong password."""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'logintest',
                'password': 'WrongPassword123!'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'INVALID_CREDENTIALS' in data.get('error_code', '') or 'invalid' in data.get('message', '').lower()
    
    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'nonexistent',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_login_missing_identifier(self, client):
        """Test login without username or email."""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False


class TestAuthLogout:
    """Integration tests for user logout endpoint."""
    
    @pytest.fixture
    def authenticated_user(self, client):
        """Create and authenticate a user, returning tokens."""
        # Register user
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'logouttest',
                'email': 'logout@example.com',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        # Login to get tokens
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'logouttest',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        data = json.loads(response.data)
        return data['data']['tokens']
    
    def test_logout_success(self, client, authenticated_user):
        """Test successful logout with valid token."""
        response = client.post(
            '/api/auth/logout',
            headers={'Authorization': f"Bearer {authenticated_user['access_token']}"}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'logout' in data.get('message', '').lower() or 'successful' in data.get('message', '').lower()
    
    def test_logout_without_token(self, client):
        """Test logout without authentication token."""
        response = client.post('/api/auth/logout')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_logout_invalid_token(self, client):
        """Test logout with invalid token."""
        response = client.post(
            '/api/auth/logout',
            headers={'Authorization': 'Bearer invalid-token'}
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_logout_after_already_logged_out(self, client, authenticated_user):
        """Test logout with already invalidated token."""
        # First logout
        client.post(
            '/api/auth/logout',
            headers={'Authorization': f"Bearer {authenticated_user['access_token']}"}
        )
        
        # Try to logout again with same token
        response = client.post(
            '/api/auth/logout',
            headers={'Authorization': f"Bearer {authenticated_user['access_token']}"}
        )
        
        # Should fail because session is already invalidated
        assert response.status_code == 401


class TestAuthTokenRefresh:
    """Integration tests for token refresh endpoint."""
    
    @pytest.fixture
    def authenticated_user(self, client):
        """Create and authenticate a user, returning tokens."""
        # Register user
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'refreshtest',
                'email': 'refresh@example.com',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        # Login to get tokens
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'refreshtest',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        data = json.loads(response.data)
        return data['data']['tokens']
    
    def test_refresh_token_success(self, client, authenticated_user):
        """Test successful token refresh."""
        response = client.post(
            '/api/auth/refresh',
            data=json.dumps({
                'refresh_token': authenticated_user['refresh_token']
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'tokens' in data['data']
        assert 'access_token' in data['data']['tokens']
        assert 'refresh_token' in data['data']['tokens']
        # New tokens should be different from old ones
        assert data['data']['tokens']['access_token'] != authenticated_user['access_token']
    
    def test_refresh_token_invalid(self, client):
        """Test refresh with invalid token."""
        response = client.post(
            '/api/auth/refresh',
            data=json.dumps({
                'refresh_token': 'invalid-refresh-token'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_refresh_token_missing(self, client):
        """Test refresh without token."""
        response = client.post(
            '/api/auth/refresh',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False


class TestAuthPasswordChange:
    """Integration tests for password change endpoint."""
    
    @pytest.fixture
    def authenticated_user(self, client):
        """Create and authenticate a user, returning tokens and user data."""
        # Register user
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'passwordtest',
                'email': 'password@example.com',
                'password': 'OldSecurePass123!'
            }),
            content_type='application/json'
        )
        
        # Login to get tokens
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'passwordtest',
                'password': 'OldSecurePass123!'
            }),
            content_type='application/json'
        )
        
        data = json.loads(response.data)
        return data['data']
    
    def test_password_change_success(self, client, authenticated_user):
        """Test successful password change."""
        response = client.post(
            '/api/auth/password-change',
            data=json.dumps({
                'current_password': 'OldSecurePass123!',
                'new_password': 'NewSecurePass456!'
            }),
            content_type='application/json',
            headers={'Authorization': f"Bearer {authenticated_user['tokens']['access_token']}"}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        
        # Verify can login with new password
        login_response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'passwordtest',
                'password': 'NewSecurePass456!'
            }),
            content_type='application/json'
        )
        
        assert login_response.status_code == 200
    
    def test_password_change_wrong_current(self, client, authenticated_user):
        """Test password change with wrong current password."""
        response = client.post(
            '/api/auth/password-change',
            data=json.dumps({
                'current_password': 'WrongPassword123!',
                'new_password': 'NewSecurePass456!'
            }),
            content_type='application/json',
            headers={'Authorization': f"Bearer {authenticated_user['tokens']['access_token']}"}
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'INVALID_CURRENT_PASSWORD' in data.get('error_code', '') or 'incorrect' in data.get('message', '').lower()
    
    def test_password_change_weak_new(self, client, authenticated_user):
        """Test password change with weak new password."""
        response = client.post(
            '/api/auth/password-change',
            data=json.dumps({
                'current_password': 'OldSecurePass123!',
                'new_password': 'weak'
            }),
            content_type='application/json',
            headers={'Authorization': f"Bearer {authenticated_user['tokens']['access_token']}"}
        )
        
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_password_change_same_password(self, client, authenticated_user):
        """Test password change with same password."""
        response = client.post(
            '/api/auth/password-change',
            data=json.dumps({
                'current_password': 'OldSecurePass123!',
                'new_password': 'OldSecurePass123!'
            }),
            content_type='application/json',
            headers={'Authorization': f"Bearer {authenticated_user['tokens']['access_token']}"}
        )
        
        assert response.status_code == 422
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_password_change_unauthenticated(self, client):
        """Test password change without authentication."""
        response = client.post(
            '/api/auth/password-change',
            data=json.dumps({
                'current_password': 'OldSecurePass123!',
                'new_password': 'NewSecurePass456!'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False


class TestAuthProfile:
    """Integration tests for profile retrieval endpoint."""
    
    @pytest.fixture
    def authenticated_user(self, client):
        """Create and authenticate a user, returning tokens and user data."""
        # Register user
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'profiletest',
                'email': 'profile@example.com',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        # Login to get tokens
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'profiletest',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        data = json.loads(response.data)
        return data['data']
    
    def test_get_profile_success(self, client, authenticated_user):
        """Test successful profile retrieval."""
        response = client.get(
            '/api/auth/profile',
            headers={'Authorization': f"Bearer {authenticated_user['tokens']['access_token']}"}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'user' in data['data']
        assert data['data']['user']['username'] == 'profiletest'
        assert data['data']['user']['email'] == 'profile@example.com'
        assert 'password' not in str(data).lower()
        assert 'password_hash' not in str(data)
    
    def test_get_profile_unauthenticated(self, client):
        """Test profile retrieval without authentication."""
        response = client.get('/api/auth/profile')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_get_profile_invalid_token(self, client):
        """Test profile retrieval with invalid token."""
        response = client.get(
            '/api/auth/profile',
            headers={'Authorization': 'Bearer invalid-token'}
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False


class TestAuthEndToEndFlow:
    """End-to-end integration tests for complete authentication flows."""
    
    def test_complete_auth_flow(self, client):
        """Test complete authentication flow: register -> login -> profile -> logout."""
        # Step 1: Register
        register_response = client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'e2euser',
                'email': 'e2e@example.com',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        assert register_response.status_code == 201
        register_data = json.loads(register_response.data)
        assert register_data['success'] is True
        
        # Step 2: Login
        login_response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'e2euser',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        assert login_response.status_code == 200
        login_data = json.loads(login_response.data)
        assert login_data['success'] is True
        assert 'tokens' in login_data['data']
        
        access_token = login_data['data']['tokens']['access_token']
        
        # Step 3: Get Profile
        profile_response = client.get(
            '/api/auth/profile',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        assert profile_response.status_code == 200
        profile_data = json.loads(profile_response.data)
        assert profile_data['success'] is True
        assert profile_data['data']['user']['username'] == 'e2euser'
        
        # Step 4: Logout
        logout_response = client.post(
            '/api/auth/logout',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        assert logout_response.status_code == 200
        logout_data = json.loads(logout_response.data)
        assert logout_data['success'] is True
        
        # Step 5: Verify token is invalidated (profile should fail)
        profile_after_logout = client.get(
            '/api/auth/profile',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        assert profile_after_logout.status_code == 401
    
    def test_multiple_sessions(self, client):
        """Test multiple concurrent sessions for same user."""
        # Register user
        client.post(
            '/api/auth/register',
            data=json.dumps({
                'username': 'multisession',
                'email': 'multi@example.com',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        # Login from device 1
        login1 = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'multisession',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        token1 = json.loads(login1.data)['data']['tokens']['access_token']
        
        # Login from device 2
        login2 = client.post(
            '/api/auth/login',
            data=json.dumps({
                'username': 'multisession',
                'password': 'SecurePass123!'
            }),
            content_type='application/json'
        )
        
        token2 = json.loads(login2.data)['data']['tokens']['access_token']
        
        # Both tokens should work
        profile1 = client.get(
            '/api/auth/profile',
            headers={'Authorization': f'Bearer {token1}'}
        )
        assert profile1.status_code == 200
        
        profile2 = client.get(
            '/api/auth/profile',
            headers={'Authorization': f'Bearer {token2}'}
        )
        assert profile2.status_code == 200
        
        # Logout from device 1
        client.post(
            '/api/auth/logout',
            headers={'Authorization': f'Bearer {token1}'}
        )
        
        # Token 1 should be invalid, but token 2 should still work
        profile1_after = client.get(
            '/api/auth/profile',
            headers={'Authorization': f'Bearer {token1}'}
        )
        assert profile1_after.status_code == 401
        
        profile2_after = client.get(
            '/api/auth/profile',
            headers={'Authorization': f'Bearer {token2}'}
        )
        assert profile2_after.status_code == 200
