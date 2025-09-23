# backend/core/logging/logger.py

"""
Enhanced logger factory with automatic context enrichment.

Provides loggers that automatically include correlation_id, user_id, 
and client_id in all log messages.
"""

import logging
from typing import Any, Dict, Optional
from functools import wraps

from .context import get_correlation_id


def get_request_context() -> Dict[str, Any]:
    """
    Get the current request context for logging.
    
    Attempts to retrieve user_id and client_id from the current request
    via Django's thread-local storage.
    
    Returns:
        dict: Context with user_id, client_id, and correlation_id
    """
    context = {
        'correlation_id': get_correlation_id(),
        'user_id': '-',
        'client_id': '-',
    }
    
    try:
        # Try to get request from Django's thread-local storage
        from django.utils.deprecation import MiddlewareMixin
        from django.core.handlers.wsgi import WSGIRequest
        import threading
        
        # Django stores request in thread-local during request processing
        # This is a bit hacky but works for most cases
        # Better approach would be to use contextvars for request too
        
        # Try multiple methods to get current request
        request = None
        
        # Method 1: Try from current thread's stored request (if using custom middleware)
        if hasattr(threading.current_thread(), 'request'):
            request = threading.current_thread().request
        
        # Method 2: Try from context vars (if we store it there)
        if not request:
            try:
                from contextvars import ContextVar
                _request_var: ContextVar = ContextVar('request', default=None)
                request = _request_var.get()
            except:
                pass
        
        if request:
            # Extract user_id
            if hasattr(request, 'user') and request.user and hasattr(request.user, 'id'):
                if request.user.is_authenticated:
                    context['user_id'] = str(request.user.id)
            
            # Extract client_id (from JWT or session)
            if hasattr(request, 'client_id'):
                context['client_id'] = str(request.client_id)
            elif hasattr(request, 'session') and 'client_id' in request.session:
                context['client_id'] = str(request.session['client_id'])
            
            # Also check JWT context if available
            if hasattr(request, 'jwt_payload'):
                if 'client_id' in request.jwt_payload:
                    context['client_id'] = str(request.jwt_payload['client_id'])
                if 'user_id' in request.jwt_payload and context['user_id'] == '-':
                    context['user_id'] = str(request.jwt_payload['user_id'])
    
    except Exception:
        # Silently fail - better to log without context than to crash
        pass
    
    return context

def ctx_from_request(request) -> Dict:
    """
    Construit un contexte de log cohérent depuis la request.
    Remplit method/path/ip/user_id/client_id/correlation_id/stubs status/duration.
    """
    context = {
        'method': getattr(request, 'method', '-'),
        'path': getattr(request, 'path', '-'),
    }

    # user_id
    user = getattr(request, 'user', None)
    if user and getattr(user, 'is_authenticated', False):
        context['user_id'] = str(getattr(user, 'id', '-'))
    else:
        context['user_id'] = '-'

    # client_id: plusieurs sources
    client_id = getattr(request, 'client_id', None)
    if not client_id:
        # 1) DRF/JWT: request.auth peut être un dict (payload) ou un objet avec .payload
        auth = getattr(request, 'auth', None)
        if isinstance(auth, dict):
            client_id = auth.get('client_account') or auth.get('client_id')
        elif hasattr(auth, 'payload') and isinstance(auth.payload, dict):
            client_id = auth.payload.get('client_account') or auth.payload.get('client_id')

        # 2) payload posé par l’auth (si tu la mets, voir Étape 2)
        if not client_id and hasattr(request, 'jwt_payload'):
            payload = getattr(request, 'jwt_payload') or {}
            if isinstance(payload, dict):
                client_id = payload.get('client_account') or payload.get('client_id')

        # 3) session éventuelle
        if not client_id and hasattr(request, 'session'):
            client_id = request.session.get('client_id')

    context['client_id'] = str(client_id) if client_id else '-'

    # correlation_id (request -> META -> session -> contextvar)
    correlation_id = '-'
    if hasattr(request, 'correlation_id'):
        correlation_id = request.correlation_id
    elif hasattr(request, 'META') and 'CORRELATION_ID' in request.META:
        correlation_id = request.META['CORRELATION_ID']
    else:
        correlation_id = get_correlation_id()
    context['correlation_id'] = correlation_id

    # IP
    context['remote_ip'] = getattr(request, '_client_ip', request.META.get('REMOTE_ADDR', '-'))

    # Champs standardisés pour tes handlers
    context['status_code'] = '-'
    context['duration_ms'] = '-'

    return context



def ctx_from_user(user) -> Dict:
    """
    Extract logging context from a Django user object.
    
    Useful when you have a user but no request object.
    
    Args:
        user: Django User object
        
    Returns:
        dict: Context dictionary with user_id
        
    Usage:
        logger.info("User action", extra=ctx_from_user(user))
    """
    context = {
        'correlation_id': get_correlation_id(),
    }
    
    if user and hasattr(user, 'id'):
        context['user_id'] = str(user.id)
    else:
        context['user_id'] = '-'
    
    return context


class ContextualLogger:
    """
    Logger wrapper that automatically adds context to all log messages.
    
    This wrapper intercepts all logging calls and enriches them with
    correlation_id, user_id, and client_id from the current context.
    """
    
    def __init__(self, logger: logging.Logger):
        """
        Initialize the contextual logger.
        
        Args:
            logger: The underlying Python logger
        """
        self._logger = logger
        
    def _add_context(self, extra: Optional[Dict] = None) -> Dict:
        """
        Add context to the extra dict for logging.
        
        Args:
            extra: Existing extra dict (if any)
            
        Returns:
            dict: Merged extra dict with context
        """
        # Get current context
        context = get_request_context()
        
        # Merge with provided extra, preferring provided values
        if extra:
            merged = context.copy()
            merged.update(extra)
            return merged
        
        return context
    
    def debug(self, msg: str, *args, extra: Optional[Dict] = None, **kwargs):
        extra = self._add_context(extra)
        kwargs.setdefault("stacklevel", 2)
        self._logger.debug(msg, *args, extra=extra, **kwargs)

    def info(self, msg: str, *args, extra: Optional[Dict] = None, **kwargs):
        extra = self._add_context(extra)
        kwargs.setdefault("stacklevel", 2)
        self._logger.info(msg, *args, extra=extra, **kwargs)

    def warning(self, msg: str, *args, extra: Optional[Dict] = None, **kwargs):
        extra = self._add_context(extra)
        kwargs.setdefault("stacklevel", 2)
        self._logger.warning(msg, *args, extra=extra, **kwargs)

    def error(self, msg: str, *args, extra: Optional[Dict] = None, **kwargs):
        extra = self._add_context(extra)
        kwargs.setdefault("stacklevel", 2)
        self._logger.error(msg, *args, extra=extra, **kwargs)

    def critical(self, msg: str, *args, extra: Optional[Dict] = None, **kwargs):
        extra = self._add_context(extra)
        kwargs.setdefault("stacklevel", 2)
        self._logger.critical(msg, *args, extra=extra, **kwargs)

    def exception(self, msg: str, *args, extra: Optional[Dict] = None, **kwargs):
        extra = self._add_context(extra)
        kwargs.setdefault("stacklevel", 2)
        self._logger.exception(msg, *args, extra=extra, **kwargs)

    def log(self, level: int, msg: str, *args, extra: Optional[Dict] = None, **kwargs):
        extra = self._add_context(extra)
        kwargs.setdefault("stacklevel", 2)
        self._logger.log(level, msg, *args, extra=extra, **kwargs)
    
    # Proxy other attributes to the underlying logger
    def __getattr__(self, name):
        """Proxy any other attributes to the underlying logger."""
        return getattr(self._logger, name)
    
    # Properties to match standard logger interface
    @property
    def name(self):
        return self._logger.name
    
    @property
    def level(self):
        return self._logger.level
    
    @level.setter
    def level(self, value):
        self._logger.level = value
    
    @property
    def parent(self):
        return self._logger.parent
    
    @property
    def handlers(self):
        return self._logger.handlers
    
    @property
    def disabled(self):
        return self._logger.disabled
    
    @disabled.setter  
    def disabled(self, value):
        self._logger.disabled = value


# Cache for contextual loggers
_logger_cache: Dict[str, ContextualLogger] = {}


def get_logger(name: str = None) -> ContextualLogger:
    """
    Get a logger that automatically includes context in all messages.
    
    This is the main factory function that should be used throughout
    the application instead of logging.getLogger().
    
    Args:
        name: Logger name (typically __name__). If None, uses root logger.
        
    Returns:
        ContextualLogger: A logger that adds context automatically
        
    Usage:
        from core.logging import get_logger
        
        logger = get_logger(__name__)
        logger.info("User logged in")  # Will include correlation_id, user_id, client_id
    """
    if name is None:
        name = 'root'
    
    # Return cached logger if exists
    if name in _logger_cache:
        return _logger_cache[name]
    
    # Create new contextual logger
    base_logger = logging.getLogger(name)
    contextual = ContextualLogger(base_logger)
    
    # Cache it
    _logger_cache[name] = contextual
    
    return contextual


def log_with_context(
    logger_name: str,
    level: int,
    message: str,
    extra_context: Optional[Dict] = None
) -> None:
    """
    Convenience function to log a message with context.
    
    Args:
        logger_name: Name of the logger to use
        level: Log level (e.g., logging.INFO)
        message: Log message
        extra_context: Additional context to include
        
    Example:
        log_with_context(__name__, logging.INFO, "User action", {'action': 'login'})
    """
    logger = get_logger(logger_name)
    logger.log(level, message, extra=extra_context)


# Decorator for adding logging to functions
def log_execution(
    logger_name: Optional[str] = None,
    level: int = logging.DEBUG,
    log_args: bool = False,
    log_result: bool = False
):
    """
    Decorator to automatically log function execution.
    
    Args:
        logger_name: Logger name (uses function's module if not provided)
        level: Log level for the messages
        log_args: Whether to log function arguments
        log_result: Whether to log function result
        
    Usage:
        @log_execution(log_args=True, log_result=True)
        def process_user(user_id):
            return {'status': 'processed'}
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get logger
            nonlocal logger_name
            if logger_name is None:
                logger_name = func.__module__
            logger = get_logger(logger_name)
            
            # Build context
            context = {
                'function': func.__name__,
                'module': func.__module__,
            }
            
            if log_args:
                # Be careful with sensitive data in args
                from .sanitize import sanitize_dict
                context['args'] = sanitize_dict({'args': args, 'kwargs': kwargs})
            
            # Log entry
            logger.log(level, f"Entering {func.__name__}", extra=context)
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Log result if requested
                if log_result:
                    from .sanitize import scrub_payload
                    context['result'] = scrub_payload(result)
                
                # Log success
                logger.log(level, f"Exiting {func.__name__} successfully", extra=context)
                
                return result
                
            except Exception as e:
                # Log exception
                logger.exception(
                    f"Exception in {func.__name__}: {e}",
                    extra=context
                )
                raise
        
        return wrapper
    return decorator