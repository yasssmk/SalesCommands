"""
ETag middleware for JSON responses.

Generates MD5 hash of JSON response body and handles If-None-Match headers
to return 304 Not Modified when content hasn't changed.

This saves bandwidth and improves client-side performance by avoiding
re-transmitting identical JSON payloads.

Note: This middleware applies globally to all JSON 200 responses.
Test thoroughly before enabling in production.
"""

import hashlib
import json
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse, StreamingHttpResponse, JsonResponse
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class ETagMiddleware(MiddlewareMixin):
    """
    Middleware that adds ETag headers to JSON responses and handles If-None-Match.
    
    How it works:
    1. Calculates MD5 hash of JSON response body
    2. Sets ETag header: ETag: "abc123def456"
    3. On next request, client sends: If-None-Match: "abc123def456"
    4. If hash matches → returns 304 Not Modified (no body)
    5. If hash differs → returns 200 OK with new data and new ETag
    
    Placement in MIDDLEWARE:
    - Should be placed LATE in the middleware stack (after authentication, logging)
    - Before any compression middleware
    
    Example:
        MIDDLEWARE = [
            ...
            'core.logging.request_logging.RequestLoggingMiddleware',
            'core.http.etag.ETagMiddleware',  # <-- Here
            ...
        ]
    """
    
    # Paths to exclude from ETag processing
    EXCLUDED_PATHS = {
        '/health',
        '/ready',
        '/metrics',
        '/admin/',
        '/static/',
        '/media/',
    }
    
    def should_process(self, request, response):
        """
        Determine if this response should have ETag processing.
        
        Args:
            request: Django request object
            response: Django response object
            
        Returns:
            bool: True if ETag should be added, False otherwise
        """
        # Skip if not a successful response
        if response.status_code != 200:
            return False
        
        # Skip excluded paths
        path = request.path
        for excluded in self.EXCLUDED_PATHS:
            if path.startswith(excluded):
                return False
        
        # Skip streaming responses (can't hash the body)
        if isinstance(response, StreamingHttpResponse):
            return False
        
        # Only process JSON responses
        content_type = response.get('Content-Type', '')
        if 'application/json' not in content_type:
            return False
        
        # Skip if ETag already set by view
        if response.has_header('ETag'):
            return False
        
        return True
    
    def process_response(self, request, response):
        """
        Add ETag header to response and handle If-None-Match.
        
        Args:
            request: Django request object
            response: Django response object
            
        Returns:
            HttpResponse: Original or 304 Not Modified response
        """
        try:
            # Check if we should process this response
            if not self.should_process(request, response):
                return response
            
            # Get response content
            try:
                content = response.content
            except Exception as e:
                logger.warning(f"Could not access response content for ETag: {e}")
                return response
            
            # Calculate MD5 hash
            etag = f'"{hashlib.md5(content).hexdigest()}"'
            
            # Check If-None-Match header from client
            client_etag = request.META.get('HTTP_IF_NONE_MATCH')
            
            if client_etag and client_etag == etag:
                # Content hasn't changed - return 304
                response_304 = HttpResponse(status=304)
                response_304['ETag'] = etag
                
                # Copy cache-control headers if present
                if response.has_header('Cache-Control'):
                    response_304['Cache-Control'] = response['Cache-Control']
                
                if settings.DEBUG:
                    logger.debug(f"ETag match - returning 304: {etag} for {request.path}")
                
                return response_304
            
            # Content is new or different - add ETag and return 200
            response['ETag'] = etag
            
            if settings.DEBUG:
                logger.debug(f"ETag added: {etag} for {request.path}")
            
            return response
            
        except Exception as e:
            # Graceful degradation - return original response on any error
            logger.warning(f"ETag middleware error: {e}", exc_info=settings.DEBUG)
            return response