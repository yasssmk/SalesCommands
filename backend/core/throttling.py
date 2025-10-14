# backend/core/throttling.py

"""
Custom throttle classes for Django REST Framework.

These classes provide fine-grained rate limiting for sensitive endpoints
to prevent abuse and brute force attacks.
"""

import logging
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, SimpleRateThrottle
from rest_framework.exceptions import Throttled

logger = logging.getLogger('core.throttling')


class BaseCustomThrottle(SimpleRateThrottle):
    """
    Base class for custom throttles with enhanced logging and whitelist support.
    """
    
    def __init__(self):
        """Initialize throttle and ensure rate is set from settings."""
        super().__init__()
        # Ensure the rate is loaded from settings if not already set
        if not self.rate:
            self.rate = self.get_rate()
    
    def get_rate(self):
        """
        Get the throttle rate from settings.
        Overrides parent to ensure we get the rate from our THROTTLE_RATES config.
        """
        if not getattr(self, 'scope', None):
            msg = ("You must set either `.scope` or `.rate` for '%s' throttle" %
                   self.__class__.__name__)
            raise ImproperlyConfigured(msg)
        
        try:
            # Get from Django settings REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
            from django.conf import settings
            rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
            return rates[self.scope]
        except KeyError:
            msg = "No default throttle rate set for '%s' scope" % self.scope
            raise ImproperlyConfigured(msg)
    
    def get_ident(self, request):
        """
        Get unique identifier for the request.
        Checks whitelist before returning identifier.
        """
        # Get IP address from headers or direct connection
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        remote_addr = request.META.get('REMOTE_ADDR')
        
        if xff:
            # Take first IP if multiple (proxy chain)
            ip = xff.split(',')[0].strip()
        else:
            ip = remote_addr
            
        # Check IP whitelist if configured
        whitelist_ips = getattr(settings, 'THROTTLE_WHITELIST_IPS', [])
        if ip in whitelist_ips:
            logger.debug(f"IP {ip} is whitelisted, skipping throttle")
            return None  # No throttling for whitelisted IPs
            
        return ip
    
    def get_cache_key(self, request, view):
        """
        Generate cache key for throttle counter.
        Returns None for whitelisted requests (no throttling).
        """
        ident = self.get_ident(request)
        if ident is None:
            return None  # Skip throttling
            
        # Check user whitelist for authenticated users
        if request.user and request.user.is_authenticated:
            whitelist_users = getattr(settings, 'THROTTLE_WHITELIST_USERS', [])
            if request.user.email in whitelist_users:
                logger.debug(f"User {request.user.email} is whitelisted, skipping throttle")
                return None  # Skip throttling for whitelisted users
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
    
    def throttle_failure(self):
        """
        Called when a request is throttled.
        Logs the event and returns custom error message.
        """
        import math
        # Calculer une valeur numérique de wait en secondes (>= 0)
        try:
            wait_seconds = self.wait()
            wait_seconds = 0 if wait_seconds is None else max(0, int(math.ceil(wait_seconds)))
        except Exception:
            wait_seconds = 0

        logger.warning(
            f"Throttle limit exceeded for scope='{self.scope}' "
            f"rate={self.num_requests}/{self.duration}s wait={wait_seconds}s"
        )

        # Message personnalisé si configuré
        error_messages = getattr(settings, 'THROTTLE_ERROR_MESSAGES', {})
        default_msg = f"Request was throttled. Please retry in {wait_seconds} seconds."
        message = error_messages.get(self.scope, default_msg)

        raise Throttled(detail=message)



class LoginRateThrottle(BaseCustomThrottle):

    """
    Throttle for login attempts with dual-key enforcement.
    
    Implements AND-model rate limiting:
    - IP-based throttle: prevents brute force from single source
    - Email-based throttle: prevents account-targeted attacks
    
    Both limits must pass for request to proceed. If either is exceeded,
    request is blocked BEFORE authentication runs.
    
    Uses the new throttle_enforcer module for atomic dual-key checking.
    """
    scope = 'login'
    
    def __init__(self):
        """Initialize throttle with rate from settings."""
        super().__init__()
        # Store throttle result for use in throttle_failure()
        self._throttle_result = None
    
    def allow_request(self, request, view):
        """
        Check if request should be allowed.
        
        Overrides DRF's default behavior to implement dual-key throttling.
        Uses throttle_enforcer for AND-model enforcement.
        
        Returns:
            bool: True if request allowed, False if throttled
        """
        # Import here to avoid circular imports
        from core.throttle_enforcer import check_dual_throttle
        
        # Extract email from request data
        email = None
        if request.data:
            email = request.data.get('email', '')
        
        # If no email provided, we can't throttle by identifier
        # Fall back to IP-only throttling via parent class
        if not email:
            logger.debug("No email in login request, using IP-only throttle")
            return super().allow_request(request, view)
        
        # Check dual throttle (IP AND email)
        self._throttle_result = check_dual_throttle(
            request=request,
            email=email,
            scope=self.scope
        )
        
        # If throttled, return False to trigger throttle_failure()
        if self._throttle_result['is_throttled']:
            return False
        
        # Not throttled - allow request
        return True
    
    def wait(self):
        """
        Return number of seconds to wait before retry.
        
        Called by DRF when throttled to populate Retry-After header.
        
        Returns:
            int: Seconds to wait (0 if unknown)
        """
        if self._throttle_result:
            return self._throttle_result.get('wait_seconds', 0)
        
        # Fallback to parent implementation
        try:
            return super().wait()
        except Exception:
            return 0
    
    def throttle_failure(self):
        """
        Called when request is throttled.
        
        Logs the throttle event with detailed context and raises
        Throttled exception with user-friendly message.
        """
        import math
        
        # Get wait time (ensure it's a valid integer >= 0)
        try:
            wait_seconds = self.wait()
            wait_seconds = 0 if wait_seconds is None else max(0, int(math.ceil(wait_seconds)))
        except Exception:
            wait_seconds = 0
        
        # Log with detailed context from enforcer
        if self._throttle_result:
            details = self._throttle_result.get('details', {})
            violated_key = self._throttle_result.get('violated_key', 'unknown')
            
            logger.warning(
                f"Login throttle exceeded: "
                f"key={violated_key} "
                f"ip={details.get('ip', '-')} "
                f"email={details.get('email_prefix', '-')} "
                f"rate={details.get('rate', '-')} "
                f"wait={wait_seconds}s"
            )
        else:
            # Fallback logging if no enforcer result
            logger.warning(
                f"Login throttle exceeded "
                f"scope={self.scope} wait={wait_seconds}s"
            )
        
        # Construct user-friendly message
        # Convert wait_seconds to minutes if >= 60 seconds
        if wait_seconds >= 60:
            wait_minutes = math.ceil(wait_seconds / 60)
            time_msg = f"{wait_minutes} minute{'s' if wait_minutes > 1 else ''}"
        else:
            time_msg = f"{wait_seconds} second{'s' if wait_seconds != 1 else ''}"

        message = (
            f"Too many login attempts. Please wait {time_msg} before trying again."
        )
        
        # Raise Throttled exception with wait time (DRF will add Retry-After header)
        raise Throttled(detail=message)
    
    def get_cache_key(self, request, view):
        """
        Generate cache key for DRF compatibility.
        
        Note: This method is kept for backward compatibility with DRF's
        SimpleRateThrottle, but actual throttling is done in allow_request()
        via the dual-key enforcer.
        
        Returns:
            str|None: Cache key (or None for whitelisted requests)
        """
        ident = self.get_ident(request)
        if ident is None:
            return None  # Whitelisted
        
        # Try to get email from request data
        email = None
        if request.data:
            email = request.data.get('email', '')
        
        # Create composite key: IP + email (if available)
        # This maintains compatibility with existing cache patterns
        if email:
            composite_ident = f"{ident}:{email.lower()}"
        else:
            composite_ident = ident
        
        cache_key = self.cache_format % {
            'scope': self.scope,
            'ident': composite_ident
        }
        
        return cache_key
    



class SensitiveActionThrottle(UserRateThrottle):
    """
    Throttle for sensitive actions like:
    - Grant/revoke superuser
    - Delete users
    - Bulk operations
    - Permission changes
    
    Only applies to non-GET requests.
    """
    scope = 'sensitive'
    
    def __init__(self):
        """Ensure rate is loaded for custom scope."""
        super().__init__()
        # Override the rate with our custom scope
        try:
            from django.conf import settings
            rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
            self.rate = rates.get(self.scope)
            if self.rate:
                self.num_requests, self.duration = self.parse_rate(self.rate)
        except Exception:
            pass  # Fall back to parent behavior
    
    def allow_request(self, request, view):
        """
        Only throttle modification requests (POST, PUT, PATCH, DELETE).
        GET requests are not throttled.
        """
        # Skip throttling for safe methods
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
            
        # Check if this is actually a sensitive action
        if hasattr(view, 'action'):
            sensitive_actions = [
                'grant_superuser',
                'destroy',
                'bulk_delete',
                'bulk_update',
                'change_permissions',
            ]
            if view.action not in sensitive_actions:
                return True  # Not a sensitive action
        
        # Apply throttle for sensitive actions
        return super().allow_request(request, view)
    
    def throttle_failure(self):
        """Log sensitive action throttling."""
        import math
        try:
            wait_seconds = self.wait()
            wait_seconds = 0 if wait_seconds is None else max(0, int(math.ceil(wait_seconds)))
        except Exception:
            wait_seconds = 0

        logger.warning(
            f"Sensitive action throttled "
            f"scope='{self.scope}' rate={self.num_requests}/{self.duration}s "
            f"wait={wait_seconds}s"
        )

        message = (
            "This sensitive action has been rate limited for security. "
            f"Please wait {wait_seconds} seconds before trying again."
        )

        raise Throttled(detail=message)



class PasswordChangeThrottle(UserRateThrottle):
    """
    Throttle specifically for password change attempts.
    More restrictive than general user throttle.
    """
    scope = 'password'
    
    def __init__(self):
        """Ensure rate is loaded for custom scope."""
        super().__init__()
        # Override the rate with our custom scope
        try:
            from django.conf import settings
            rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
            self.rate = rates.get(self.scope)
            if self.rate:
                self.num_requests, self.duration = self.parse_rate(self.rate)
        except Exception:
            pass  # Fall back to parent behavior
    
    def throttle_failure(self):
        """Log password change throttling."""
        import math
        try:
            wait_seconds = self.wait()
            wait_seconds = 0 if wait_seconds is None else max(0, int(math.ceil(wait_seconds)))
        except Exception:
            wait_seconds = 0

        logger.warning(
            f"Password change throttled "
            f"scope='{self.scope}' rate={self.num_requests}/{self.duration}s "
            f"wait={wait_seconds}s"
        )

        message = (
            "Too many password change attempts. "
            f"Please wait {wait_seconds} seconds for security reasons."
        )

        raise Throttled(detail=message, wait=wait_seconds)



class BurstRateThrottle(UserRateThrottle):
    """
    Additional throttle to prevent burst requests.
    Limits requests per minute regardless of hourly limit.
    
    Example: User has 100/hour limit but this prevents doing all 100 in 1 minute.
    """
    scope = 'burst'
    
    def __init__(self):
        """Initialize with burst rate from settings or default."""
        super().__init__()
        # Try to get rate from settings, fall back to hardcoded
        try:
            from django.conf import settings
            rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
            custom_rate = rates.get(self.scope)
            if custom_rate:
                self.rate = custom_rate
            else:
                self.rate = '10/minute'  # Fallback default
            self.num_requests, self.duration = self.parse_rate(self.rate)
        except Exception:
            self.rate = '10/minute'
            self.num_requests, self.duration = self.parse_rate(self.rate)


class RegistrationThrottle(AnonRateThrottle):
    """
    Throttle for user registration/signup.
    Prevents mass account creation.
    """
    scope = 'registration'
    
    def __init__(self):
        """Ensure rate is loaded for custom scope."""
        super().__init__()
        # Try to get rate from settings, fall back to hardcoded
        try:
            from django.conf import settings
            rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
            custom_rate = rates.get(self.scope)
            if custom_rate:
                self.rate = custom_rate
            else:
                self.rate = '5/hour'  # Fallback default
            self.num_requests, self.duration = self.parse_rate(self.rate)
        except Exception:
            self.rate = '5/hour'
            self.num_requests, self.duration = self.parse_rate(self.rate)
    
    def get_cache_key(self, request, view):
        """Use IP-based throttling for registration."""
        ident = self.get_ident(request)
        if ident is None:
            return None
            
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
    
    def throttle_failure(self):
        """Log registration throttling."""
        import math
        try:
            wait_seconds = self.wait()
            wait_seconds = 0 if wait_seconds is None else max(0, int(math.ceil(wait_seconds)))
        except Exception:
            wait_seconds = 0

        logger.warning(
            f"Registration throttled scope='{self.scope}' "
            f"rate={self.num_requests}/{self.duration}s wait={wait_seconds}s"
        )

        message = (
            "Too many registration attempts from this IP address. "
            f"Please wait {wait_seconds} seconds."
        )

        raise Throttled(detail=message)


# =====================================================================
# UTILITY FUNCTIONS
# =====================================================================

def check_throttle_status(scope, identifier):
    """
    Check current throttle status exactly as DRF would apply it.
    - Lit les rates depuis settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
    - Utilise la même fenêtre (seconds) que DRF via parse_rate()
    - Épure l'historique hors fenêtre avant de compter
    """
    import time
    from rest_framework.throttling import SimpleRateThrottle

    # 1) Source unique des rates = même que DRF
    rates = getattr(settings, 'REST_FRAMEWORK', {}).get('DEFAULT_THROTTLE_RATES', {})
    rate_str = rates.get(scope)
    if not rate_str:
        return {
            'scope': scope,
            'identifier': identifier,
            'rate': None,
            'requests': 0,
            'limit': None,
            'duration_seconds': None,
            'is_throttled': False,
            'wait_time': 0,
        }

    # 2) Parse DRF (num_requests, duration en secondes)
    #    On instancie SimpleRateThrottle pour réutiliser sa logique officielle.
    parser = SimpleRateThrottle()
    num_requests, duration_seconds = parser.parse_rate(rate_str)

    # 3) Lire l'historique et le purger hors fenêtre
    cache_key = f"throttle_{scope}_{identifier}"
    history = cache.get(cache_key, []) or []
    now = time.time()
    cutoff = now - duration_seconds
    history = [ts for ts in history if ts > cutoff]

    # 4) État courant après purge
    current_requests = len(history)
    is_throttled = current_requests >= num_requests

    # 5) Calcul du temps d'attente
    if is_throttled and history:
        # Le prochain slot se libère quand la plus vieille requête de la fenêtre sort
        oldest = min(history)
        wait_time = max(0, int((oldest + duration_seconds) - now))
    else:
        wait_time = 0

    return {
        'scope': scope,
        'identifier': identifier,
        'rate': rate_str,
        'requests': current_requests,
        'limit': num_requests,
        'duration_seconds': duration_seconds,
        'is_throttled': is_throttled,
        'wait_time': wait_time,
    }

def reset_throttle(scope, identifier):
    """
    Reset throttle counter for a specific identifier.
    Useful for testing or admin overrides.
    
    Args:
        scope: Throttle scope
        identifier: User identifier
        
    Returns:
        bool: True if reset successful
    """
    cache_key = f"throttle_{scope}_{identifier}"
    cache.delete(cache_key)
    logger.info(f"Throttle reset for {scope}:{identifier}")
    return True