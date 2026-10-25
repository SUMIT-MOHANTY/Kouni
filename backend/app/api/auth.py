"""
Authentication API Endpoints

Flask-RESTX namespace and REST API endpoints for user authentication:
- POST /auth/register - User registration
- POST /auth/login - User login
- POST /auth/logout - User logout
- POST /auth/refresh - Token refresh
- POST /auth/password-change - Password change
- GET /auth/profile - Get user profile
"""
from flask import request, g
from flask_restx import Namespace, Resource, fields
from datetime import datetime

from ..services.auth_service import AuthService, AuthError
from ..utils.decorators import require_auth, get_current_user
from ..utils.validators import ValidationError


# Create Flask-RESTX namespace
auth_ns = Namespace('auth', description='Authentication operations')


# =============================================================================
# API Models (Request/Response Schemas)
# =============================================================================

# Registration request model
register_model = auth_ns.model('RegisterRequest', {
    'username': fields.String(required=True, description='Username (3-50 chars, alphanumeric + underscore)'),
    'email': fields.String(required=True, description='Email address'),
    'password': fields.String(required=True, description='Password (min 8 chars, mixed case, number, special char)')
})

# Login request model
login_model = auth_ns.model('LoginRequest', {
    'username': fields.String(description='Username or email address'),
    'email': fields.String(description='Email address (alternative to username)'),
    'password': fields.String(required=True, description='Password')
})

# Password change model
password_change_model = auth_ns.model('PasswordChangeRequest', {
    'current_password': fields.String(required=True, description='Current password'),
    'new_password': fields.String(required=True, description='New password')
})

# Token response model
token_model = auth_ns.model('TokenResponse', {
    'access_token': fields.String(description='JWT access token'),
    'refresh_token': fields.String(description='JWT refresh token'),
    'expires_in': fields.Integer(description='Token expiration time in seconds'),
    'token_type': fields.String(description='Token type (Bearer)')
})

# User profile model
user_profile_model = auth_ns.model('UserProfile', {
    'id': fields.String(description='User ID'),
    'username': fields.String(description='Username'),
    'email': fields.String(description='Email address'),
    'is_active': fields.Boolean(description='Account active status'),
    'is_admin': fields.Boolean(description='Admin status'),
    'created_at': fields.String(description='Account creation timestamp'),
    'updated_at': fields.String(description='Last update timestamp'),
    'active_sessions': fields.Integer(description='Number of active sessions')
})

# Success response model
success_response = auth_ns.model('SuccessResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'message': fields.String(description='Success message'),
    'data': fields.Raw(description='Response data')
})

# Error response model
error_response = auth_ns.model('ErrorResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'error': fields.String(description='Error type'),
    'message': fields.String(description='Error message'),
    'error_code': fields.String(description='Error code for client handling')
})


# =============================================================================
# Helper Functions
# =============================================================================

def get_client_ip():
    """Get client IP address from request."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr


def get_user_agent():
    """Get user agent string from request."""
    return request.headers.get('User-Agent', '')


def make_response(success=True, data=None, message=None, error=None, error_code=None, status_code=200):
    """
    Create a standardized API response.
    
    Args:
        success: Whether the operation was successful
        data: Response data payload
        message: Human-readable message
        error: Error type/name
        error_code: Machine-readable error code
        status_code: HTTP status code
        
    Returns:
        tuple: (response_dict, status_code)
    """
    response = {'success': success}
    
    if message:
        response['message'] = message
    if data is not None:
        response['data'] = data
    if error:
        response['error'] = error
    if error_code:
        response['error_code'] = error_code
        
    return response, status_code


# =============================================================================
# API Resources
# =============================================================================

@auth_ns.route('/register')
class RegisterResource(Resource):
    """User registration endpoint."""
    
    @auth_ns.doc('register_user')
    @auth_ns.expect(register_model, validate=True)
    @auth_ns.response(201, 'User registered successfully', success_response)
    @auth_ns.response(409, 'Username or email already exists', error_response)
    @auth_ns.response(422, 'Validation error', error_response)
    @auth_ns.response(500, 'Internal server error', error_response)
    def post(self):
        """
        Register a new user account.
        
        Creates a new user with the provided username, email, and password.
        Returns the created user profile on success.
        """
        try:
            data = request.get_json()
            
            # Extract fields
            username = data.get('username', '').strip()
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
            
            # Register user
            user, message = AuthService.register_user(username, email, password)
            
            return make_response(
                success=True,
                data={'user': AuthService.get_user_profile(user)},
                message=message,
                status_code=201
            )
            
        except AuthError as e:
            return make_response(
                success=False,
                error='Registration Failed',
                message=e.message,
                error_code=e.error_code,
                status_code=e.status_code
            )
        except ValidationError as e:
            return make_response(
                success=False,
                error='Validation Error',
                message=e.message,
                error_code='VALIDATION_ERROR',
                status_code=422
            )
        except Exception as e:
            auth_ns.logger.error(f'Unexpected error during registration: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An unexpected error occurred during registration',
                error_code='INTERNAL_ERROR',
                status_code=500
            )


@auth_ns.route('/login')
class LoginResource(Resource):
    """User login endpoint."""
    
    @auth_ns.doc('login_user')
    @auth_ns.expect(login_model, validate=True)
    @auth_ns.response(200, 'Login successful', success_response)
    @auth_ns.response(401, 'Invalid credentials', error_response)
    @auth_ns.response(403, 'Account deactivated', error_response)
    @auth_ns.response(422, 'Validation error', error_response)
    @auth_ns.response(500, 'Internal server error', error_response)
    def post(self):
        """
        Authenticate user and create session.
        
        Authenticates user with username/email and password.
        Returns JWT tokens and user profile on success.
        """
        try:
            data = request.get_json()
            
            # Extract credentials
            identifier = data.get('username') or data.get('email', '').strip()
            password = data.get('password', '')
            
            if not identifier:
                return make_response(
                    success=False,
                    error='Validation Error',
                    message='Username or email is required',
                    error_code='MISSING_IDENTIFIER',
                    status_code=422
                )
            
            # Authenticate user
            user = AuthService.authenticate_user(identifier, password)
            
            # Create session with client info
            session, tokens = AuthService.create_session(
                user,
                ip_address=get_client_ip(),
                user_agent=get_user_agent()
            )
            
            return make_response(
                success=True,
                data={
                    'user': AuthService.get_user_profile(user),
                    'tokens': tokens
                },
                message='Login successful',
                status_code=200
            )
            
        except AuthError as e:
            return make_response(
                success=False,
                error='Authentication Failed',
                message=e.message,
                error_code=e.error_code,
                status_code=e.status_code
            )
        except Exception as e:
            auth_ns.logger.error(f'Unexpected error during login: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An unexpected error occurred during login',
                error_code='INTERNAL_ERROR',
                status_code=500
            )


@auth_ns.route('/logout')
class LogoutResource(Resource):
    """User logout endpoint."""
    
    @auth_ns.doc('logout_user')
    @auth_ns.doc(security='Bearer')
    @auth_ns.response(200, 'Logout successful', success_response)
    @auth_ns.response(401, 'Authentication required', error_response)
    @auth_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def post(self):
        """
        Logout current user and invalidate session.
        
        Requires authentication. Invalidates the current session token.
        """
        try:
            # Get session ID from token payload
            token_payload = getattr(g, 'token_payload', {})
            session_id = token_payload.get('session_id')
            
            if session_id:
                AuthService.invalidate_session(session_id)
                message = 'Logout successful'
            else:
                message = 'Session not found, but logout processed'
            
            return make_response(
                success=True,
                message=message,
                status_code=200
            )
            
        except Exception as e:
            auth_ns.logger.error(f'Error during logout: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred during logout',
                error_code='LOGOUT_ERROR',
                status_code=500
            )


@auth_ns.route('/refresh')
class RefreshResource(Resource):
    """Token refresh endpoint."""
    
    refresh_request_model = auth_ns.model('RefreshRequest', {
        'refresh_token': fields.String(required=True, description='Refresh token')
    })
    
    @auth_ns.doc('refresh_token')
    @auth_ns.expect(refresh_request_model, validate=True)
    @auth_ns.response(200, 'Token refreshed successfully', success_response)
    @auth_ns.response(401, 'Invalid or expired refresh token', error_response)
    @auth_ns.response(500, 'Internal server error', error_response)
    def post(self):
        """
        Refresh access token using refresh token.
        
        Returns new access and refresh tokens.
        """
        try:
            data = request.get_json()
            refresh_token = data.get('refresh_token', '')
            
            if not refresh_token:
                return make_response(
                    success=False,
                    error='Validation Error',
                    message='Refresh token is required',
                    error_code='MISSING_REFRESH_TOKEN',
                    status_code=422
                )
            
            # Refresh tokens
            session, tokens = AuthService.refresh_token(refresh_token)
            
            return make_response(
                success=True,
                data={'tokens': tokens},
                message='Token refreshed successfully',
                status_code=200
            )
            
        except AuthError as e:
            return make_response(
                success=False,
                error='Token Refresh Failed',
                message=e.message,
                error_code=e.error_code,
                status_code=e.status_code
            )
        except Exception as e:
            auth_ns.logger.error(f'Error refreshing token: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while refreshing token',
                error_code='REFRESH_ERROR',
                status_code=500
            )


@auth_ns.route('/password-change')
class PasswordChangeResource(Resource):
    """Password change endpoint."""
    
    @auth_ns.doc('change_password')
    @auth_ns.doc(security='Bearer')
    @auth_ns.expect(password_change_model, validate=True)
    @auth_ns.response(200, 'Password changed successfully', success_response)
    @auth_ns.response(401, 'Authentication required or current password incorrect', error_response)
    @auth_ns.response(422, 'Validation error', error_response)
    @auth_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def post(self):
        """
        Change user password.
        
        Requires authentication. Verifies current password before setting new one.
        """
        try:
            data = request.get_json()
            
            current_password = data.get('current_password', '')
            new_password = data.get('new_password', '')
            
            # Get current user
            user = get_current_user()
            
            # Change password
            AuthService.change_password(user, current_password, new_password)
            
            return make_response(
                success=True,
                message='Password changed successfully',
                status_code=200
            )
            
        except AuthError as e:
            return make_response(
                success=False,
                error='Password Change Failed',
                message=e.message,
                error_code=e.error_code,
                status_code=e.status_code
            )
        except Exception as e:
            auth_ns.logger.error(f'Error changing password: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while changing password',
                error_code='PASSWORD_CHANGE_ERROR',
                status_code=500
            )


@auth_ns.route('/profile')
class ProfileResource(Resource):
    """User profile endpoint."""
    
    @auth_ns.doc('get_profile')
    @auth_ns.doc(security='Bearer')
    @auth_ns.response(200, 'Profile retrieved successfully', success_response)
    @auth_ns.response(401, 'Authentication required', error_response)
    @auth_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def get(self):
        """
        Get current user profile.
        
        Requires authentication. Returns user profile information.
        """
        try:
            user = get_current_user()
            profile = AuthService.get_user_profile(user)
            
            return make_response(
                success=True,
                data={'user': profile},
                message='Profile retrieved successfully',
                status_code=200
            )
            
        except Exception as e:
            auth_ns.logger.error(f'Error retrieving profile: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while retrieving profile',
                error_code='PROFILE_ERROR',
                status_code=500
            )


# =============================================================================
# Error Handlers for this Namespace
# =============================================================================

@auth_ns.errorhandler(AuthError)
def handle_auth_error(error):
    """Handle AuthError exceptions."""
    return make_response(
        success=False,
        error='Authentication Error',
        message=error.message,
        error_code=error.error_code,
        status_code=error.status_code
    )


@auth_ns.errorhandler(ValidationError)
def handle_validation_error(error):
    """Handle ValidationError exceptions."""
    return make_response(
        success=False,
        error='Validation Error',
        message=error.message,
        error_code='VALIDATION_ERROR',
        status_code=422
    )
