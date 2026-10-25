"""
Authentication Decorators

Flask decorators for protecting routes with authentication and authorization checks.
Provides JWT token validation, admin privilege verification, and request body validation.
"""
import functools
from functools import wraps
from flask import request, jsonify, g, current_app
from datetime import datetime
import jwt
from typing import Callable, Optional

from ..extensions import db
from ..models.user import User
from ..models.user_session import UserSession


class AuthenticationError(Exception):
    """Custom exception for authentication errors."""
    
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def get_auth_token() -> Optional[str]:
    """
    Extract JWT token from Authorization header.
    
    Supports Bearer token format:
    Authorization: Bearer <token>
    
    Returns:
        str: The JWT token if present, None otherwise
    """
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        return None
    
    # Check for Bearer token format
    parts = auth_header.split()
    
    if len(parts) != 2:
        return None
    
    if parts[0].lower() != 'bearer':
        return None
    
    return parts[1]


def decode_token(token: str) -> dict:
    """
    Decode and validate JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        dict: Decoded token payload
        
    Raises:
        AuthenticationError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError('Token has expired', 401)
    except jwt.InvalidTokenError:
        raise AuthenticationError('Invalid token', 401)


def require_auth(f: Callable) -> Callable:
    """
    Decorator to require authentication for a route.
    
    Validates JWT token from Authorization header, checks session validity,
    and attaches the current user to the request context (g.user).
    
    Args:
        f: Function to decorate
        
    Returns:
        Callable: Decorated function
        
    Example:
        @app.route('/api/protected')
        @require_auth
        def protected_route():
            return jsonify({'message': f'Hello, {g.user.username}!'})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from header
        token = get_auth_token()
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Unauthorized',
                'message': 'Authentication required. Please provide a valid Bearer token.'
            }), 401
        
        try:
            # Decode token
            payload = decode_token(token)
            
            # Get user_id from token
            user_id = payload.get('user_id')
            session_id = payload.get('session_id')
            
            if not user_id:
                return jsonify({
                    'success': False,
                    'error': 'Unauthorized',
                    'message': 'Invalid token: missing user_id'
                }), 401
            
            # Check session validity in database
            if session_id:
                from ..extensions import db
                user_session = db.session.query(UserSession).filter_by(
                    id=session_id,
                    token=token,
                    is_valid=True
                ).first()
                
                if not user_session:
                    return jsonify({
                        'success': False,
                        'error': 'Unauthorized',
                        'message': 'Session has been revoked or is invalid'
                    }), 401
                
                if user_session.is_expired():
                    user_session.invalidate()
                    db.session.commit()
                    return jsonify({
                        'success': False,
                        'error': 'Unauthorized',
                        'message': 'Session has expired'
                    }), 401
                
                # Load user from session relationship
                _ = user_session.user
                
                # Store user in g.user for require_admin check
                g.user = user_session.user
            
            # Get user from database
            user = db.session.query(User).filter_by(id=user_id, is_active=True).first()
            
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'Unauthorized',
                    'message': 'User not found or account is deactivated'
                }), 401
            
            # Attach user and token info to request context
            g.user = user
            g.token_payload = payload
            g.token = token
            
            return f(*args, **kwargs)
            
        except AuthenticationError as e:
            return jsonify({
                'success': False,
                'error': 'Unauthorized',
                'message': e.message
            }), e.status_code
        except Exception as e:
            current_app.logger.error(f'Authentication error: {str(e)}')
            return jsonify({
                'success': False,
                'error': 'Internal Server Error',
                'message': 'An error occurred during authentication'
            }), 500
    
    return decorated_function


def require_admin(f: Callable) -> Callable:
    """
    Decorator to require admin privileges for a route.
    
    Must be used after @require_auth decorator. Checks if the authenticated
    user has admin privileges (is_admin=True).
    
    Args:
        f: Function to decorate
        
    Returns:
        Callable: Decorated function
        
    Example:
        @app.route('/api/admin/users')
        @require_auth
        @require_admin
        def admin_users():
            return jsonify({'users': [...]})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if require_auth was called first
        if not hasattr(g, 'user'):
            return jsonify({
                'success': False,
                'error': 'Unauthorized',
                'message': 'Authentication required before admin check'
            }), 401
        
        # Check admin privileges - g.user is the User model
        if not g.user.is_admin:
            return jsonify({
                'success': False,
                'error': 'Forbidden',
                'message': 'Admin privileges required'
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


def validate_request_body(schema: dict) -> Callable:
    """
    Decorator to validate request body against a schema.
    
    Schema format:
    {
        'field_name': {
            'type': str,
            'required': True,
            'min_length': 3,
            'max_length': 50,
            'validator': custom_validator_function
        }
    }
    
    Args:
        schema: Dictionary defining validation rules for each field
        
    Returns:
        Callable: Decorator function
        
    Example:
        @app.route('/api/register', methods=['POST'])
        @validate_request_body({
            'username': {'type': str, 'required': True, 'min_length': 3},
            'email': {'type': str, 'required': True},
            'password': {'type': str, 'required': True, 'min_length': 8}
        })
        def register():
            data = request.get_json()
            # Process validated data...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get request data
            data = request.get_json(silent=True) or {}
            errors = {}
            
            for field_name, rules in schema.items():
                value = data.get(field_name)
                
                # Check required fields
                if rules.get('required', False):
                    if value is None or (isinstance(value, str) and not value.strip()):
                        errors[field_name] = f"{field_name} is required"
                        continue
                
                # Skip further validation if field is not required and not present
                if value is None and not rules.get('required', False):
                    continue
                
                # Type validation
                expected_type = rules.get('type')
                if expected_type and value is not None:
                    if expected_type == str and not isinstance(value, str):
                        errors[field_name] = f"{field_name} must be a string"
                        continue
                    elif expected_type == int and not isinstance(value, int):
                        errors[field_name] = f"{field_name} must be an integer"
                        continue
                    elif expected_type == bool and not isinstance(value, bool):
                        errors[field_name] = f"{field_name} must be a boolean"
                        continue
                    elif expected_type == list and not isinstance(value, list):
                        errors[field_name] = f"{field_name} must be a list"
                        continue
                    elif expected_type == dict and not isinstance(value, dict):
                        errors[field_name] = f"{field_name} must be an object"
                        continue
                
                # String-specific validations
                if isinstance(value, str):
                    # Min length
                    min_length = rules.get('min_length')
                    if min_length is not None and len(value.strip()) < min_length:
                        errors[field_name] = f"{field_name} must be at least {min_length} characters"
                        continue
                    
                    # Max length
                    max_length = rules.get('max_length')
                    if max_length is not None and len(value) > max_length:
                        errors[field_name] = f"{field_name} must not exceed {max_length} characters"
                        continue
                    
                    # Pattern validation (regex)
                    pattern = rules.get('pattern')
                    if pattern and not pattern.match(value):
                        errors[field_name] = rules.get('pattern_message', f"{field_name} format is invalid")
                        continue
                
                # Custom validator
                custom_validator = rules.get('validator')
                if custom_validator and callable(custom_validator):
                    is_valid, error_message = custom_validator(value)
                    if not is_valid:
                        errors[field_name] = error_message or f"{field_name} is invalid"
                        continue
            
            # Return validation errors if any
            if errors:
                return jsonify({
                    'success': False,
                    'error': 'Validation Error',
                    'message': 'Request validation failed',
                    'errors': errors
                }), 422
            
            # Store validated data in g for access in route
            g.validated_data = data
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def optional_auth(f: Callable) -> Callable:
    """
    Decorator for routes that can work with or without authentication.
    
    If a valid token is provided, attaches the user to g.user.
    If no token or invalid token, g.user will be None.
    
    Args:
        f: Function to decorate
        
    Returns:
        Callable: Decorated function
        
    Example:
        @app.route('/api/public-data')
        @optional_auth
        def public_data():
            if g.user:
                return jsonify({'data': personalized_data})
            return jsonify({'data': public_data})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        g.user = None
        g.token_payload = None
        g.token = None
        
        token = get_auth_token()
        
        if token:
            try:
                payload = decode_token(token)
                user_id = payload.get('user_id')
                
                if user_id:
                    from ..extensions import db
                    user = db.session.query(User).filter_by(id=user_id, is_active=True).first()
                    if user:
                        g.user = user
                        g.token_payload = payload
                        g.token = token
            except Exception:
                # Silently ignore auth errors for optional auth
                pass
        
        return f(*args, **kwargs)
    
    return decorated_function


def rate_limit(max_requests: int = 100, window_seconds: int = 3600) -> Callable:
    """
    Decorator to implement rate limiting for routes.
    
    Simple in-memory rate limiting. For production, consider using
    Redis or a dedicated rate limiting service.
    
    Args:
        max_requests: Maximum number of requests allowed in the window
        window_seconds: Time window in seconds
        
    Returns:
        Callable: Decorator function
    """
    # In-memory storage for rate limiting (use Redis in production)
    _rate_limit_storage = {}
    
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client identifier (IP or user_id if authenticated)
            client_id = request.remote_addr or 'unknown'
            if hasattr(g, 'user') and g.user:
                client_id = g.user.id
            
            now = datetime.utcnow().timestamp()
            window_start = now - window_seconds
            
            # Get client's request history
            client_requests = _rate_limit_storage.get(client_id, [])
            
            # Remove old requests outside the window
            client_requests = [ts for ts in client_requests if ts > window_start]
            
            # Check if limit exceeded
            if len(client_requests) >= max_requests:
                return jsonify({
                    'success': False,
                    'error': 'Too Many Requests',
                    'message': f'Rate limit exceeded. Try again in {window_seconds} seconds.'
                }), 429
            
            # Add current request timestamp
            client_requests.append(now)
            _rate_limit_storage[client_id] = client_requests
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def get_current_user() -> Optional[User]:
    """
    Get the currently authenticated user from request context.
    
    Returns:
        User: The authenticated user, or None if not authenticated
    """
    return getattr(g, 'user', None)


def get_current_user_id() -> Optional[str]:
    """
    Get the currently authenticated user's ID from request context.
    
    Returns:
        str: The user's ID, or None if not authenticated
    """
    user = get_current_user()
    return user.id if user else None


def is_authenticated() -> bool:
    """
    Check if the current request has an authenticated user.
    
    Returns:
        bool: True if authenticated, False otherwise
    """
    return get_current_user() is not None


def check_is_admin() -> bool:
    """
    Check if the current user is an admin.
    
    Returns:
        bool: True if user is admin, False otherwise
    """
    user = get_current_user()
    return user.is_admin if user else False
