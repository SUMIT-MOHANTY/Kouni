"""
Admin API Endpoints

Flask-RESTX namespace for administrative operations including user management,
system health checks, and metrics monitoring.

All endpoints require admin privileges.
"""
from flask import request, g
from flask_restx import Namespace, Resource, fields
from typing import Dict, Any

from ..extensions import db
from ..services.admin_service import AdminService, AdminServiceError, UserNotFoundError, CannotDeleteAdminError
from ..utils.decorators import require_auth, require_admin


# Create admin namespace
admin_ns = Namespace('admin', description='Administrative operations', path='/admin')


# =============================================================================
# API Models (Request/Response Schemas)
# =============================================================================

# User list response model
user_list_model = admin_ns.model('UserListResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'users': fields.List(fields.Raw, description='List of users'),
    'total': fields.Integer(description='Total number of users'),
    'page': fields.Integer(description='Current page number'),
    'per_page': fields.Integer(description='Items per page'),
    'total_pages': fields.Integer(description='Total number of pages')
})

# Single user response model
user_detail_model = admin_ns.model('UserDetailResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'user': fields.Raw(description='User details with statistics')
})

# User activation response model
user_activation_model = admin_ns.model('UserActivationResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'message': fields.String(description='Status message'),
    'user': fields.Raw(description='Updated user data')
})

# Delete response model
delete_response_model = admin_ns.model('DeleteResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'message': fields.String(description='Status message')
})

# Health check response model
health_response_model = admin_ns.model('HealthResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'status': fields.String(description='Overall system status'),
    'timestamp': fields.DateTime(description='Check timestamp'),
    'checks': fields.Raw(description='Detailed health check results')
})

# Metrics response model
metrics_response_model = admin_ns.model('MetricsResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'metrics': fields.Raw(description='System metrics data')
})

# Error response model
error_model = admin_ns.model('ErrorResponse', {
    'success': fields.Boolean(default=False, description='Operation success status'),
    'error': fields.String(description='Error type'),
    'message': fields.String(description='Error message')
})


# =============================================================================
# Helper Functions
# =============================================================================

def make_response(success: bool, data: Dict[str, Any] = None, status_code: int = 200) -> tuple:
    """
    Create a standardized API response.
    
    Args:
        success: Whether the operation was successful
        data: Response data dictionary
        status_code: HTTP status code
        
    Returns:
        tuple: (response_dict, status_code)
    """
    response = {'success': success}
    if data:
        response.update(data)
    return response, status_code


def handle_admin_error(error: AdminServiceError) -> tuple:
    """
    Handle AdminServiceError exceptions.
    
    Args:
        error: The AdminServiceError exception
        
    Returns:
        tuple: (error_response, status_code)
    """
    return make_response(
        success=False,
        data={
            'error': error.error_code or 'ADMIN_ERROR',
            'message': error.message
        },
        status_code=error.status_code
    )


# =============================================================================
# API Resources
# =============================================================================

@admin_ns.route('/users')
class UserListResource(Resource):
    """
    Resource for listing and managing users.
    
    GET: Get paginated list of users with filtering
    """
    
    @admin_ns.doc(
        'list_users',
        description='Get paginated list of users with optional filtering',
        security='bearer',
        params={
            'page': {'description': 'Page number (1-based)', 'type': 'integer', 'default': 1},
            'per_page': {'description': 'Items per page', 'type': 'integer', 'default': 20},
            'is_active': {'description': 'Filter by active status', 'type': 'boolean'},
            'is_admin': {'description': 'Filter by admin status', 'type': 'boolean'},
            'search': {'description': 'Search in username and email', 'type': 'string'},
            'sort_by': {'description': 'Field to sort by', 'type': 'string', 'default': 'created_at'},
            'sort_order': {'description': 'Sort order (asc/desc)', 'type': 'string', 'default': 'desc'}
        },
        responses={
            200: ('Success', user_list_model),
            401: ('Unauthorized', error_model),
            403: ('Forbidden - Admin required', error_model),
            500: ('Internal server error', error_model)
        }
    )
    @require_auth
    @require_admin
    def get(self):
        """Get paginated list of users with filtering and sorting."""
        try:
            # Get query parameters
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            is_active = request.args.get('is_active', type=lambda x: x.lower() == 'true' if x else None)
            is_admin = request.args.get('is_admin', type=lambda x: x.lower() == 'true' if x else None)
            search_query = request.args.get('search', None)
            sort_by = request.args.get('sort_by', 'created_at')
            sort_order = request.args.get('sort_order', 'desc')
            
            # Validate pagination
            if page < 1:
                page = 1
            if per_page < 1:
                per_page = 20
            if per_page > 100:
                per_page = 100
            
            # Get users from service
            result = AdminService.get_users(
                page=page,
                per_page=per_page,
                is_active=is_active,
                is_admin=is_admin,
                search_query=search_query,
                sort_by=sort_by,
                sort_order=sort_order
            )
            
            return make_response(
                success=True,
                data=result
            )
            
        except AdminServiceError as e:
            return handle_admin_error(e)
        except Exception as e:
            return make_response(
                success=False,
                data={
                    'error': 'INTERNAL_ERROR',
                    'message': f'An error occurred: {str(e)}'
                },
                status_code=500
            )


@admin_ns.route('/users/<string:user_id>')
class UserResource(Resource):
    """
    Resource for managing individual users.
    
    GET: Get user details
    PUT: Activate/deactivate user
    DELETE: Hard delete user
    """
    
    @admin_ns.doc(
        'get_user',
        description='Get detailed information about a specific user',
        security='bearer',
        params={
            'user_id': {'description': 'User UUID', 'type': 'string', 'required': True}
        },
        responses={
            200: ('Success', user_detail_model),
            401: ('Unauthorized', error_model),
            403: ('Forbidden - Admin required', error_model),
            404: ('User not found', error_model),
            500: ('Internal server error', error_model)
        }
    )
    @require_auth
    @require_admin
    def get(self, user_id: str):
        """Get detailed user information by ID."""
        try:
            user_data = AdminService.get_user_by_id(user_id)
            
            return make_response(
                success=True,
                data={'user': user_data}
            )
            
        except UserNotFoundError as e:
            return handle_admin_error(e)
        except AdminServiceError as e:
            return handle_admin_error(e)
        except Exception as e:
            return make_response(
                success=False,
                data={
                    'error': 'INTERNAL_ERROR',
                    'message': f'An error occurred: {str(e)}'
                },
                status_code=500
            )
    
    @admin_ns.doc(
        'update_user_status',
        description='Activate or deactivate a user account',
        security='bearer',
        params={
            'user_id': {'description': 'User UUID', 'type': 'string', 'required': True}
        },
        body=admin_ns.model('UserStatusUpdate', {
            'is_active': fields.Boolean(required=True, description='New active status')
        }),
        responses={
            200: ('Success', user_activation_model),
            400: ('Bad request', error_model),
            401: ('Unauthorized', error_model),
            403: ('Forbidden - Admin required', error_model),
            404: ('User not found', error_model),
            500: ('Internal server error', error_model)
        }
    )
    @require_auth
    @require_admin
    def put(self, user_id: str):
        """Activate or deactivate a user account."""
        try:
            data = request.get_json()
            
            if data is None or 'is_active' not in data:
                return make_response(
                    success=False,
                    data={
                        'error': 'VALIDATION_ERROR',
                        'message': 'is_active field is required'
                    },
                    status_code=400
                )
            
            is_active = data.get('is_active')
            
            if is_active:
                result = AdminService.activate_user(user_id)
            else:
                result = AdminService.deactivate_user(user_id)
            
            return make_response(
                success=result['success'],
                data=result
            )
            
        except UserNotFoundError as e:
            return handle_admin_error(e)
        except AdminServiceError as e:
            return handle_admin_error(e)
        except Exception as e:
            return make_response(
                success=False,
                data={
                    'error': 'INTERNAL_ERROR',
                    'message': f'An error occurred: {str(e)}'
                },
                status_code=500
            )
    
    @admin_ns.doc(
        'delete_user',
        description='Hard delete a user and all associated data (cascade)',
        security='bearer',
        params={
            'user_id': {'description': 'User UUID', 'type': 'string', 'required': True}
        },
        responses={
            200: ('Success', delete_response_model),
            401: ('Unauthorized', error_model),
            403: ('Forbidden - Admin required or cannot delete last admin', error_model),
            404: ('User not found', error_model),
            500: ('Internal server error', error_model)
        }
    )
    @require_auth
    @require_admin
    def delete(self, user_id: str):
        """Hard delete a user and all associated data."""
        try:
            result = AdminService.delete_user(user_id)
            
            return make_response(
                success=result['success'],
                data=result
            )
            
        except UserNotFoundError as e:
            return handle_admin_error(e)
        except CannotDeleteAdminError as e:
            return handle_admin_error(e)
        except AdminServiceError as e:
            return handle_admin_error(e)
        except Exception as e:
            return make_response(
                success=False,
                data={
                    'error': 'INTERNAL_ERROR',
                    'message': f'An error occurred: {str(e)}'
                },
                status_code=500
            )


@admin_ns.route('/health')
class HealthResource(Resource):
    """
    Resource for system health checks.
    
    GET: Get detailed system health status
    """
    
    @admin_ns.doc(
        'get_health',
        description='Get detailed system health status including database connectivity',
        security='bearer',
        responses={
            200: ('Success', health_response_model),
            401: ('Unauthorized', error_model),
            403: ('Forbidden - Admin required', error_model),
            500: ('Internal server error', error_model)
        }
    )
    @require_auth
    @require_admin
    def get(self):
        """Get detailed system health status."""
        try:
            health_data = AdminService.get_system_health()
            
            return make_response(
                success=True,
                data=health_data
            )
            
        except AdminServiceError as e:
            return handle_admin_error(e)
        except Exception as e:
            return make_response(
                success=False,
                data={
                    'error': 'INTERNAL_ERROR',
                    'message': f'An error occurred: {str(e)}'
                },
                status_code=500
            )


@admin_ns.route('/metrics')
class MetricsResource(Resource):
    """
    Resource for system metrics.
    
    GET: Get aggregated system statistics
    """
    
    @admin_ns.doc(
        'get_metrics',
        description='Get aggregated system metrics including user counts, task statistics, and recent activity',
        security='bearer',
        params={
            'days': {'description': 'Number of days for recent activity metrics', 'type': 'integer', 'default': 30}
        },
        responses={
            200: ('Success', metrics_response_model),
            401: ('Unauthorized', error_model),
            403: ('Forbidden - Admin required', error_model),
            500: ('Internal server error', error_model)
        }
    )
    @require_auth
    @require_admin
    def get(self):
        """Get aggregated system metrics."""
        try:
            days = request.args.get('days', 30, type=int)
            
            if days < 1:
                days = 30
            if days > 365:
                days = 365
            
            metrics_data = AdminService.get_system_metrics(days=days)
            
            return make_response(
                success=True,
                data={'metrics': metrics_data}
            )
            
        except AdminServiceError as e:
            return handle_admin_error(e)
        except Exception as e:
            return make_response(
                success=False,
                data={
                    'error': 'INTERNAL_ERROR',
                    'message': f'An error occurred: {str(e)}'
                },
                status_code=500
            )
