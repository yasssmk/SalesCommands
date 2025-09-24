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
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.conf import settings

from .context import get_correlation_id
from .sanitize import format_headers_for_logging, sanitize_headers

try:
    from backend.permissions.compat import get_auth_ctx
except ImportError:
    try:
        from permissions.compat import get_auth_ctx
    except ImportError:
        # Fallback si permissions non disponible
        def get_auth_ctx(request):
            class DummyContext:
                client_id = None
                user_id = None
                origin = None
                jti = None
            return DummyContext()

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
    - Handles StreamingHttpResponse safely (P0-T1)
    
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
        
        # P1: Get header logging configuration from settings
        self.log_headers_in_prod = getattr(settings, 'LOG_HEADERS_IN_PROD', False)
        self.headers_allowlist = getattr(settings, 'LOG_HEADERS_ALLOWLIST', [])

        # ⚠️ Alerte DEBUG si on utilise le fallback DummyContext
        try:
            is_dummy = (
                getattr(get_auth_ctx, "__name__", "") == "get_auth_ctx" and
                getattr(get_auth_ctx, "__module__", "") == __name__  # le fallback est défini dans ce module
            )
        except Exception:
            is_dummy = False  # par prudence

        if settings.DEBUG and is_dummy:
            logger.warning(
                "request_logging: get_auth_ctx not importable; using DummyContext "
                "(client_id may be '-')"
            )
        
        # P1: Log header configuration on startup (DEBUG only)
        if settings.DEBUG:
            if self.log_headers_in_prod:
                logger.info(
                    f"request_logging: Header logging enabled in production mode "
                    f"with {len(self.headers_allowlist)} allowed headers"
                )
            else:
                logger.debug("request_logging: Headers will only be logged in DEBUG mode")
    
    def process_request(self, request: HttpRequest) -> None:
        """
        Process incoming request and start timing.
        
        Args:
            request: The incoming HTTP request
        """
        # Start timing with monotonic clock (P0-T2: renamed for clarity)
        request._logging_start_ts = time.perf_counter()
        
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
        
        # P1: Log headers based on configuration
        # Log headers in DEBUG mode OR when explicitly enabled in production
        should_log_headers = settings.DEBUG or self.log_headers_in_prod
        
        if should_log_headers:
            # Get headers dict from META
            headers = self._extract_headers(request.META)
            
            if settings.DEBUG:
                # In DEBUG mode: log all headers (sanitized)
                context['headers'] = format_headers_for_logging(headers)
            elif self.log_headers_in_prod:
                # In production with flag enabled: use allowlist
                context['headers'] = sanitize_headers(
                    headers, 
                    allowlist=self.headers_allowlist,
                    redact_sensitive=True
                )
        
        # Log with simple message (details in structured fields)
        logger.log(
            self.request_log_level,
            "request_started",  # Simple, fixed message
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
        
        # P0-T2: Calculate duration with robust fallback
        duration_ms = '-'
        try:
            if hasattr(request, '_logging_start_ts'):
                duration = time.perf_counter() - request._logging_start_ts
                duration_ms = f"{duration * 1000:.2f}"  # Convert to milliseconds
        except Exception:
            # Fallback in case of any error
            duration_ms = '-'
        
        # P0-T1: Safe response_size handling for streaming responses
        response_size = None
        try:
            # Check if it's a streaming response
            if isinstance(response, StreamingHttpResponse) or \
               hasattr(response, 'streaming_content') or \
               getattr(response, 'streaming', False):
                # Streaming response - size unknown
                response_size = None
            elif hasattr(response, 'content'):
                # Regular response with content
                response_size = len(response.content)
            else:
                # Fallback for responses without content
                response_size = 0
        except Exception:
            # Any error accessing content - default to None
            response_size = None
        
        # Build response context
        context = {
            'correlation_id': get_correlation_id(),
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'duration_ms': duration_ms,
            'remote_ip': getattr(request, '_client_ip', '-'),
            'response_size': response_size if response_size is not None else '-',
        }
        
        # CHANGEMENT PRINCIPAL : Utiliser get_auth_ctx() pour extraire le contexte unifié
        # C'est la même source que celle utilisée par les permissions
        auth_ctx = get_auth_ctx(request)
        
        # Peupler les champs depuis l'AuthContext
        context['user_id'] = str(auth_ctx.user_id) if auth_ctx.user_id else '-'
        context['client_id'] = str(auth_ctx.client_id) if auth_ctx.client_id else '-'
        
        # Ajouter origin et jti s'ils sont disponibles
        if auth_ctx.origin:
            context['origin'] = auth_ctx.origin
        else:
            context['origin'] = '-'
            
        if auth_ctx.jti:
            context['jti'] = auth_ctx.jti
        
        # P0-T2: Determine log level based on status code (confirmer mapping)
        if response.status_code >= 500:
            log_level = logging.ERROR
        elif response.status_code >= 400:
            log_level = logging.WARNING
        else:
            # 2xx/3xx: INFO en prod, DEBUG en dev
            log_level = self.request_log_level
        
        # Log with simple message
        logger.log(
            log_level,
            "request_completed",  # Simple, fixed message
            extra=context
        )
        
        return response

    
    def process_exception(self, request: HttpRequest, exception: Exception) -> None:
        """
        Process exception and log request failure.
        
        Args:
            request: The HTTP request
            exception: The exception that occurred
            
        Returns:
            None (let Django handle the exception)
        """
        if getattr(request, '_skip_logging', False):
            return None

        # P0-T2: Robust duration calculation with fallback
        duration_ms = '-'
        try:
            if hasattr(request, '_logging_start_ts'):
                duration = time.perf_counter() - request._logging_start_ts
                duration_ms = f"{duration * 1000:.2f}"
        except Exception:
            duration_ms = '-'

        context = {
            'correlation_id': get_correlation_id(),
            'method': getattr(request, 'method', '-'),
            'path': getattr(request, 'path', '-'),
            'duration_ms': duration_ms,
            'remote_ip': getattr(request, '_client_ip', '-'),
            'exception_type': exception.__class__.__name__,
            'exception_message': str(exception),
        }

        # >>> unifier la source avec les permissions
        auth_ctx = get_auth_ctx(request)
        context['user_id'] = str(auth_ctx.user_id) if getattr(auth_ctx, 'user_id', None) else '-'
        context['client_id'] = str(auth_ctx.client_id) if getattr(auth_ctx, 'client_id', None) else '-'
        context['origin'] = getattr(auth_ctx, 'origin', '-') or '-'
        if getattr(auth_ctx, 'jti', None):
            context['jti'] = auth_ctx.jti

        # P0-T2: Exception = ERROR level
        logger.error(
            "request_failed",
            extra=context,
            exc_info=True if settings.DEBUG else False
        )
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
            bool: True if valid IP format
        """
        if not ip:
            return False
        
        # Basic IPv4 validation
        if '.' in ip:
            parts = ip.split('.')
            if len(parts) == 4:
                try:
                    return all(0 <= int(p) <= 255 for p in parts)
                except ValueError:
                    return False
        
        # Basic IPv6 validation (simplified)
        if ':' in ip:
            # Just check it has colons and hex chars
            return all(c in '0123456789abcdefABCDEF:' for c in ip)
        
        return False
    
    def _extract_headers(self, meta: dict) -> dict:
        """
        Extract HTTP headers from request META.
        
        Django stores headers in META with HTTP_ prefix.
        
        Args:
            meta: Request META dict
            
        Returns:
            dict: Headers dict
        """
        headers = {}
        
        for key, value in meta.items():
            if key.startswith('HTTP_'):
                # Remove HTTP_ prefix and convert to header case
                header_name = key[5:].replace('_', '-').title()
                headers[header_name] = value
            elif key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
                # Special cases without HTTP_ prefix
                header_name = key.replace('_', '-').title()
                headers[header_name] = value
        
        return headers