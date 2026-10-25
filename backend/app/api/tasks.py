"""
Tasks API Endpoints

Flask-RESTX namespace and REST API endpoints for task management:
- GET /tasks - List tasks with filtering, sorting, and pagination
- POST /tasks - Create a new task
- GET /tasks/:id - Get a specific task
- PUT /tasks/:id - Update a task
- DELETE /tasks/:id - Delete a task
- POST /tasks/:id/complete - Mark task as completed
- POST /tasks/:id/uncomplete - Mark task as active
- GET /tasks/:id/history - Get task history
"""
from flask import request, g
from flask_restx import Namespace, Resource, fields
from datetime import datetime

from ..services.task_service import TaskService, TaskNotFoundError, CategoryNotFoundError, OptimisticLockError
from ..services.stats_service import StatsService
from ..utils.decorators import require_auth, get_current_user
from ..models import TaskStatus, TaskPriority


# Create Flask-RESTX namespace
tasks_ns = Namespace('tasks', description='Task management operations')


# =============================================================================
# API Models (Request/Response Schemas)
# =============================================================================

# Task status enum model
task_status_model = tasks_ns.model('TaskStatus', {
    'value': fields.String(description='Status value', enum=['active', 'completed', 'archived']),
    'label': fields.String(description='Status label')
})

# Task priority enum model
task_priority_model = tasks_ns.model('TaskPriority', {
    'value': fields.String(description='Priority value', enum=['low', 'medium', 'high']),
    'label': fields.String(description='Priority label')
})

# Category reference model
category_ref_model = tasks_ns.model('CategoryRef', {
    'id': fields.String(description='Category ID'),
    'name': fields.String(description='Category name'),
    'color': fields.String(description='Category color hex code')
})

# Task response model
task_model = tasks_ns.model('Task', {
    'id': fields.String(description='Task ID'),
    'title': fields.String(description='Task title'),
    'description': fields.String(description='Task description'),
    'status': fields.String(description='Task status', enum=['active', 'completed', 'archived']),
    'priority': fields.String(description='Task priority', enum=['low', 'medium', 'high']),
    'due_date': fields.String(description='Task due date (ISO format)'),
    'version': fields.Integer(description='Optimistic locking version'),
    'is_overdue': fields.Boolean(description='Whether task is overdue'),
    'user_id': fields.String(description='Task owner ID'),
    'categories': fields.List(fields.Nested(category_ref_model), description='Associated categories'),
    'created_at': fields.String(description='Creation timestamp'),
    'updated_at': fields.String(description='Last update timestamp')
})

# Create task request model
create_task_model = tasks_ns.model('CreateTaskRequest', {
    'title': fields.String(required=True, description='Task title (1-200 chars)'),
    'description': fields.String(description='Task description'),
    'status': fields.String(description='Task status', enum=['active', 'completed', 'archived'], default='active'),
    'priority': fields.String(description='Task priority', enum=['low', 'medium', 'high'], default='medium'),
    'due_date': fields.String(description='Due date (ISO 8601 format)'),
    'category_ids': fields.List(fields.String, description='List of category IDs to associate')
})

# Update task request model
update_task_model = tasks_ns.model('UpdateTaskRequest', {
    'title': fields.String(description='Task title (1-200 chars)'),
    'description': fields.String(description='Task description'),
    'status': fields.String(description='Task status', enum=['active', 'completed', 'archived']),
    'priority': fields.String(description='Task priority', enum=['low', 'medium', 'high']),
    'due_date': fields.String(description='Due date (ISO 8601 format)'),
    'category_ids': fields.List(fields.String, description='List of category IDs to associate'),
    'version': fields.Integer(required=True, description='Current version for optimistic locking')
})

# Complete/uncomplete request model
complete_task_model = tasks_ns.model('CompleteTaskRequest', {
    'version': fields.Integer(required=True, description='Current version for optimistic locking')
})

# Task history entry model
task_history_entry_model = tasks_ns.model('TaskHistoryEntry', {
    'id': fields.String(description='History entry ID'),
    'task_id': fields.String(description='Task ID'),
    'action': fields.String(description='Action performed'),
    'field_changes': fields.Raw(description='Field changes as JSON'),
    'user_id': fields.String(description='User who performed the action'),
    'timestamp': fields.String(description='When the action occurred')
})

# Task list response model
task_list_model = tasks_ns.model('TaskListResponse', {
    'tasks': fields.List(fields.Nested(task_model), description='List of tasks'),
    'total': fields.Integer(description='Total number of tasks'),
    'page': fields.Integer(description='Current page number'),
    'per_page': fields.Integer(description='Items per page'),
    'total_pages': fields.Integer(description='Total number of pages')
})

# Task history response model
task_history_model = tasks_ns.model('TaskHistoryResponse', {
    'history': fields.List(fields.Nested(task_history_entry_model), description='List of history entries'),
    'total': fields.Integer(description='Total number of history entries'),
    'page': fields.Integer(description='Current page number'),
    'per_page': fields.Integer(description='Items per page'),
    'total_pages': fields.Integer(description='Total number of pages')
})

# Success response model
success_response = tasks_ns.model('TaskSuccessResponse', {
    'success': fields.Boolean(description='Operation success status'),
    'message': fields.String(description='Success message'),
    'data': fields.Raw(description='Response data')
})

# Error response model
error_response = tasks_ns.model('TaskErrorResponse', {
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


def parse_datetime(date_string):
    """
    Parse ISO 8601 datetime string.
    
    Args:
        date_string: ISO 8601 formatted datetime string
        
    Returns:
        datetime or None: Parsed datetime or None if invalid
    """
    if not date_string:
        return None
    try:
        # Handle various ISO formats
        if date_string.endswith('Z'):
            date_string = date_string[:-1] + '+00:00'
        return datetime.fromisoformat(date_string)
    except (ValueError, AttributeError):
        return None


def parse_task_status(status_string):
    """
    Parse task status string to TaskStatus enum.
    
    Args:
        status_string: Status string value
        
    Returns:
        TaskStatus or None: Parsed status or None if invalid
    """
    if not status_string:
        return None
    try:
        return TaskStatus(status_string.lower())
    except (ValueError, AttributeError):
        return None


def parse_task_priority(priority_string):
    """
    Parse task priority string to TaskPriority enum.
    
    Args:
        priority_string: Priority string value
        
    Returns:
        TaskPriority or None: Parsed priority or None if invalid
    """
    if not priority_string:
        return None
    try:
        return TaskPriority(priority_string.lower())
    except (ValueError, AttributeError):
        return None


# =============================================================================
# API Resources
# =============================================================================

@tasks_ns.route('')
class TaskListResource(Resource):
    """Task list endpoint for listing and creating tasks."""
    
    @tasks_ns.doc('list_tasks')
    @tasks_ns.doc(security='Bearer')
    @tasks_ns.param('status', 'Filter by status', type='string', enum=['active', 'completed', 'archived'])
    @tasks_ns.param('priority', 'Filter by priority', type='string', enum=['low', 'medium', 'high'])
    @tasks_ns.param('category_id', 'Filter by category ID', type='string')
    @tasks_ns.param('due_date_from', 'Filter by due date >= (ISO format)', type='string')
    @tasks_ns.param('due_date_to', 'Filter by due date <= (ISO format)', type='string')
    @tasks_ns.param('search', 'Search in title and description', type='string')
    @tasks_ns.param('sort_by', 'Sort field', type='string', default='created_at')
    @tasks_ns.param('sort_order', 'Sort order', type='string', enum=['asc', 'desc'], default='desc')
    @tasks_ns.param('page', 'Page number (1-based)', type='integer', default=1)
    @tasks_ns.param('per_page', 'Items per page', type='integer', default=20)
    @tasks_ns.response(200, 'Tasks retrieved successfully', task_list_model)
    @tasks_ns.response(401, 'Authentication required', error_response)
    @tasks_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def get(self):
        """
        Get tasks with filtering, sorting, and pagination.
        
        Returns a paginated list of tasks for the authenticated user.
        Supports filtering by status, priority, category, due date range, and search query.
        """
        try:
            user = get_current_user()
            
            # Parse query parameters
            status = parse_task_status(request.args.get('status'))
            priority = parse_task_priority(request.args.get('priority'))
            category_id = request.args.get('category_id')
            due_date_from = parse_datetime(request.args.get('due_date_from'))
            due_date_to = parse_datetime(request.args.get('due_date_to'))
            search_query = request.args.get('search')
            sort_by = request.args.get('sort_by', 'created_at')
            sort_order = request.args.get('sort_order', 'desc')
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            
            # Validate pagination
            if page < 1:
                page = 1
            if per_page < 1 or per_page > 100:
                per_page = 20
            
            # Get tasks
            result = TaskService.get_tasks(
                user_id=user.id,
                status=status,
                priority=priority,
                category_id=category_id,
                due_date_from=due_date_from,
                due_date_to=due_date_to,
                search_query=search_query,
                sort_by=sort_by,
                sort_order=sort_order,
                page=page,
                per_page=per_page
            )
            
            # Convert tasks to dictionaries
            tasks_data = [task.to_dict(include_categories=True) for task in result['tasks']]
            
            return make_response(
                success=True,
                data={
                    'tasks': tasks_data,
                    'total': result['total'],
                    'page': result['page'],
                    'per_page': result['per_page'],
                    'total_pages': result['total_pages']
                },
                message='Tasks retrieved successfully',
                status_code=200
            )
            
        except Exception as e:
            tasks_ns.logger.error(f'Error retrieving tasks: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while retrieving tasks',
                error_code='TASKS_RETRIEVE_ERROR',
                status_code=500
            )
    
    @tasks_ns.doc('create_task')
    @tasks_ns.doc(security='Bearer')
    @tasks_ns.expect(create_task_model, validate=True)
    @tasks_ns.response(201, 'Task created successfully', success_response)
    @tasks_ns.response(400, 'Invalid request data', error_response)
    @tasks_ns.response(401, 'Authentication required', error_response)
    @tasks_ns.response(404, 'Category not found', error_response)
    @tasks_ns.response(422, 'Validation error', error_response)
    @tasks_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def post(self):
        """
        Create a new task.
        
        Creates a task with the provided data. Optionally associates categories.
        Returns the created task on success.
        """
        try:
            user = get_current_user()
            data = request.get_json()
            
            # Validate required fields
            title = data.get('title', '').strip()
            if not title:
                return make_response(
                    success=False,
                    error='Validation Error',
                    message='Title is required',
                    error_code='MISSING_TITLE',
                    status_code=422
                )
            
            if len(title) > 200:
                return make_response(
                    success=False,
                    error='Validation Error',
                    message='Title must be 200 characters or less',
                    error_code='TITLE_TOO_LONG',
                    status_code=422
                )
            
            # Parse optional fields
            description = data.get('description')
            status = parse_task_status(data.get('status')) or TaskStatus.ACTIVE
            priority = parse_task_priority(data.get('priority')) or TaskPriority.MEDIUM
            due_date = parse_datetime(data.get('due_date'))
            category_ids = data.get('category_ids', [])
            
            # Create task
            task = TaskService.create_task(
                user_id=user.id,
                title=title,
                description=description,
                status=status,
                priority=priority,
                due_date=due_date,
                category_ids=category_ids if category_ids else None
            )
            
            return make_response(
                success=True,
                data={'task': task.to_dict(include_categories=True)},
                message='Task created successfully',
                status_code=201
            )
            
        except CategoryNotFoundError as e:
            return make_response(
                success=False,
                error='Category Not Found',
                message=str(e),
                error_code='CATEGORY_NOT_FOUND',
                status_code=404
            )
        except Exception as e:
            tasks_ns.logger.error(f'Error creating task: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while creating the task',
                error_code='TASK_CREATE_ERROR',
                status_code=500
            )


@tasks_ns.route('/<string:task_id>')
class TaskResource(Resource):
    """Task detail endpoint for getting, updating, and deleting a specific task."""
    
    @tasks_ns.doc('get_task')
    @tasks_ns.doc(security='Bearer')
    @tasks_ns.response(200, 'Task retrieved successfully', success_response)
    @tasks_ns.response(401, 'Authentication required', error_response)
    @tasks_ns.response(404, 'Task not found', error_response)
    @tasks_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def get(self, task_id):
        """
        Get a specific task by ID.
        
        Returns the task details including associated categories.
        """
        try:
            user = get_current_user()
            
            task = TaskService.get_task_by_id(task_id, user.id)
            if not task:
                return make_response(
                    success=False,
                    error='Task Not Found',
                    message=f'Task {task_id} not found',
                    error_code='TASK_NOT_FOUND',
                    status_code=404
                )
            
            return make_response(
                success=True,
                data={'task': task.to_dict(include_categories=True)},
                message='Task retrieved successfully',
                status_code=200
            )
            
        except Exception as e:
            tasks_ns.logger.error(f'Error retrieving task: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while retrieving the task',
                error_code='TASK_RETRIEVE_ERROR',
                status_code=500
            )
    
    @tasks_ns.doc('update_task')
    @tasks_ns.doc(security='Bearer')
    @tasks_ns.expect(update_task_model, validate=True)
    @tasks_ns.response(200, 'Task updated successfully', success_response)
    @tasks_ns.response(400, 'Invalid request data', error_response)
    @tasks_ns.response(401, 'Authentication required', error_response)
    @tasks_ns.response(404, 'Task or category not found', error_response)
    @tasks_ns.response(409, 'Optimistic lock conflict', error_response)
    @tasks_ns.response(422, 'Validation error', error_response)
    @tasks_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def put(self, task_id):
        """
        Update a task.
        
        Updates the task with the provided data. Requires version for optimistic locking.
        Returns the updated task on success.
        """
        try:
            user = get_current_user()
            data = request.get_json()
            
            # Validate version for optimistic locking
            version = data.get('version')
            if version is None:
                return make_response(
                    success=False,
                    error='Validation Error',
                    message='Version is required for optimistic locking',
                    error_code='MISSING_VERSION',
                    status_code=422
                )
            
            # Parse optional fields
            title = data.get('title')
            if title:
                title = title.strip()
                if len(title) > 200:
                    return make_response(
                        success=False,
                        error='Validation Error',
                        message='Title must be 200 characters or less',
                        error_code='TITLE_TOO_LONG',
                        status_code=422
                    )
            
            description = data.get('description')
            status = parse_task_status(data.get('status'))
            priority = parse_task_priority(data.get('priority'))
            due_date = parse_datetime(data.get('due_date'))
            category_ids = data.get('category_ids')
            
            # Update task
            task = TaskService.update_task(
                task_id=task_id,
                user_id=user.id,
                expected_version=version,
                title=title,
                description=description,
                status=status,
                priority=priority,
                due_date=due_date,
                category_ids=category_ids
            )
            
            return make_response(
                success=True,
                data={'task': task.to_dict(include_categories=True)},
                message='Task updated successfully',
                status_code=200
            )
            
        except TaskNotFoundError as e:
            return make_response(
                success=False,
                error='Task Not Found',
                message=str(e),
                error_code='TASK_NOT_FOUND',
                status_code=404
            )
        except OptimisticLockError as e:
            return make_response(
                success=False,
                error='Conflict',
                message=str(e),
                error_code='OPTIMISTIC_LOCK_ERROR',
                status_code=409
            )
        except CategoryNotFoundError as e:
            return make_response(
                success=False,
                error='Category Not Found',
                message=str(e),
                error_code='CATEGORY_NOT_FOUND',
                status_code=404
            )
        except Exception as e:
            tasks_ns.logger.error(f'Error updating task: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while updating the task',
                error_code='TASK_UPDATE_ERROR',
                status_code=500
            )
    
    @tasks_ns.doc('delete_task')
    @tasks_ns.doc(security='Bearer')
    @tasks_ns.response(200, 'Task deleted successfully', success_response)
    @tasks_ns.response(401, 'Authentication required', error_response)
    @tasks_ns.response(404, 'Task not found', error_response)
    @tasks_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def delete(self, task_id):
        """
        Delete a task.
        
        Permanently deletes the task and its associated data (history, tags).
        """
        try:
            user = get_current_user()
            
            TaskService.delete_task(task_id, user.id)
            
            return make_response(
                success=True,
                message='Task deleted successfully',
                status_code=200
            )
            
        except TaskNotFoundError as e:
            return make_response(
                success=False,
                error='Task Not Found',
                message=str(e),
                error_code='TASK_NOT_FOUND',
                status_code=404
            )
        except Exception as e:
            tasks_ns.logger.error(f'Error deleting task: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while deleting the task',
                error_code='TASK_DELETE_ERROR',
                status_code=500
            )


@tasks_ns.route('/<string:task_id>/complete')
class TaskCompleteResource(Resource):
    """Task completion endpoint."""
    
    @tasks_ns.doc('complete_task')
    @tasks_ns.doc(security='Bearer')
    @tasks_ns.expect(complete_task_model, validate=True)
    @tasks_ns.response(200, 'Task completed successfully', success_response)
    @tasks_ns.response(400, 'Invalid request data', error_response)
    @tasks_ns.response(401, 'Authentication required', error_response)
    @tasks_ns.response(404, 'Task not found', error_response)
    @tasks_ns.response(409, 'Optimistic lock conflict', error_response)
    @tasks_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def post(self, task_id):
        """
        Mark a task as completed.
        
        Changes the task status to 'completed'. Requires version for optimistic locking.
        """
        try:
            user = get_current_user()
            data = request.get_json()
            
            # Validate version for optimistic locking
            version = data.get('version')
            if version is None:
                return make_response(
                    success=False,
                    error='Validation Error',
                    message='Version is required for optimistic locking',
                    error_code='MISSING_VERSION',
                    status_code=422
                )
            
            task = TaskService.complete_task(task_id, user.id, version)
            
            return make_response(
                success=True,
                data={'task': task.to_dict(include_categories=True)},
                message='Task completed successfully',
                status_code=200
            )
            
        except TaskNotFoundError as e:
            return make_response(
                success=False,
                error='Task Not Found',
                message=str(e),
                error_code='TASK_NOT_FOUND',
                status_code=404
            )
        except OptimisticLockError as e:
            return make_response(
                success=False,
                error='Conflict',
                message=str(e),
                error_code='OPTIMISTIC_LOCK_ERROR',
                status_code=409
            )
        except Exception as e:
            tasks_ns.logger.error(f'Error completing task: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while completing the task',
                error_code='TASK_COMPLETE_ERROR',
                status_code=500
            )


@tasks_ns.route('/<string:task_id>/uncomplete')
class TaskUncompleteResource(Resource):
    """Task uncompletion endpoint."""
    
    @tasks_ns.doc('uncomplete_task')
    @tasks_ns.doc(security='Bearer')
    @tasks_ns.expect(complete_task_model, validate=True)
    @tasks_ns.response(200, 'Task uncompleted successfully', success_response)
    @tasks_ns.response(400, 'Invalid request data', error_response)
    @tasks_ns.response(401, 'Authentication required', error_response)
    @tasks_ns.response(404, 'Task not found', error_response)
    @tasks_ns.response(409, 'Optimistic lock conflict', error_response)
    @tasks_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def post(self, task_id):
        """
        Mark a completed task as active.
        
        Changes the task status from 'completed' to 'active'. Requires version for optimistic locking.
        """
        try:
            user = get_current_user()
            data = request.get_json()
            
            # Validate version for optimistic locking
            version = data.get('version')
            if version is None:
                return make_response(
                    success=False,
                    error='Validation Error',
                    message='Version is required for optimistic locking',
                    error_code='MISSING_VERSION',
                    status_code=422
                )
            
            task = TaskService.uncomplete_task(task_id, user.id, version)
            
            return make_response(
                success=True,
                data={'task': task.to_dict(include_categories=True)},
                message='Task uncompleted successfully',
                status_code=200
            )
            
        except TaskNotFoundError as e:
            return make_response(
                success=False,
                error='Task Not Found',
                message=str(e),
                error_code='TASK_NOT_FOUND',
                status_code=404
            )
        except OptimisticLockError as e:
            return make_response(
                success=False,
                error='Conflict',
                message=str(e),
                error_code='OPTIMISTIC_LOCK_ERROR',
                status_code=409
            )
        except Exception as e:
            tasks_ns.logger.error(f'Error uncompleting task: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while uncompleting the task',
                error_code='TASK_UNCOMPLETE_ERROR',
                status_code=500
            )


@tasks_ns.route('/<string:task_id>/history')
class TaskHistoryResource(Resource):
    """Task history endpoint."""
    
    @tasks_ns.doc('get_task_history')
    @tasks_ns.doc(security='Bearer')
    @tasks_ns.param('page', 'Page number (1-based)', type='integer', default=1)
    @tasks_ns.param('per_page', 'Items per page', type='integer', default=20)
    @tasks_ns.response(200, 'Task history retrieved successfully', task_history_model)
    @tasks_ns.response(401, 'Authentication required', error_response)
    @tasks_ns.response(404, 'Task not found', error_response)
    @tasks_ns.response(500, 'Internal server error', error_response)
    @require_auth
    def get(self, task_id):
        """
        Get task history (audit log).
        
        Returns a paginated list of history entries for the task.
        """
        try:
            user = get_current_user()
            
            # Parse pagination parameters
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            
            # Validate pagination
            if page < 1:
                page = 1
            if per_page < 1 or per_page > 100:
                per_page = 20
            
            result = TaskService.get_task_history(
                task_id=task_id,
                user_id=user.id,
                page=page,
                per_page=per_page
            )
            
            # Convert history entries to dictionaries
            history_data = [entry.to_dict() for entry in result['history']]
            
            return make_response(
                success=True,
                data={
                    'history': history_data,
                    'total': result['total'],
                    'page': result['page'],
                    'per_page': result['per_page'],
                    'total_pages': result['total_pages']
                },
                message='Task history retrieved successfully',
                status_code=200
            )
            
        except TaskNotFoundError as e:
            return make_response(
                success=False,
                error='Task Not Found',
                message=str(e),
                error_code='TASK_NOT_FOUND',
                status_code=404
            )
        except Exception as e:
            tasks_ns.logger.error(f'Error retrieving task history: {str(e)}')
            return make_response(
                success=False,
                error='Internal Server Error',
                message='An error occurred while retrieving task history',
                error_code='TASK_HISTORY_ERROR',
                status_code=500
            )


# =============================================================================
# Error Handlers for this Namespace
# =============================================================================

@tasks_ns.errorhandler(TaskNotFoundError)
def handle_task_not_found_error(error):
    """Handle TaskNotFoundError exceptions."""
    return make_response(
        success=False,
        error='Task Not Found',
        message=str(error),
        error_code='TASK_NOT_FOUND',
        status_code=404
    )


@tasks_ns.errorhandler(OptimisticLockError)
def handle_optimistic_lock_error(error):
    """Handle OptimisticLockError exceptions."""
    return make_response(
        success=False,
        error='Conflict',
        message=str(error),
        error_code='OPTIMISTIC_LOCK_ERROR',
        status_code=409
    )
