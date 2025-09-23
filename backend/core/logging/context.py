# backend/core/logging/context.py

"""
Context management for correlation IDs across requests.

Uses contextvars to maintain correlation IDs in a thread-safe and async-safe manner.
This ensures each request has its own isolated correlation ID that follows
through all log messages during request processing.
"""

import uuid
from contextvars import ContextVar
from typing import Optional

# Context variable for storing correlation ID
# This is thread-safe and async-safe by design
_correlation_id: ContextVar[Optional[str]] = ContextVar(
    'correlation_id',
    default=None
)


def get_correlation_id() -> str:
    """
    Get the current correlation ID from context.
    
    Returns:
        str: Current correlation ID or '-' if not set
    
    Usage:
        correlation_id = get_correlation_id()
        logger.info("Processing", extra={'correlation_id': correlation_id})
    """
    correlation_id = _correlation_id.get()
    return correlation_id if correlation_id else '-'


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set the correlation ID in the current context.
    
    Args:
        correlation_id: The correlation ID to set. If None, generates a new UUID.
    
    Returns:
        str: The correlation ID that was set
    
    Usage:
        # Set a specific ID (e.g., from X-Request-ID header)
        set_correlation_id(request.headers.get('X-Request-ID'))
        
        # Generate a new ID
        new_id = set_correlation_id()
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    
    _correlation_id.set(correlation_id)
    return correlation_id


def clear_correlation_id() -> None:
    """
    Clear the correlation ID from context.
    
    This should typically be called at the end of request processing
    to ensure clean context for the next request (though contextvars
    handles this automatically for async contexts).
    
    Usage:
        clear_correlation_id()
    """
    _correlation_id.set(None)


def get_logging_context() -> dict:
    """
    Get a dictionary with all logging context variables.
    
    This is a convenience function that returns all context variables
    in a format ready for logging. Can be extended to include additional
    context like user_id, client_id, etc.
    
    Returns:
        dict: Dictionary with logging context variables
    
    Usage:
        logger.info("User action", extra=get_logging_context())
    """
    return {
        'correlation_id': get_correlation_id(),
    }


# Context manager for temporary correlation ID
class correlation_context:
    """
    Context manager for temporarily setting a correlation ID.
    
    Useful for background tasks or when you need to temporarily
    override the correlation ID.
    
    Usage:
        with correlation_context('special-task-123'):
            # All logs within this block will use 'special-task-123'
            process_background_task()
    """
    
    def __init__(self, correlation_id: Optional[str] = None):
        """
        Initialize the context manager.
        
        Args:
            correlation_id: Correlation ID to use. If None, generates a new one.
        """
        self.new_id = correlation_id or str(uuid.uuid4())
        self.token = None
    
    def __enter__(self):
        """Set the correlation ID and return it."""
        self.token = _correlation_id.set(self.new_id)
        return self.new_id
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore the previous correlation ID."""
        if self.token:
            _correlation_id.reset(self.token)
        return False