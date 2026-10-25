"""
User Session Model

SQLAlchemy 2.0 declarative model for user session management with JWT token tracking.
"""
import uuid
import secrets
from datetime import datetime, timedelta
from sqlalchemy import String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..extensions import db


class UserSession(db.Model):
    """
    User session model for JWT token lifecycle management.
    
    Tracks active user sessions with token metadata, expiration,
    and client information for security auditing.
    
    Attributes:
        id: UUID primary key
        user_id: Foreign key to users table
        token: JWT access token (64+ characters)
        refresh_token: JWT refresh token for session renewal
        expires_at: Token expiration timestamp
        is_valid: Session validity flag (for revocation)
        ip_address: Client IP address
        user_agent: Client user agent string
        created_at: Session creation timestamp
    """
    
    __tablename__ = 'user_sessions'
    
    # Primary key - UUID for security
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    # Foreign key to users table with cascade delete
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # JWT tokens
    token: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        unique=True,
        index=True
    )
    
    refresh_token: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        unique=True,
        index=True
    )
    
    # Expiration tracking
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True
    )
    
    # Session validity flag (for soft revocation)
    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True
    )
    
    # Client metadata for security auditing
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True
    )
    
    user_agent: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationship to User model
    user: Mapped['User'] = relationship('User', back_populates='sessions')
    
    def __init__(self, user_id: str, token: str, refresh_token: str, 
                 expires_at: datetime, ip_address: str | None = None, 
                 user_agent: str | None = None):
        """
        Initialize a new user session.
        
        Args:
            user_id: UUID of the associated user
            token: JWT access token
            refresh_token: JWT refresh token
            expires_at: Token expiration datetime
            ip_address: Client IP address (optional)
            user_agent: Client user agent string (optional)
        """
        self.user_id = user_id
        self.token = token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.is_valid = True
    
    def is_expired(self) -> bool:
        """
        Check if the session token has expired.
        
        Returns:
            bool: True if expired, False otherwise
        """
        return datetime.utcnow() > self.expires_at
    
    def is_active(self) -> bool:
        """
        Check if the session is active (valid and not expired).
        
        Returns:
            bool: True if session is active, False otherwise
        """
        return self.is_valid and not self.is_expired()
    
    def invalidate(self) -> None:
        """
        Mark the session as invalid (soft delete/revocation).
        """
        self.is_valid = False
    
    def to_dict(self, include_tokens: bool = False) -> dict:
        """
        Convert session to dictionary representation.
        
        Args:
            include_tokens: Whether to include token values
            
        Returns:
            dict: Session data dictionary
        """
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'is_valid': self.is_valid,
            'is_expired': self.is_expired(),
            'is_active': self.is_active(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_tokens:
            data['token'] = self.token
            data['refresh_token'] = self.refresh_token
            
        return data
    
    def __repr__(self) -> str:
        """String representation of UserSession."""
        return f"<UserSession(id={self.id}, user_id={self.user_id}, is_active={self.is_active()})>"
    
    @staticmethod
    def _attach_user_relationship():
        """Attach sessions relationship to User model after both are defined."""
        from .user import User
        from sqlalchemy.orm import relationship
        User.sessions = relationship(
            'UserSession',
            back_populates='user',
            cascade='all, delete-orphan',
            lazy='dynamic'
        )
