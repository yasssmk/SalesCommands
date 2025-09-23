# backend/core/logging/middlewares.py

"""
Logging middlewares for request tracking and correlation.

RequestIdMiddleware must be placed FIRST in MIDDLEWARE settings
to ensure correlation ID is available for all other middlewares.
"""

import uuid
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse

from .context import set_correlation_id, get_correlation_id, clear_correlation_id

logger = logging.getLogger(__name__)


class RequestIdMiddleware(MiddlewareMixin):
    """
    Middleware that assigns a unique correlation ID to each request.
    
    This middleware:
    1. Checks for existing X-Request-ID header from client/proxy
    2. Generates a new UUID if none exists
    3. Stores the ID in contextvars for the request lifecycle
    4. Adds X-Request-ID to the response headers
    
    MUST be placed FIRST in MIDDLEWARE list to ensure correlation ID
    is available for all subsequent middleware and view processing.
    
    Configuration in settings.py:
        MIDDLEWARE = [
            'core.logging.middlewares.RequestIdMiddleware',  # <-- FIRST!
            'corsheaders.middleware.CorsMiddleware',
            'django.middleware.security.SecurityMiddleware',
            ...
        ]
    """
    
    # Header names
    REQUEST_ID_HEADER = 'HTTP_X_REQUEST_ID'  # Django's internal format
    RESPONSE_HEADER = 'X-Request-ID'
    
    def process_request(self, request: HttpRequest) -> None:
        """
        Process incoming request and set correlation ID.
        
        Args:
            request: The incoming HTTP request
        """
        # Try to get correlation ID from incoming headers
        correlation_id = None
        
        # Check for X-Request-ID header (Django converts to HTTP_X_REQUEST_ID)
        if self.REQUEST_ID_HEADER in request.META:
            incoming_id = request.META[self.REQUEST_ID_HEADER]
            # Validate the incoming ID (basic validation)
            if incoming_id and self._is_valid_correlation_id(incoming_id):
                correlation_id = incoming_id
                logger.debug(
                    "Using incoming X-Request-ID",
                    extra={
                        'correlation_id': correlation_id,
                        'source': 'header'
                    }
                )
        
        # Generate new ID if none provided or invalid
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
            logger.debug(
                "Generated new correlation ID",
                extra={
                    'correlation_id': correlation_id,
                    'source': 'generated'
                }
            )
        
        # Store in contextvars for the request lifecycle
        set_correlation_id(correlation_id)
        
        # Also store on request object for easy access
        request.correlation_id = correlation_id
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Add correlation ID to response headers.
        
        Args:
            request: The HTTP request
            response: The HTTP response
        
        Returns:
            HttpResponse: The response with X-Request-ID header added
        """
        # Get the correlation ID from context
        correlation_id = get_correlation_id()
        
        # Add to response headers if we have one
        if correlation_id and correlation_id != '-':
            response[self.RESPONSE_HEADER] = correlation_id
        
        # Clear context (cleanup, though contextvars handles this automatically)
        clear_correlation_id()
        
        return response
    
    def process_exception(self, request: HttpRequest, exception: Exception) -> None:
        """
        Ensure correlation ID is available when logging exceptions.
        
        Args:
            request: The HTTP request
            exception: The exception that occurred
        """
        # The correlation ID is already in context from process_request
        # This method is here for completeness and future exception handling
        correlation_id = get_correlation_id()
        
        # Log that an exception occurred with correlation ID
        logger.debug(
            f"Exception occurred during request processing: {exception.__class__.__name__}",
            extra={
                'correlation_id': correlation_id,
                'exception_type': exception.__class__.__name__
            }
        )
        
        # Let Django's exception handling continue
        return None
    
    def _is_valid_correlation_id(self, correlation_id: str) -> bool:
        """
        Validate a correlation ID.
        
        Basic validation to prevent header injection and ensure reasonable IDs.
        
        Args:
            correlation_id: The correlation ID to validate
        
        Returns:
            bool: True if valid, False otherwise
        """
        if not correlation_id:
            return False
        
        # Limit length (UUIDs are 36 chars, but allow up to 128 for custom IDs)
        if len(correlation_id) > 128:
            return False
        
        # Basic character validation (alphanumeric, hyphens, underscores)
        # This prevents header injection attacks
        import re
        if not re.match(r'^[a-zA-Z0-9\-_]+$', correlation_id):
            return False
        
        return True