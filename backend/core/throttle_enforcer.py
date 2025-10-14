# backend/core/throttle_enforcer.py

"""
Dual-key throttle enforcer for login security.

Implements AND-model rate limiting:
- IP-based throttle: limits attempts from same source IP
- Identifier-based throttle: limits attempts for same email/username

Both limits must pass for request to proceed. If either is exceeded,
request is blocked before authentication runs.

Uses Redis INCR with TTL for atomic counters when available,
falls back to Django cache (file-based) gracefully.
"""

import time
import math
import logging
from typing import Dict, Optional, Tuple
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger('core.throttling')


# ============================================================================
# CONFIGURATION
# ============================================================================

def _get_throttle_rates() -> Dict[str, str]:
    """
    Get throttle rates from settings.
    
    Returns:
        dict: Throttle rates (e.g., {'login': '5/hour', 'burst': '10/minute'})
    """
    return settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})


def _parse_rate(rate_str: str) -> Tuple[int, int]:
    """
    Parse rate string into (num_requests, duration_seconds).
    
    Args:
        rate_str: Rate string like '5/hour', '10/minute', '100/day'
    
    Returns:
        tuple: (num_requests, duration_in_seconds)
    
    Examples:
        >>> _parse_rate('5/hour')
        (5, 3600)
        >>> _parse_rate('10/minute')
        (10, 60)
    """
    if not rate_str:
        return (0, 0)
    
    num, period = rate_str.split('/')
    num_requests = int(num)
    
    duration_map = {
        'second': 1,
        'minute': 60,
        'hour': 3600,
        'day': 86400,
    }
    
    duration_seconds = duration_map.get(period, 3600)
    return (num_requests, duration_seconds)


def _get_client_ip(request) -> str:
    """
    Extract real client IP from request, respecting proxy headers.
    
    Checks X-Forwarded-For header first (for proxies/load balancers),
    falls back to REMOTE_ADDR.
    
    Args:
        request: Django/DRF request object
    
    Returns:
        str: Client IP address
    """
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        # Take first IP in proxy chain (original client)
        ip = xff.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    
    return ip


def _is_whitelisted(ip: str, email: Optional[str], user) -> bool:
    """
    Check if IP or user is whitelisted (exempt from throttling).
    
    Args:
        ip: Client IP address
        email: User email (if available)
        user: Request user object (if authenticated)
    
    Returns:
        bool: True if whitelisted, False otherwise
    """
    # Check IP whitelist
    whitelist_ips = getattr(settings, 'THROTTLE_WHITELIST_IPS', [])
    if ip in whitelist_ips:
        logger.debug(f"IP {ip} is whitelisted, skipping throttle")
        return True
    
    # Check user whitelist (for authenticated users)
    if user and getattr(user, 'is_authenticated', False):
        whitelist_users = getattr(settings, 'THROTTLE_WHITELIST_USERS', [])
        if user.email in whitelist_users:
            logger.debug(f"User {user.email} is whitelisted, skipping throttle")
            return True
    
    # Check email whitelist (for login attempts)
    if email:
        whitelist_users = getattr(settings, 'THROTTLE_WHITELIST_USERS', [])
        if email.lower() in [u.lower() for u in whitelist_users]:
            logger.debug(f"Email {email} is whitelisted, skipping throttle")
            return True
    
    return False


# ============================================================================
# CACHE KEY BUILDERS
# ============================================================================

def _build_ip_key(scope: str, ip: str) -> str:
    """Build cache key for IP-based throttling."""
    return f"throttle_{scope}_ip:{ip}"


def _build_identifier_key(scope: str, identifier: str) -> str:
    """Build cache key for identifier-based throttling (email/username)."""
    return f"throttle_{scope}_id:{identifier.lower()}"


# ============================================================================
# THROTTLE CHECKING
# ============================================================================

def _check_single_key(
    cache_key: str,
    num_requests: int,
    duration_seconds: int
) -> Tuple[bool, int]:
    """
    Check throttle status for a single cache key.
    
    Uses Redis INCR with TTL for atomic counting when available.
    Falls back to list-based history tracking for non-Redis backends.
    
    Args:
        cache_key: Cache key to check
        num_requests: Maximum allowed requests
        duration_seconds: Time window in seconds
    
    Returns:
        tuple: (is_throttled: bool, wait_seconds: int)
    """
    # Try Redis INCR approach (atomic, efficient)
    from core.cache_utils import _is_redis_backend, is_redis_healthy
    
    if _is_redis_backend() and is_redis_healthy():
        try:
            cache_client = cache.client.get_client()
            
            # Atomic increment
            current_count = cache_client.incr(cache_key)
            
            # Set TTL on first request
            if current_count == 1:
                cache_client.expire(cache_key, duration_seconds)
            
            # Check if throttled
            if current_count > num_requests:
                # Calculate wait time from TTL
                ttl = cache_client.ttl(cache_key)
                wait_seconds = max(0, ttl) if ttl > 0 else 0
                return (True, wait_seconds)
            
            return (False, 0)
            
        except Exception as e:
            logger.warning(
                f"Redis throttle check failed for {cache_key}: {e}",
                exc_info=settings.DEBUG
            )
            # Fall through to history-based approach
    
    # Fallback: history-based approach (works with any cache backend)
    now = time.time()
    history = cache.get(cache_key, []) or []
    
    # Purge old entries outside time window
    cutoff = now - duration_seconds
    history = [ts for ts in history if ts > cutoff]
    
    # Check if throttled
    if len(history) >= num_requests:
        # Calculate wait time until oldest entry expires
        oldest = min(history)
        wait_seconds = max(0, int(math.ceil((oldest + duration_seconds) - now)))
        return (True, wait_seconds)
    
    # Not throttled - record this attempt
    history.append(now)
    cache.set(cache_key, history, duration_seconds)
    
    return (False, 0)


# ============================================================================
# PUBLIC API
# ============================================================================

def check_dual_throttle(
    request,
    email: str,
    scope: str = 'login'
) -> Dict[str, any]:
    """
    Check dual-key throttle: IP AND identifier (email).
    
    Implements AND-model rate limiting:
    - Checks IP-based limit (prevents IP-based attacks)
    - Checks email-based limit (prevents account-targeted attacks)
    - Both must pass for request to proceed
    
    Args:
        request: Django/DRF request object
        email: Email/username to check (case-insensitive)
        scope: Throttle scope (default: 'login')
    
    Returns:
        dict: {
            'is_throttled': bool,      # True if throttled
            'wait_seconds': int,       # Seconds to wait
            'violated_key': str|None,  # Which key was violated ('ip' or 'email')
            'details': dict            # Detailed state for logging
        }
    
    Example:
        >>> result = check_dual_throttle(request, 'user@example.com')
        >>> if result['is_throttled']:
        >>>     raise Throttled(wait=result['wait_seconds'])
    """
    ip = _get_client_ip(request)
    user = getattr(request, 'user', None)
    
    # Check whitelist first
    if _is_whitelisted(ip, email, user):
        return {
            'is_throttled': False,
            'wait_seconds': 0,
            'violated_key': None,
            'details': {'whitelisted': True}
        }
    
    # Get rate limits from settings
    rates = _get_throttle_rates()
    rate_str = rates.get(scope)
    
    if not rate_str:
        # No rate configured for this scope - allow by default
        logger.warning(f"No throttle rate configured for scope '{scope}'")
        return {
            'is_throttled': False,
            'wait_seconds': 0,
            'violated_key': None,
            'details': {'no_rate_configured': True}
        }
    
    num_requests, duration_seconds = _parse_rate(rate_str)
    
    if num_requests == 0:
        # Throttling disabled for this scope
        return {
            'is_throttled': False,
            'wait_seconds': 0,
            'violated_key': None,
            'details': {'throttling_disabled': True}
        }
    
    # Check IP-based throttle
    ip_key = _build_ip_key(scope, ip)
    ip_throttled, ip_wait = _check_single_key(ip_key, num_requests, duration_seconds)
    
    # Check email-based throttle
    identifier_key = _build_identifier_key(scope, email)
    id_throttled, id_wait = _check_single_key(
        identifier_key, num_requests, duration_seconds
    )
    
    # AND model: if EITHER is throttled, block the request
    if ip_throttled or id_throttled:
        wait_seconds = max(ip_wait, id_wait)
        violated_key = 'ip' if ip_throttled else 'email'
        
        logger.warning(
            f"Throttle limit exceeded: scope={scope} key={violated_key} "
            f"ip={ip} email={email[:3]}*** wait={wait_seconds}s"
        )
        
        return {
            'is_throttled': True,
            'wait_seconds': wait_seconds,
            'violated_key': violated_key,
            'details': {
                'ip': ip,
                'email_prefix': email[:3] + '***' if email else '-',
                'ip_throttled': ip_throttled,
                'id_throttled': id_throttled,
                'rate': rate_str
            }
        }
    
    # Both checks passed - not throttled
    return {
        'is_throttled': False,
        'wait_seconds': 0,
        'violated_key': None,
        'details': {
            'ip': ip,
            'email_prefix': email[:3] + '***' if email else '-',
            'rate': rate_str
        }
    }


def reset_throttle(scope: str, ip: Optional[str] = None, email: Optional[str] = None):
    """
    Reset throttle counters for testing or admin overrides.
    
    Args:
        scope: Throttle scope (e.g., 'login')
        ip: IP address to reset (optional)
        email: Email/identifier to reset (optional)
    
    Returns:
        dict: {'ip_reset': bool, 'email_reset': bool}
    
    Example:
        >>> reset_throttle('login', ip='203.0.113.10')
        {'ip_reset': True, 'email_reset': False}
    """
    result = {'ip_reset': False, 'email_reset': False}
    
    if ip:
        ip_key = _build_ip_key(scope, ip)
        cache.delete(ip_key)
        result['ip_reset'] = True
        logger.info(f"Throttle reset: scope={scope} ip={ip}")
    
    if email:
        id_key = _build_identifier_key(scope, email)
        cache.delete(id_key)
        result['email_reset'] = True
        logger.info(f"Throttle reset: scope={scope} email={email[:3]}***")
    
    return result