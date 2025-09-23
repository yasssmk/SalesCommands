# backend/core/logging/sanitize.py

"""
Sanitization utilities for safe logging.

Provides functions to mask sensitive data before logging to prevent
PII/secrets leakage in logs.
"""

import re
from typing import Any, Dict, List, Optional, Union
import json


# Maximum size for any logged value (2KB)
MAX_VALUE_SIZE = 2048

# Patterns for sensitive data detection
SENSITIVE_HEADERS = {
    'authorization',
    'cookie', 
    'set-cookie',
    'x-api-key',
    'x-auth-token',
    'x-csrf-token',
    'x-access-token',
    'x-refresh-token',
}

SENSITIVE_KEYS = {
    'password',
    'passwd',
    'pwd',
    'secret',
    'token',
    'api_key',
    'apikey',
    'auth',
    'authorization',
    'cookie',
    'session',
    'jwt',
    'bearer',
    'refresh_token',
    'access_token',
    'private_key',
    'client_secret',
}

# Email regex pattern
EMAIL_PATTERN = re.compile(r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})')


def mask_email(email: str) -> str:
    """
    Mask email address keeping first letter and domain.
    
    Args:
        email: Email address to mask
        
    Returns:
        str: Masked email (j***@domain.com) or original if not an email
        
    Examples:
        >>> mask_email('john.doe@example.com')
        'j***@example.com'
        >>> mask_email('admin@company.org')
        'a***@company.org'
        >>> mask_email('not_an_email')
        'not_an_email'
    """
    if not email or not isinstance(email, str):
        return email
    
    match = EMAIL_PATTERN.match(email.strip())
    if match:
        local, domain = match.groups()
        if local:
            masked = f"{local[0]}***@{domain}"
            return masked
    
    return email


def mask_header(header_name: str, header_value: str) -> str:
    """
    Mask sensitive header values.
    
    Args:
        header_name: Name of the header (case-insensitive)
        header_value: Value of the header
        
    Returns:
        str: Masked value if sensitive, original otherwise
        
    Examples:
        >>> mask_header('Authorization', 'Bearer abc123xyz')
        'Bearer [REDACTED]'
        >>> mask_header('Cookie', 'session=xyz123; user=john')
        '[REDACTED]'
        >>> mask_header('Content-Type', 'application/json')
        'application/json'
    """
    if not header_value:
        return header_value
    
    # Convert to string if not already
    header_value = str(header_value)
    header_name_lower = header_name.lower() if header_name else ''
    
    # Check if header is sensitive
    if header_name_lower in SENSITIVE_HEADERS:
        # Special handling for Authorization header - keep scheme
        if header_name_lower == 'authorization' and ' ' in header_value:
            scheme = header_value.split(' ', 1)[0]
            return f"{scheme} [REDACTED]"
        else:
            return '[REDACTED]'
    
    # Check for emails in header value
    if EMAIL_PATTERN.search(header_value):
        return EMAIL_PATTERN.sub(lambda m: mask_email(m.group(0)), header_value)
    
    # Truncate if too long
    if len(header_value) > MAX_VALUE_SIZE:
        return header_value[:MAX_VALUE_SIZE] + '[TRUNCATED]'
    
    return header_value


def scrub_payload(
    data: Union[Dict, List, str, Any],
    max_size: int = MAX_VALUE_SIZE,
    depth: int = 0,
    max_depth: int = 10
) -> Union[Dict, List, str, Any]:
    """
    Recursively scrub sensitive data from payloads.
    
    Args:
        data: Data to scrub (dict, list, or primitive)
        max_size: Maximum size for string values (default 2KB)
        depth: Current recursion depth (internal)
        max_depth: Maximum recursion depth to prevent infinite loops
        
    Returns:
        Scrubbed data with sensitive values masked and large values truncated
        
    Examples:
        >>> scrub_payload({'username': 'john', 'password': 'secret123'})
        {'username': 'john', 'password': '[REDACTED]'}
        >>> scrub_payload({'email': 'john@example.com', 'data': 'x' * 3000})
        {'email': 'j***@example.com', 'data': 'xxx...[TRUNCATED_2048]'}
    """
    # Prevent infinite recursion
    if depth > max_depth:
        return '[MAX_DEPTH_EXCEEDED]'
    
    # Handle None
    if data is None:
        return data
    
    # Handle dictionaries
    if isinstance(data, dict):
        scrubbed = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            
            # Check if key indicates sensitive data
            is_sensitive = any(
                sensitive in key_lower 
                for sensitive in SENSITIVE_KEYS
            )
            
            # Check for body/payload keys (completely redact)
            is_payload = key_lower in ('body', 'request_body', 'response_body', 
                                       'payload', 'data', 'request_data')
            
            if is_payload:
                scrubbed[key] = '[PAYLOAD_REDACTED]'
            elif is_sensitive:
                # Mask sensitive values
                if isinstance(value, str) and '@' in value:
                    scrubbed[key] = mask_email(value)
                else:
                    scrubbed[key] = '[REDACTED]'
            else:
                # Recursively scrub nested structures
                scrubbed[key] = scrub_payload(value, max_size, depth + 1, max_depth)
        
        return scrubbed
    
    # Handle lists
    elif isinstance(data, list):
        return [
            scrub_payload(item, max_size, depth + 1, max_depth) 
            for item in data
        ]
    
    # Handle strings
    elif isinstance(data, str):
        # Check for email patterns
        if EMAIL_PATTERN.search(data):
            data = EMAIL_PATTERN.sub(lambda m: mask_email(m.group(0)), data)
        
        # Truncate if too long
        if len(data) > max_size:
            return data[:max_size] + f'[TRUNCATED_{max_size}]'
        
        return data
    
    # Handle other types (numbers, booleans, etc.)
    else:
        # Convert to string for size check
        str_data = str(data)
        if len(str_data) > max_size:
            return str_data[:max_size] + f'[TRUNCATED_{max_size}]'
        return data


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to sanitize a dictionary for logging.
    
    This is the main entry point for sanitizing structured data before logging.
    
    Args:
        data: Dictionary to sanitize
        
    Returns:
        dict: Sanitized dictionary safe for logging
        
    Example:
        >>> context = {'user': 'john', 'password': 'secret', 'action': 'login'}
        >>> sanitize_dict(context)
        {'user': 'john', 'password': '[REDACTED]', 'action': 'login'}
    """
    if not isinstance(data, dict):
        return data
    
    return scrub_payload(data)


def format_headers_for_logging(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Format HTTP headers dict for safe logging.
    
    Args:
        headers: Dictionary of HTTP headers
        
    Returns:
        dict: Sanitized headers safe for logging
        
    Example:
        >>> headers = {'Authorization': 'Bearer token123', 'Content-Type': 'application/json'}
        >>> format_headers_for_logging(headers)
        {'Authorization': 'Bearer [REDACTED]', 'Content-Type': 'application/json'}
    """
    if not headers:
        return {}
    
    sanitized = {}
    for name, value in headers.items():
        sanitized[name] = mask_header(name, value)
    
    return sanitized


def get_safe_error_details(error: Exception, include_type: bool = True) -> Dict[str, Any]:
    """
    Extract safe details from an exception for logging.
    
    Args:
        error: The exception to extract details from
        include_type: Whether to include the exception type
        
    Returns:
        dict: Safe exception details for logging
    """
    details = {}
    
    if include_type:
        details['error_type'] = error.__class__.__name__
    
    # Get error message, but sanitize it
    error_msg = str(error)
    
    # Check for emails in error message
    if EMAIL_PATTERN.search(error_msg):
        error_msg = EMAIL_PATTERN.sub(lambda m: mask_email(m.group(0)), error_msg)
    
    # Truncate if too long
    if len(error_msg) > MAX_VALUE_SIZE:
        error_msg = error_msg[:MAX_VALUE_SIZE] + '[TRUNCATED]'
    
    details['error_message'] = error_msg
    
    # Add any safe attributes from the exception
    if hasattr(error, 'status_code'):
        details['status_code'] = getattr(error, 'status_code', None)
    
    if hasattr(error, 'error_code'):
        details['error_code'] = getattr(error, 'error_code', None)
    
    return details