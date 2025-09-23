# backend/core/logging/__init__.py

"""
Core logging utilities for the application.

This module provides:
- Context management for correlation IDs
- Request/response logging middleware  
- Log sanitization utilities
- Structured logging helpers

Note: Import middlewares directly from their modules to avoid circular imports.
"""

from .context import (
    get_correlation_id,
    set_correlation_id,
    clear_correlation_id,
    get_logging_context,
    correlation_context,
)
from .sanitize import (
    mask_email,
    mask_header,
    scrub_payload,
    sanitize_dict,
    format_headers_for_logging,
    get_safe_error_details,
)
from .logger import (
    get_logger,
    log_with_context,
    log_execution,
    ContextualLogger,
)

__all__ = [
    # Context management
    'get_correlation_id',
    'set_correlation_id',
    'clear_correlation_id',
    'get_logging_context',
    'correlation_context',
    # Sanitization
    'mask_email',
    'mask_header',
    'scrub_payload',
    'sanitize_dict',
    'format_headers_for_logging',
    'get_safe_error_details',
    # Logger factory
    'get_logger',
    'log_with_context',
    'log_execution',
    'ContextualLogger',
]
