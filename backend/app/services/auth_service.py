"""
Authentication Service

Core authentication business logic including user registration, login,
token generation/validation, session management, and password operations.
"""
import uuid
import jwt
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from flask import current_app, request

from ..extensions import db
from ..models.user import User
from ..models.user_session import UserSession
from ..utils.validators import (
    validate_email_format,
    validate_password_strength,
    validate_username_format,
    validate_registration_data,
    validate_password_change_data
)


class AuthError(Exception):
    """Custom exception for authentication errors."""
    
    def __init__(self, message: str, status_code: int = 400, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or 'AUTH_ERROR'
        super().__init__(self.message)


class AuthService:
    """
    Authentication service for user management and session handling.
    
    Provides methods for:
    - User registration
    - User authentication (login)
    - JWT token generation and validation
    - Session lifecycle management
    - Password operations
    - User profile retrieval
    """
    
    @staticmethod
    def register_user(username: str, email: str, password: str) -> Tuple[User, str]:
        """
        Register a new user account.
        
        Args:
            username: Desired username
            email: User's email address
            password: User's password
            
        Returns:
            Tuple of (User object, success message)
            
        Raises:
            AuthError: If validation fails or user already exists
        """
        # Validate registration data
        is_valid, errors = validate_registration_data({
            'username': username,
            'email': email,
            'password': password
        })
        
        if not is_valid:
            raise AuthError(
                message='Validation failed',
                status_code=422,
                error_code='VALIDATION_ERROR'
            )
        # Check for existing username
        existing_user = db.session.query(User).filter_by(username=username.lower().strip()).first()
        if existing_user:
            raise AuthError(
                message='Username already exists',
                status_code=409,
                error_code='USERNAME_EXISTS'
            )
        
        # Check for existing email
        existing_email = db.session.query(User).filter_by(email=email.lower().strip()).first()
        if existing_email:
            raise AuthError(
                message='Email address already registered',
                status_code=409,
                error_code='EMAIL_EXISTS'
            )
        
        # Create new user
        user = User(
            username=username.lower().strip(),
            email=email.lower().strip()
        )
        user.set_password(password)
        
        # Save to database
        try:
            db.session.add(user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Database error during registration: {str(e)}')
            raise AuthError(
                message='Registration failed. Please try again.',
                status_code=500,
                error_code='DATABASE_ERROR'
            )
        
        return user, 'User registered successfully'
    
    @staticmethod
    def authenticate_user(identifier: str, password: str) -> User:
        """
        Authenticate a user by username/email and password.
        
        Args:
            identifier: Username or email address
            password: Plain text password
            
        Returns:
            User object if authentication succeeds
            
        Raises:
            AuthError: If authentication fails
        """
        if not identifier or not password:
            raise AuthError(
                message='Username/email and password are required',
                status_code=400,
                error_code='MISSING_CREDENTIALS'
            )
        # Try to find user by username or email
        identifier = identifier.lower().strip()
        
        # Check if identifier looks like an email
        if '@' in identifier:
            user = db.session.query(User).filter_by(email=identifier).first()
        else:
            user = db.session.query(User).filter_by(username=identifier).first()
        
        if not user:
            raise AuthError(
                message='Invalid credentials',
                status_code=401,
                error_code='INVALID_CREDENTIALS'
            )
        
        # Check if account is active
        if not user.is_active:
            raise AuthError(
                message='Account is deactivated. Please contact support.',
                status_code=403,
                error_code='ACCOUNT_DEACTIVATED'
            )
        
        # Verify password
        if not user.check_password(password):
            raise AuthError(
                message='Invalid credentials',
                status_code=401,
                error_code='INVALID_CREDENTIALS'
            )
        
        return user
    
    @staticmethod
    def generate_token(user: User, session_id: Optional[str] = None) -> Dict[str, str]:
        """
        Generate JWT access and refresh tokens for a user.
        
        Args:
            user: User object to generate token for
            session_id: Optional session ID to include in token
            
        Returns:
            Dictionary containing access_token, refresh_token, and expires_in
        """
        now = datetime.utcnow()
        
        # Access token expiration
        access_expires = current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', timedelta(minutes=15))
        access_expires_at = now + access_expires
        
        # Refresh token expiration
        refresh_expires = current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES', timedelta(days=7))
        refresh_expires_at = now + refresh_expires
        # JWT payload for access token - include user data from User model
        access_payload = {
            'user_id': user.id,
            'session_id': session_id,
            'type': 'access',
            'iat': now,
            'exp': access_expires_at,
            'nbf': now  # Not valid before
        }
        
        # JWT payload for refresh token
        refresh_payload = {
            'user_id': user.id,
            'session_id': session_id,
            'type': 'refresh',
            'iat': now,
            'exp': refresh_expires_at,
            'nbf': now
        }
        
        # Generate tokens
        jwt_secret = current_app.config['JWT_SECRET_KEY']
        
        access_token = jwt.encode(access_payload, jwt_secret, algorithm='HS256')
        refresh_token = jwt.encode(refresh_payload, jwt_secret, algorithm='HS256')
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': int(access_expires.total_seconds()),
            'token_type': 'Bearer'
        }
    
    @staticmethod
    def validate_token(token: str, token_type: str = 'access') -> Dict[str, Any]:
        """
        Validate a JWT token.
        
        Args:
            token: JWT token string
            token_type: Expected token type ('access' or 'refresh')
            
        Returns:
            Decoded token payload
            
        Raises:
            AuthError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                current_app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )
            
            # Verify token type
            if payload.get('type') != token_type:
                raise AuthError(
                    message=f'Invalid token type. Expected {token_type} token.',
                    status_code=401,
                    error_code='INVALID_TOKEN_TYPE'
                )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise AuthError(
                message='Token has expired',
                status_code=401,
                error_code='TOKEN_EXPIRED'
            )
        except jwt.InvalidTokenError as e:
            raise AuthError(
                message='Invalid token',
                status_code=401,
                error_code='INVALID_TOKEN'
            )
    
    @staticmethod
    def create_session(user: User, ip_address: Optional[str] = None, 
                       user_agent: Optional[str] = None) -> Tuple[UserSession, Dict[str, str]]:
        """
        Create a new user session with tokens.
        
        Args:
            user: User to create session for
            ip_address: Client IP address
            user_agent: Client user agent string
            
        Returns:
            Tuple of (UserSession object, token dictionary)
        """
        # Generate tokens first to get session_id
        tokens = AuthService.generate_token(user)
        
        # Calculate expiration
        access_expires = current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', timedelta(minutes=15))
        expires_at = datetime.utcnow() + access_expires
        
        # Get client info from request if not provided
        if ip_address is None and request:
            ip_address = request.remote_addr
        if user_agent is None and request:
            user_agent = request.headers.get('User-Agent', '')[:512]  # Limit length
        
        # Create session
        session = UserSession(
            user_id=user.id,
            token=tokens['access_token'],
            refresh_token=tokens['refresh_token'],
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Save session to database
        try:
            db.session.add(session)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Database error creating session: {str(e)}')
            raise AuthError(
                message='Failed to create session',
                status_code=500,
                error_code='SESSION_ERROR'
            )
        
        return session, tokens
    
    @staticmethod
    def invalidate_session(session_id: str) -> bool:
        """
        Invalidate a user session (logout).
        
        Args:
            session_id: Session ID to invalidate
            
        Returns:
            True if session was invalidated, False if not found
        """
        session = db.session.query(UserSession).filter_by(id=session_id).first()
        
        if not session:
            return False
        
        try:
            session.invalidate()
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error invalidating session: {str(e)}')
            return False
    
    @staticmethod
    def invalidate_all_user_sessions(user_id: str, except_session_id: Optional[str] = None) -> int:
        """
        # Invalidate all sessions for a user (logout everywhere).
        
        Args:
            user_id: User ID whose sessions to invalidate
            except_session_id: Optional session ID to keep valid
            
        Returns:
            Number of sessions invalidated
        """
        query = db.session.query(UserSession).filter_by(user_id=user_id, is_valid=True)
        
        if except_session_id:
            query = query.filter(UserSession.id != except_session_id)
        
        sessions = query.all()
        count = 0
        
        for session in sessions:
            session.invalidate()
            count += 1
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error invalidating user sessions: {str(e)}')
        
        return count
    
    @staticmethod
    def refresh_token(refresh_token: str) -> Tuple[UserSession, Dict[str, str]]:
        """
        Refresh an access token using a refresh token.
        
        Args:
            refresh_token: Refresh token string
            
        Returns:
            Tuple of (UserSession object, new token dictionary)
            
        Raises:
            AuthError: If refresh token is invalid or session is revoked
        """
        # Validate refresh token
        payload = AuthService.validate_token(refresh_token, token_type='refresh')
        
        session_id = payload.get('session_id')
        user_id = payload.get('user_id')
        
        if not session_id or not user_id:
            raise AuthError(
                message='Invalid refresh token',
                status_code=401,
                error_code='INVALID_REFRESH_TOKEN'
            )
        
        # Find session in database
        from ..models.user_session import UserSession
        session = db.session.query(UserSession).filter_by(
            id=session_id,
            refresh_token=refresh_token,
            is_valid=True
        ).first()
        
        if not session:
            raise AuthError(
                message='Session has been revoked or is invalid',
                status_code=401,
                error_code='SESSION_REVOKED'
            )
        
        if session.is_expired():
            session.invalidate()
            db.session.commit()
            raise AuthError(
                message='Session has expired. Please log in again.',
                status_code=401,
                error_code='SESSION_EXPIRED'
            )
        
        # Get user from database - access via session relationship
        user = session.user if session else None
        if not user:
            user = db.session.query(User).filter_by(id=user_id, is_active=True).first()
        
        if not user:
            raise AuthError(
                message='User not found or account is deactivated',
                status_code=401,
                error_code='USER_NOT_FOUND'
            )
        
        # Generate new tokens
        new_tokens = AuthService.generate_token(user, session_id=session_id)
        
        # Update session with new tokens
        access_expires = current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', timedelta(minutes=15))
        session.token = new_tokens['access_token']
        session.refresh_token = new_tokens['refresh_token']
        session.expires_at = datetime.utcnow() + access_expires
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error refreshing session: {str(e)}')
            raise AuthError(
                message='Failed to refresh session',
                status_code=500,
                error_code='REFRESH_ERROR'
            )
        
        return session, new_tokens
    
    @staticmethod
    def change_password(user: User, current_password: str, new_password: str) -> bool:
        """
        Change a user's password.
        
        Args:
            user: User object
            current_password: Current password for verification
            new_password: New password to set
            
        Returns:
            True if password was changed successfully
            
        Raises:
            AuthError: If current password is wrong or new password is invalid
        """
        # Validate password change data
        is_valid, errors = validate_password_change_data({
            'current_password': current_password,
            'new_password': new_password
        })
        
        if not is_valid:
            raise AuthError(
                message='Validation failed',
                status_code=422,
                error_code='VALIDATION_ERROR'
            )
        
        # Verify current password
        if not user.check_password(current_password):
            raise AuthError(
                message='Current password is incorrect',
                status_code=401,
                error_code='INVALID_CURRENT_PASSWORD'
            )
        
        # Set new password
        user.set_password(new_password)
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error changing password: {str(e)}')
            raise AuthError(
                message='Failed to change password',
                status_code=500,
                error_code='PASSWORD_CHANGE_ERROR'
            )
        
        return True
    
    @staticmethod
    def get_user_profile(user: User) -> Dict[str, Any]:
        """
        Get user profile information.
        
        Args:
            user: User object
            
        Returns:
            Dictionary containing user profile data
        """
        # Get active sessions count
        from ..models.user_session import UserSession
        active_sessions = db.session.query(UserSession).filter_by(
            user_id=user.id,
            is_valid=True
        ).count()
        
        # Build user dict with safe attribute access
        user_dict = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active,
            'is_admin': user.is_admin,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'updated_at': user.updated_at.isoformat() if hasattr(user, 'updated_at') and user.updated_at else None
        }
        
        return {
            'user': user_dict,
            'active_sessions': active_sessions
        }
    
    @staticmethod
    def get_user_sessions(user_id: str, include_expired: bool = False) -> list:
        """
        Get all sessions for a user.
        
        Args:
            user_id: User ID to get sessions for
            include_expired: Whether to include expired sessions
            
        Returns:
            List of session dictionaries
        """
        from ..models.user_session import UserSession
        query = db.session.query(UserSession).filter_by(user_id=user_id)
        
        if not include_expired:
            query = query.filter_by(is_valid=True)
        
        sessions = query.order_by(UserSession.created_at.desc()).all()
        
        return [session.to_dict(include_tokens=False) for session in sessions]
    
    @staticmethod
    def cleanup_expired_sessions() -> int:
        """
        Clean up expired sessions from the database.
        
        Returns:
            Number of sessions cleaned up
        """
        from ..models.user_session import UserSession
        expired_sessions = db.session.query(UserSession).filter(
            UserSession.expires_at < datetime.utcnow()
        ).all()
        
        count = 0
        for session in expired_sessions:
            session.invalidate()
            count += 1
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error cleaning up sessions: {str(e)}')
        
        return count
