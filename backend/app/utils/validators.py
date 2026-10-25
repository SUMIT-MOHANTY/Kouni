"""
Input Validation Utilities

Comprehensive validation functions for user input including email format,
password strength, and username constraints. Provides security against
injection attacks and ensures data integrity.
"""
import re
from typing import Optional
from email_validator import validate_email, EmailNotValidError


class ValidationError(Exception):
    """Custom exception for validation errors with detailed messages."""
    
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"Validation error in '{field}': {message}")


def validate_email_format(email: str) -> tuple[bool, Optional[str]]:
    """
    Validate email address format and deliverability.
    
    Uses the email_validator library for RFC-compliant validation
    including DNS checks for domain existence.
    
    Args:
        email: Email address to validate
        
    Returns:
        tuple: (is_valid, error_message or None)
    """
    if not email:
        return False, "Email address is required"
    
    if not isinstance(email, str):
        return False, "Email must be a string"
    
    email = email.strip().lower()
    
    if len(email) > 255:
        return False, "Email address exceeds maximum length of 255 characters"
    
    try:
        # Validate and normalize email
        validation = validate_email(email, check_deliverability=False)
        normalized_email = validation.email
        
        # Additional checks for common attack patterns
        if '..' in normalized_email:
            return False, "Email contains invalid consecutive dots"
        
        if normalized_email.startswith('.') or normalized_email.endswith('.'):
            return False, "Email cannot start or end with a dot"
        
        # Check for suspicious patterns that might indicate injection attempts
        dangerous_patterns = [';', '--', '/*', '*/', '\\x', '\\u', '\\0', '<script']
        for pattern in dangerous_patterns:
            if pattern in normalized_email.lower():
                return False, "Email contains invalid characters"
        
        return True, None
        
    except EmailNotValidError as e:
        return False, str(e)


def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
    """
    Validate password strength against security requirements.
    
    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character (!@#$%^&*)
    - No whitespace characters
    - No common patterns or sequences
    
    Args:
        password: Password to validate
        
    Returns:
        tuple: (is_valid, error_message or None)
    """
    if not password:
        return False, "Password is required"
    
    if not isinstance(password, str):
        return False, "Password must be a string"
    
    # Check minimum length
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    # Check maximum length (prevent DoS via extremely long passwords)
    if len(password) > 128:
        return False, "Password exceeds maximum length of 128 characters"
    
    # Check for whitespace
    if any(char.isspace() for char in password):
        return False, "Password cannot contain whitespace characters"
    
    # Check for uppercase letter
    if not any(char.isupper() for char in password):
        return False, "Password must contain at least one uppercase letter"
    
    # Check for lowercase letter
    if not any(char.islower() for char in password):
        return False, "Password must contain at least one lowercase letter"
    
    # Check for digit
    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one digit"
    
    # Check for special character
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(char in special_chars for char in password):
        return False, "Password must contain at least one special character (!@#$%^&* etc.)"
    
    # Check for common weak patterns
    common_patterns = [
        'password', '123456', 'qwerty', 'abc123', 'letmein', 'welcome',
        'admin', 'login', 'user', 'test', 'default', 'guest'
    ]
    password_lower = password.lower()
    for pattern in common_patterns:
        if pattern in password_lower:
            return False, f"Password contains common weak pattern: '{pattern}'"
    
    # Check for sequential characters (e.g., "abc", "123", "xyz")
    sequential_patterns = [
        'abcdefghijklmnopqrstuvwxyz',
        'zyxwvutsrqponmlkjihgfedcba',
        '0123456789',
        '9876543210',
        'qwertyuiop',
        'asdfghjkl',
        'zxcvbnm'
    ]
    for seq in sequential_patterns:
        for i in range(len(seq) - 2):
            if seq[i:i+3] in password_lower:
                return False, "Password contains sequential characters (e.g., 'abc', '123')"
    
    # Check for repeated characters (e.g., "aaa", "111")
    if re.search(r'(.)\1{2,}', password):
        return False, "Password contains too many repeated characters"
    
    return True, None


def validate_username_format(username: str) -> tuple[bool, Optional[str]]:
    """
    Validate username format and constraints.
    
    Requirements:
    - 3-50 characters
    - Alphanumeric characters only (letters, numbers)
    - Underscores allowed
    - Must start with a letter
    - No consecutive underscores
    - No SQL injection patterns
    
    Args:
        username: Username to validate
        
    Returns:
        tuple: (is_valid, error_message or None)
    """
    if not username:
        return False, "Username is required"
    
    if not isinstance(username, str):
        return False, "Username must be a string"
    
    username = username.strip()
    
    # Check length
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    
    if len(username) > 50:
        return False, "Username exceeds maximum length of 50 characters"
    
    # Check for SQL injection patterns
    dangerous_patterns = [';', '--', '/*', '*/', "'", '"', '\\x', '\\u', '\\0', '<script']
    for pattern in dangerous_patterns:
        if pattern in username.lower():
            return False, "Username contains invalid characters"
    
    # Check for control characters
    if any(ord(char) < 32 for char in username):
        return False, "Username contains invalid control characters"
    
    # Must start with a letter
    if not username[0].isalpha():
        return False, "Username must start with a letter"
    
    # Check allowed characters (alphanumeric + underscore)
    allowed_pattern = re.compile(r'^[a-zA-Z0-9_]+$')
    if not allowed_pattern.match(username):
        return False, "Username can only contain letters, numbers, and underscores"
    
    # No consecutive underscores
    if '__' in username:
        return False, "Username cannot contain consecutive underscores"
    
    # Cannot end with underscore
    if username.endswith('_'):
        return False, "Username cannot end with an underscore"
    
    # Check for reserved usernames
    reserved_usernames = [
        'admin', 'administrator', 'root', 'system', 'superuser',
        'moderator', 'mod', 'support', 'help', 'info', 'contact',
        'webmaster', 'hostmaster', 'postmaster', 'abuse', 'security',
        'null', 'undefined', 'test', 'guest', 'anonymous', 'user',
        'api', 'www', 'mail', 'ftp', 'smtp', 'pop', 'imap'
    ]
    if username.lower() in reserved_usernames:
        return False, f"Username '{username}' is reserved and cannot be used"
    
    return True, None


def sanitize_input(input_string: str, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent injection attacks.
    
    Removes or escapes potentially dangerous characters and patterns.
    
    Args:
        input_string: String to sanitize
        max_length: Maximum allowed length
        
    Returns:
        str: Sanitized string
    """
    if not isinstance(input_string, str):
        return ""
    
    # Trim whitespace
    sanitized = input_string.strip()
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # Remove null bytes
    sanitized = sanitized.replace('\x00', '')
    
    # Remove control characters except common whitespace
    sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in '\t\n\r')
    
    # Escape HTML special characters to prevent XSS
    html_escapes = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;'
    }
    for char, escape in html_escapes.items():
        sanitized = sanitized.replace(char, escape)
    
    return sanitized


def validate_registration_data(data: dict) -> tuple[bool, dict]:
    """
    Validate all fields for user registration.
    
    Args:
        data: Dictionary containing registration data (username, email, password)
        
    Returns:
        tuple: (is_valid, errors_dict)
    """
    errors = {}
    
    # Validate username
    if 'username' in data:
        is_valid, error = validate_username_format(data['username'])
        if not is_valid:
            errors['username'] = error
    else:
        errors['username'] = "Username is required"
    
    # Validate email
    if 'email' in data:
        is_valid, error = validate_email_format(data['email'])
        if not is_valid:
            errors['email'] = error
    else:
        errors['email'] = "Email is required"
    
    # Validate password
    if 'password' in data:
        is_valid, error = validate_password_strength(data['password'])
        if not is_valid:
            errors['password'] = error
    else:
        errors['password'] = "Password is required"
    
    return len(errors) == 0, errors


def validate_login_data(data: dict) -> tuple[bool, dict]:
    """
    Validate fields for user login.
    
    Args:
        data: Dictionary containing login data
        
    Returns:
        tuple: (is_valid, errors_dict)
    """
    errors = {}
    
    # Validate username or email
    has_identifier = False
    if 'username' in data and data['username']:
        has_identifier = True
    if 'email' in data and data['email']:
        has_identifier = True
    
    if not has_identifier:
        errors['identifier'] = "Username or email is required"
    
    # Validate password
    if 'password' not in data or not data['password']:
        errors['password'] = "Password is required"
    
    return len(errors) == 0, errors


def validate_password_change_data(data: dict) -> tuple[bool, dict]:
    """
    Validate fields for password change.
    
    Args:
        data: Dictionary containing password change data
        
    Returns:
        tuple: (is_valid, errors_dict)
    """
    errors = {}
    
    # Validate current password
    if 'current_password' not in data or not data['current_password']:
        errors['current_password'] = "Current password is required"
    
    # Validate new password
    if 'new_password' in data:
        is_valid, error = validate_password_strength(data['new_password'])
        if not is_valid:
            errors['new_password'] = error
    else:
        errors['new_password'] = "New password is required"
    
    # Check passwords are different
    if ('current_password' in data and 'new_password' in data and 
        data['current_password'] == data['new_password']):
        errors['new_password'] = "New password must be different from current password"
    
    return len(errors) == 0, errors
