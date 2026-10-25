"""
Categories API Endpoints

Flask-RESTX namespace and REST API endpoints for category management:
- GET /categories - List all categories for the current user
- POST /categories - Create a new category
- GET /categories/:id - Get a specific category
- PUT /categories/:id - Update a category
- DELETE /categories/:id - Delete a category
"""
from flask import request, g
from flask_restx import Namespace, Resource, fields
from datetime import datetime

from ..services.task_service import TaskService, TaskServiceError, TaskNotFoundError, CategoryNotFoundError, OptimisticLockError
from ..services.stats_service import StatsService
from ..utils.decorators import require_auth, get_current_user
from ..models import Category, Task, TaskTag
from ..extensions import db


# Create Flask-RESTX namespace
categories_ns = Namespace('categories', description='Category management operations')


# =============================================================================
# API Models (Request/Response Schemas)
# =============================================================================

# Category request model
category_request_model = categories_ns.model('CategoryRequest', {
    'name': fields.String(required=True, description='Category name (1-50 characters)'),
    'color': fields.String(required=False, description='Hex color code (e.g., #FF5733)')
})

# Category response model
category_model = categories_ns.model('Category', {
    'id': fields.String(description='Category ID'),
    'name': fields.String(description='Category name'),
    'color': fields.String(description='Hex color code'),
    'user_id': fields.String(description='Owner user ID'),
    'task_count': fields.Integer(description='Number of tasks in this category'),
    'created_at': fields.String(description='Creation timestamp')
})

# Category list response model
category_list_model = categories_ns.model('CategoryListResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'message': fields.String(description='Response message'),
    'data': fields.Raw(description='Response data containing categories list')
})

# Category detail response model
category_detail_model = categories_ns.model('CategoryDetailResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'message': fields.String(description='Response message'),
    'data': fields.Raw(description='Response data containing category details')
})

# Error response model
error_response = categories_ns.model('ErrorResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'error': fields.String(description='Error type'),
    'message': fields.String(description='Error message'),
    'error_code': fields.String(description='Error code for client handling')
})


# =============================================================================
# Helper Functions
# =============================================================================

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


def get_category_with_task_count(category_id: str, user_id: str) -> dict:
    """
    Get category details with task count.
    
    Args:
        category_id: UUID of the category
        user_id: UUID of the user
        
    Returns:
        dict: Category data with task count
    """
    from sqlalchemy import select
    category = db.session.execute(select(Category).where(Category.id == category_id)).scalar_one_or_none()
    
    if not category or category.user_id != user_id:
        return None
    
    from sqlalchemy import select, func
    # Get task count for this category
    task_count = db.session.execute(
        select(func.count(TaskTag.id)).where(TaskTag.category_id == category_id)
    ).scalar()
    
    data = category.to_dict()
    data['task_count'] = task_count
    
    return data


def get_user_categories_with_counts(user_id: str) -> list:
    """
    Get all categories for a user with task counts.
    
    Args:
        user_id: UUID of the user
        
    Returns:
        list: List of category data with task counts
    """
    from sqlalchemy import select
    categories = db.session.execute(
        select(Category).where(Category.user_id == user_id).order_by(Category.name)
    ).scalars().all()
    
    result = []
    for category in categories:
        from sqlalchemy import select, func
        task_count = db.session.execute(
            select(func.count(TaskTag.id)).where(TaskTag.category_id == category.id)
        ).scalar()
        data = category.to_dict()
        data['task_count'] = task_count
        result.append(data)
    
    return result


# =============================================================================
# API Resources
# =============================================================================

@categories_ns.route('/')
class CategoryListResource(Resource):
    """Category list endpoint - list all and create new."""
    
    @categories_ns.doc('list_categories')
    @categories_ns.doc(security='Bearer')
    @categories_ns.response(200, 'Categories retrieved successfully', category_list_model)
    @categories_ns.response(401, 'Authentication required', error_response)
    @categories_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def get(self):
        """
        Get all categories for the current user.
        
        Returns a list of all categories owned by the authenticated user,
        including the task count for each category.
        """
        try:
            user = get_current_user()
            categories = get_user_categories_with_counts(user.id)
            
            return make_response(
                success=True,
                data={'categories': categories},
                message='Categories retrieved successfully',
                status_code=200
            )
            
        except Exception as e:
            categories_ns.logger.error(f'Error retrieving categories: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while retrieving categories',
                error_code='CATEGORIES_RETRIEVE_ERROR',
                status_code=500
            )
    
    @categories_ns.doc('create_category')
    @categories_ns.doc(security='Bearer')
    @categories_ns.expect(category_request_model, validate=True)
    @categories_ns.response(201, 'Category created successfully', category_detail_model)
    @categories_ns.response(400, 'Validation error', error_response)
    @categories_ns.response(401, 'Authentication required', error_response)
    @categories_ns.response(409, 'Category already exists', error_response)
    @categories_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def post(self):
        """
        Create a new category.
        
        Creates a new category with the provided name and optional color.
        Category names must be unique per user.
        """
        try:
            user = get_current_user()
            data = request.get_json()
            
            # Extract and validate fields
            name = data.get('name', '').strip()
            color = data.get('color', '').strip() if data.get('color') else None
            
            # Validate name
            if not name:
                return make_response(
                    success=False,
                    error='Validation Error',
                    message='Category name is required',
                    error_code='MISSING_CATEGORY_NAME',
                    status_code=400
                )
            
            if len(name) > 50:
                return make_response(
                    success=False,
                    error='Validation Error',
                    message='Category name must be 50 characters or less',
                    error_code='CATEGORY_NAME_TOO_LONG',
                    status_code=400
                )
            
            # Validate color format if provided
            if color and not _is_valid_hex_color(color):
                return make_response(
                    success=False,
                    error='Validation Error',
                    message='Color must be a valid hex color code (e.g., #FF5733)',
                    error_code='INVALID_COLOR_FORMAT',
                    status_code=400
                )
            
            # Check for duplicate category name for this user
            from sqlalchemy import select
            existing = db.session.execute(
                select(Category).where(Category.name == name, Category.user_id == user.id)
            ).scalar_one_or_none()
            
            if existing:
                return make_response(
                    success=False,
                    error='Conflict',
                    message=f'Category "{name}" already exists',
                    error_code='CATEGORY_ALREADY_EXISTS',
                    status_code=409
                )
            
            # Create the category
            category = Category(
                name=name,
                color=color,
                user_id=user.id
            )
            
            db.session.add(category)
            db.session.commit()
            
            return make_response(
                success=True,
                data={'category': category.to_dict()},
                message='Category created successfully',
                status_code=201
            )
            
        except Exception as e:
            db.session.rollback()
            categories_ns.logger.error(f'Error creating category: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while creating the category',
                error_code='CATEGORY_CREATE_ERROR',
                status_code=500
            )


@categories_ns.route('/<string:category_id>')
class CategoryResource(Resource):
    """Category detail endpoint - get, update, delete."""
    
    @categories_ns.doc('get_category')
    @categories_ns.doc(security='Bearer')
    @categories_ns.response(200, 'Category retrieved successfully', category_detail_model)
    @categories_ns.response(401, 'Authentication required', error_response)
    @categories_ns.response(404, 'Category not found', error_response)
    @categories_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def get(self, category_id):
        """
        Get a specific category by ID.
        
        Returns the category details including task count.
        """
        try:
            user = get_current_user()
            
            category = get_category_with_task_count(category_id, user.id)
            
            if not category:
                return make_response(
                    success=False,
                    error='Not Found',
                    message='Category not found',
                    error_code='CATEGORY_NOT_FOUND',
                    status_code=404
                )
            
            return make_response(
                success=True,
                data={'category': category},
                message='Category retrieved successfully',
                status_code=200
            )
            
        except Exception as e:
            categories_ns.logger.error(f'Error retrieving category: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while retrieving the category',
                error_code='CATEGORY_RETRIEVE_ERROR',
                status_code=500
            )
    
    @categories_ns.doc('update_category')
    @categories_ns.doc(security='Bearer')
    @categories_ns.expect(category_request_model, validate=True)
    @categories_ns.response(200, 'Category updated successfully', category_detail_model)
    @categories_ns.response(400, 'Validation error', error_response)
    @categories_ns.response(401, 'Authentication required', error_response)
    @categories_ns.response(404, 'Category not found', error_response)
    @categories_ns.response(409, 'Category name already exists', error_response)
    @categories_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def put(self, category_id):
        """
        Update a category.
        
        Updates the category name and/or color. Category names must be unique per user.
        """
        try:
            user = get_current_user()
            data = request.get_json()
            
            # Find the category
            from sqlalchemy import select
            category = db.session.execute(
                select(Category).where(Category.id == category_id)
            ).scalar_one_or_none()
            
            if category and category.user_id != user.id:
                category = None
            
            if not category:
                return make_response(
                    success=False,
                    error='Not Found',
                    message='Category not found',
                    error_code='CATEGORY_NOT_FOUND',
                    status_code=404
                )
            
            # Extract fields
            name = data.get('name', '').strip() if data.get('name') else None
            color = data.get('color', '').strip() if data.get('color') else None
            
            # Validate name if provided
            if name:
                if len(name) > 50:
                    return make_response(
                        success=False,
                        error='Validation Error',
                        message='Category name must be 50 characters or less',
                        error_code='CATEGORY_NAME_TOO_LONG',
                        status_code=400
                    )
                
                # Check for duplicate name (excluding current category)
                from sqlalchemy import select
                existing = db.session.execute(
                    select(Category).where(
                        Category.name == name,
                        Category.user_id == user.id,
                        Category.id != category_id
                    )
                ).scalar_one_or_none()
                
                if existing:
                    return make_response(
                        success=False,
                        error='Conflict',
                        message=f'Category "{name}" already exists',
                        error_code='CATEGORY_ALREADY_EXISTS',
                        status_code=409
                    )
                
                category.name = name
            
            # Validate and update color if provided
            if color is not None:
                if color and not _is_valid_hex_color(color):
                    return make_response(
                        success=False,
                        error='Validation Error',
                        message='Color must be a valid hex color code (e.g., #FF5733)',
                        error_code='INVALID_COLOR_FORMAT',
                        status_code=400
                    )
                category.color = color if color else None
            
            db.session.commit()
            
            return make_response(
                success=True,
                data={'category': get_category_with_task_count(category_id, user.id)},
                message='Category updated successfully',
                status_code=200
            )
            
        except Exception as e:
            db.session.rollback()
            categories_ns.logger.error(f'Error updating category: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while updating the category',
                error_code='CATEGORY_UPDATE_ERROR',
                status_code=500
            )
    
    @categories_ns.doc('delete_category')
    @categories_ns.doc(security='Bearer')
    @categories_ns.response(200, 'Category deleted successfully')
    @categories_ns.response(401, 'Authentication required', error_response)
    @categories_ns.response(404, 'Category not found', error_response)
    @categories_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def delete(self, category_id):
        """
        Delete a category.
        
        Deletes the category and removes all associations with tasks.
        Tasks themselves are not deleted.
        """
        try:
            user = get_current_user()
            
            from sqlalchemy import select
            category = db.session.execute(
                select(Category).where(Category.id == category_id)
            ).scalar_one_or_none()
            
            if category and category.user_id != user.id:
                category = None
            
            if not category:
                return make_response(
                    success=False,
                    error='Not Found',
                    message='Category not found',
                    error_code='CATEGORY_NOT_FOUND',
                    status_code=404
                )
            
            # Delete the category (cascade will handle task_tags)
            db.session.delete(category)
            db.session.commit()
            
            return make_response(
                success=True,
                message='Category deleted successfully',
                status_code=200
            )
            
        except Exception as e:
            db.session.rollback()
            categories_ns.logger.error(f'Error deleting category: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while deleting the category',
                error_code='CATEGORY_DELETE_ERROR',
                status_code=500
            )


# =============================================================================
# Utility Functions
# =============================================================================

def _is_valid_hex_color(color: str) -> bool:
    """
    Validate hex color code format.
    
    Args:
        color: Color string to validate
        
    Returns:
        bool: True if valid hex color, False otherwise
    """
    if not color:
        return True  # Empty is valid (no color)
    
    # Check format: #RGB or #RRGGBB
    if not color.startswith('#'):
        return False
    
    hex_part = color[1:]
    
    # Must be 3 or 6 hex digits
    if len(hex_part) not in (3, 6):
        return False
    
    # All characters must be valid hex digits
    try:
        int(hex_part, 16)
        return True
    except ValueError:
        return False


# =============================================================================
# Error Handlers for this Namespace
# =============================================================================

@categories_ns.errorhandler(CategoryNotFoundError)
def handle_category_not_found_error(error):
    """Handle CategoryNotFoundError exceptions."""
    return make_response(
        success=False,
        error='Not Found',
        message=str(error),
        error_code='CATEGORY_NOT_FOUND',
        status_code=404
    )


@categories_ns.errorhandler(TaskServiceError)
def handle_task_service_error(error):
    """Handle TaskServiceError exceptions."""
    return make_response(
        success=False,
        error='Service Error',
        message=str(error),
        error_code='TASK_SERVICE_ERROR',
        status_code=400
    )
