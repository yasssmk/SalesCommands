# backend/core/logging/request_logging.py

"""
Request/Response logging middleware for HTTP traffic monitoring.

Logs metadata only (no bodies) with timing and client information.
Uses monotonic clock for accurate duration measurement.
"""

import time
import logging
from typing import Optional, List
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse
from django.conf import settings

from .context import get_correlation_id
from .sanitize import format_headers_for_logging

# Use standard logger to avoid circular import
logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware that logs HTTP request/response metadata.
    
    Features:
    - Uses time.perf_counter() for accurate duration measurement
    - Extracts real client IP from X-Forwarded-For header
    - Logs metadata only (no request/response bodies)
    - Excludes configured paths (health checks, etc.)
    - Respects DEBUG setting for verbosity
    
    This middleware should be placed AFTER RequestIdMiddleware
    to ensure correlation_id is available:
    
    MIDDLEWARE = [
        'core.logging.middlewares.RequestIdMiddleware',
        'core.logging.request_logging.RequestLoggingMiddleware',  # <-- Here
        ...
    ]
    """
    
    # Paths to exclude from logging (health checks, metrics, etc.)
    EXCLUDED_PATHS = {
        '/health',
        '/ready',
        '/metrics',
        '/healthz',
        '/readyz',
        '/_health',
        '/_ready',
    }
    
    # Additional paths to exclude in production
    EXCLUDED_PATHS_PROD = {
        '/static',
        '/media',
        '/favicon.ico',
        '/robots.txt',
    }
    
    # Headers that might contain the real IP
    IP_HEADERS = [
        'HTTP_X_FORWARDED_FOR',
        'HTTP_X_REAL_IP',
        'HTTP_CF_CONNECTING_IP',  # Cloudflare
        'HTTP_X_CLIENT_IP',
        'REMOTE_ADDR',
    ]
    
    def __init__(self, get_response):
        """Initialize the middleware."""
        super().__init__(get_response)
        
        # Determine excluded paths based on DEBUG setting
        self.excluded_paths = self.EXCLUDED_PATHS.copy()
        if not settings.DEBUG:
            self.excluded_paths.update(self.EXCLUDED_PATHS_PROD)
        
        # Get custom excluded paths from settings if defined
        custom_excluded = getattr(settings, 'LOGGING_EXCLUDED_PATHS', set())
        if custom_excluded:
            self.excluded_paths.update(custom_excluded)
        
        # Log level for requests (DEBUG in development, INFO in production)
        self.request_log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    
    def process_request(self, request: HttpRequest) -> None:
        """
        Process incoming request and start timing.
        
        Args:
            request: The incoming HTTP request
        """
        # Start timing with monotonic clock
        request._start_time = time.perf_counter()
        
        # Skip logging for excluded paths
        if self._should_skip_logging(request.path):
            request._skip_logging = True
            return
        
        # Get real client IP
        client_ip = self._get_client_ip(request)
        
        # Store for response logging
        request._client_ip = client_ip
        
        # Build request context
        context = {
            'correlation_id': get_correlation_id(),
            'method': request.method,
            'path': request.path,
            'remote_ip': client_ip,
            'user_agent': request.META.get('HTTP_USER_AGENT', '-'),
            'content_type': request.content_type or '-',
            'query_params': dict(request.GET) if request.GET else {},
        }
        
        # Add user info if available
        if hasattr(request, 'user') and request.user.is_authenticated:
            context['user_id'] = str(request.user.id)
            context['username'] = request.user.username if hasattr(request.user, 'username') else '-'
        
        # Add client_id if available
        if hasattr(request, 'client_id'):
            context['client_id'] = str(request.client_id)
        
        # Log sanitized headers in DEBUG mode
        if settings.DEBUG:
            # Get headers dict from META
            headers = self._extract_headers(request.META)
            context['headers'] = format_headers_for_logging(headers)
        
        # Log the request
        logger.log(
            self.request_log_level,
            f"Request started: {request.method} {request.path}",
            extra=context
        )
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Process response and log request completion.
        
        Args:
            request: The HTTP request
            response: The HTTP response
            
        Returns:
            HttpResponse: The unmodified response
        """
        # Skip if marked for skipping
        if getattr(request, '_skip_logging', False):
            return response
        
        # Calculate duration if we have start time
        duration_ms = '-'
        if hasattr(request, '_start_time'):
            duration = time.perf_counter() - request._start_time
            duration_ms = f"{duration * 1000:.2f}"  # Convert to milliseconds
        
        # Build response context
        context = {
            'correlation_id': get_correlation_id(),
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'duration_ms': duration_ms,
            'remote_ip': getattr(request, '_client_ip', '-'),
            'response_size': len(response.content) if hasattr(response, 'content') else 0,
        }
        
        # Add user info if available
        if hasattr(request, 'user') and request.user.is_authenticated:
            context['user_id'] = str(request.user.id)
        
        # Add client_id if available  
        if hasattr(request, 'client_id'):
            context['client_id'] = str(request.client_id)
        
        # Determine log level based on status code
        if response.status_code >= 500:
            log_level = logging.ERROR
        elif response.status_code >= 400:
            log_level = logging.WARNING
        else:
            log_level = self.request_log_level
        
        # Log the response
        logger.log(
            log_level,
            f"Request completed: {request.method} {request.path} -> {response.status_code} ({duration_ms}ms)",
            extra=context
        )
        
        return response
    
    def process_exception(self, request: HttpRequest, exception: Exception) -> None:
        """
        Log exceptions that occur during request processing.
        
        Args:
            request: The HTTP request
            exception: The exception that occurred
        """
        # Skip if marked for skipping
        if getattr(request, '_skip_logging', False):
            return None
        
        # Calculate duration if we have start time
        duration_ms = '-'
        if hasattr(request, '_start_time'):
            duration = time.perf_counter() - request._start_time
            duration_ms = f"{duration * 1000:.2f}"
        
        # Build exception context
        context = {
            'correlation_id': get_correlation_id(),
            'method': request.method,
            'path': request.path,
            'duration_ms': duration_ms,
            'remote_ip': getattr(request, '_client_ip', '-'),
            'exception_type': exception.__class__.__name__,
            'exception_message': str(exception),
        }
        
        # Add user info if available
        if hasattr(request, 'user') and request.user.is_authenticated:
            context['user_id'] = str(request.user.id)
        
        # Add client_id if available
        if hasattr(request, 'client_id'):
            context['client_id'] = str(request.client_id)
        
        # Log the exception
        logger.error(
            f"Request failed: {request.method} {request.path} -> {exception.__class__.__name__}",
            extra=context,
            exc_info=True if settings.DEBUG else False  # Include traceback in DEBUG
        )
        
        # Let Django continue with exception handling
        return None
    
    def _should_skip_logging(self, path: str) -> bool:
        """
        Check if a path should be skipped from logging.
        
        Args:
            path: The request path
            
        Returns:
            bool: True if should skip, False otherwise
        """
        # Exact match
        if path in self.excluded_paths:
            return True
        
        # Prefix match for paths like /static/*
        for excluded in self.excluded_paths:
            if excluded.endswith('/') and path.startswith(excluded):
                return True
        
        return False
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Extract the real client IP from request.
        
        Checks various headers that proxies/load balancers use
        to forward the original client IP.
        
        Args:
            request: The HTTP request
            
        Returns:
            str: The client IP address or '-' if not found
        """
        for header in self.IP_HEADERS:
            ip_value = request.META.get(header, '').strip()
            
            if ip_value:
                # X-Forwarded-For can contain multiple IPs
                # Format: "client, proxy1, proxy2"
                if header == 'HTTP_X_FORWARDED_FOR':
                    # Take the first IP (original client)
                    ip_parts = ip_value.split(',')
                    if ip_parts:
                        client_ip = ip_parts[0].strip()
                        if self._is_valid_ip(client_ip):
                            return client_ip
                else:
                    # Single IP value
                    if self._is_valid_ip(ip_value):
                        return ip_value
        
        return '-'
    
    def _is_valid_ip(self, ip: str) -> bool:
        """
        Basic validation for IP address format.
        
        Args:
            ip: IP address string
            
        Returns:
            bool: True if appears to be valid IP
        """
        if not ip or ip == '-':
            return False
        
        # Very basic check - just ensure it's not empty and looks like an IP
        # For MVP, we don't need strict validation
        parts = ip.split('.')
        if len(parts) == 4:  # IPv4
            return all(part.isdigit() for part in parts)
        elif ':' in ip:  # IPv6
            return True
        
        return False
    
    def _extract_headers(self, meta: dict) -> dict:
        """
        Extract HTTP headers from Django's META dict.
        
        Args:
            meta: Django's request.META dictionary
            
        Returns:
            dict: HTTP headers
        """
        headers = {}
        
        for key, value in meta.items():
            # HTTP headers in META start with HTTP_
            if key.startswith('HTTP_'):
                # Convert HTTP_HEADER_NAME to Header-Name
                header_name = key[5:].replace('_', '-').title()
                headers[header_name] = value
            # Also include content type and length
            elif key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
                header_name = key.replace('_', '-').title()
                headers[header_name] = value
        
        return headers


# Convenience function to check if request logging is enabled
def is_request_logging_enabled() -> bool:
    """
    Check if request logging middleware is enabled.
    
    Returns:
        bool: True if RequestLoggingMiddleware is in MIDDLEWARE
    """
    middleware = getattr(settings, 'MIDDLEWARE', [])
    return any(
        'RequestLoggingMiddleware' in m or 
        'request_logging.RequestLoggingMiddleware' in m
        for m in middleware
    )