"""
Category Model

SQLAlchemy 2.0 declarative model for task categories with user ownership.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..extensions import db


class Category(db.Model):
    """
    Category model for organizing tasks.
    
    Categories are user-owned and can be assigned to tasks for grouping.
    Each category has a name and optional color for visual distinction.
    
    Attributes:
        id: UUID primary key
        name: Category name (unique per user)
        color: Hex color code for UI display
        user_id: Foreign key to users table (owner)
        created_at: Category creation timestamp
    """
    
    __tablename__ = 'categories'
    
    # Primary key - UUID for security and scalability
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    # Category name - unique per user
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    
    # Color hex code for UI (e.g., '#FF5733')
    color: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
        default=None
    )
    
    # Foreign key to users table with cascade delete
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationship to User model
    user: Mapped['User'] = relationship('User', back_populates='categories')
    
    # Relationship to TaskTag (junction table)
    task_tags: Mapped[list['TaskTag']] = relationship(
        'TaskTag',
        back_populates='category',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    
    def to_dict(self, include_user: bool = False) -> dict:
        """
        Convert category to dictionary representation.
        
        Args:
            include_user: Whether to include user data
            
        Returns:
            dict: Category data dictionary
        """
        data = {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_user and self.user:
            data['user'] = self.user.to_dict()
            
        return data
    
    def __repr__(self) -> str:
        """String representation of Category."""
        return f"<Category(id={self.id}, name={self.name}, user_id={self.user_id})>"
