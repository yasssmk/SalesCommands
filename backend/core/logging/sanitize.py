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
    'proxy-authorization',  # P1: Added
    'www-authenticate',     # P1: Added
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


def sanitize_headers(
    headers: Dict[str, str], 
    allowlist: Optional[List[str]] = None,
    redact_sensitive: bool = True
) -> Dict[str, str]:
    """
    P1: Sanitize HTTP headers for safe logging with optional allowlist filtering.
    
    This function:
    1. Filters headers by allowlist if provided
    2. Redacts sensitive headers even if in allowlist
    3. Normalizes header names to lowercase
    4. Truncates long values
    5. Masks emails in values
    
    Args:
        headers: Dictionary of HTTP headers
        allowlist: Optional list of allowed header names (case-insensitive)
        redact_sensitive: Whether to redact sensitive headers (default: True)
        
    Returns:
        dict: Sanitized headers safe for logging
        
    Examples:
        >>> headers = {
        ...     'Authorization': 'Bearer token123',
        ...     'User-Agent': 'Mozilla/5.0',
        ...     'Content-Type': 'application/json'
        ... }
        >>> allowlist = ['user-agent', 'content-type']
        >>> sanitize_headers(headers, allowlist)
        {'user-agent': 'Mozilla/5.0', 'content-type': 'application/json'}
        
        >>> # Even if Authorization is in allowlist, it gets redacted
        >>> allowlist = ['authorization', 'user-agent']
        >>> sanitize_headers(headers, allowlist)
        {'authorization': 'Bearer [REDACTED]', 'user-agent': 'Mozilla/5.0'}
    """
    if not headers:
        return {}
    
    sanitized = {}
    
    # Convert allowlist to lowercase set for O(1) lookup
    if allowlist is not None:
        allowed_set = {name.lower() for name in allowlist}
    else:
        allowed_set = None
    
    for header_name, header_value in headers.items():
        # Normalize header name to lowercase
        normalized_name = header_name.lower()
        
        # Step 1: Check allowlist if provided
        if allowed_set is not None and normalized_name not in allowed_set:
            continue  # Skip headers not in allowlist
        
        # Convert value to string for processing
        str_value = str(header_value) if header_value is not None else ''
        
        # Step 2: Always redact sensitive headers if redact_sensitive is True
        if redact_sensitive and normalized_name in SENSITIVE_HEADERS:
            # Special handling for Authorization - preserve scheme
            if normalized_name == 'authorization' and ' ' in str_value:
                scheme = str_value.split(' ', 1)[0]
                sanitized[normalized_name] = f"{scheme} [REDACTED]"
            else:
                sanitized[normalized_name] = '[REDACTED]'
            continue
        
        # Step 3: Check for and mask emails
        if EMAIL_PATTERN.search(str_value):
            str_value = EMAIL_PATTERN.sub(lambda m: mask_email(m.group(0)), str_value)
        
        # Step 4: Truncate if too long
        if len(str_value) > MAX_VALUE_SIZE:
            str_value = str_value[:MAX_VALUE_SIZE] + '…[TRUNCATED]'
        
        # Add sanitized header
        sanitized[normalized_name] = str_value
    
    return sanitized


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
        max_size: Maximum size for string values
        depth: Current recursion depth
        max_depth: Maximum recursion depth
        
    Returns:
        Scrubbed data safe for logging
    """
    # Prevent infinite recursion
    if depth > max_depth:
        return '[MAX_DEPTH_EXCEEDED]'
    
    if isinstance(data, dict):
        scrubbed = {}
        for key, value in data.items():
            key_lower = key.lower() if isinstance(key, str) else str(key)
            
            # Check if key contains sensitive patterns
            is_sensitive = any(
                pattern in key_lower 
                for pattern in SENSITIVE_KEYS
            )
            
            if is_sensitive:
                scrubbed[key] = '[REDACTED]'
            else:
                # Recursively scrub nested structures
                scrubbed[key] = scrub_payload(
                    value, 
                    max_size, 
                    depth + 1, 
                    max_depth
                )
        
        return scrubbed
    
    elif isinstance(data, list):
        # Scrub each item in list
        return [
            scrub_payload(item, max_size, depth + 1, max_depth)
            for item in data
        ]
    
    elif isinstance(data, str):
        # Check for emails
        if EMAIL_PATTERN.search(data):
            data = EMAIL_PATTERN.sub(lambda m: mask_email(m.group(0)), data)
        
        # Truncate if too long
        if len(data) > max_size:
            return data[:max_size] + '[TRUNCATED]'
        
        return data
    
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
    
    NOTE: This function is being updated in P1 to use sanitize_headers()
    for consistency. It maintains backward compatibility.
    
    Args:
        headers: Dictionary of HTTP headers
        
    Returns:
        dict: Sanitized headers safe for logging
        
    Example:
        >>> headers = {'Authorization': 'Bearer token123', 'Content-Type': 'application/json'}
        >>> format_headers_for_logging(headers)
        {'authorization': 'Bearer [REDACTED]', 'content-type': 'application/json'}
    """
    # P1: Now delegates to sanitize_headers for consistency
    # No allowlist = include all headers, but still sanitize sensitive ones
    return sanitize_headers(headers, allowlist=None, redact_sensitive=True)


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