"""
Cache utilities for DRF-safe multi-tenant caching with tag versioning.

Provides helpers for building cache keys, versioned tagging for O(1) invalidation,
and get-or-set operations with anti-stampede locks.

Tag Versioning System:
- Each tag has a version counter stored in Redis (crm:tag_version:c{client_id}:{namespace})
- Cache keys include this version (e.g., crm:v1:c42:users_list:tv5)
- Invalidation = INCR version (O(1) atomic), making all old keys instantly stale
- No need for SET/smembers/delete pattern (avoids timeout issues)
- Falls back to local memory if Redis unavailable

Signal Control System:
- Context manager to temporarily disable cache invalidation signals during bulk operations
- Thread-safe using threading.local()
- Prevents N signal calls when processing N objects in bulk

SOC I compliant: No browser cache, server-side only, graceful fallbacks.
"""

import hashlib
import json
import time
import threading
from typing import Any, Callable, Optional, Tuple
from collections import defaultdict
from contextlib import contextmanager
from django.core.cache import cache
from django.conf import settings
from typing import Sequence, Union
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# TAG VERSIONING SYSTEM - Fallback & Health Check
# ============================================================================

# Fallback mémoire locale pour dev sans Redis
# Note: Se réinitialise à chaque redémarrage du serveur
_local_tag_versions = defaultdict(int)

# Cache pour health check Redis (mémoïsé avec TTL)
_redis_health_cache = {"healthy": None, "expires_at": 0}

# Thread-local flag pour désactiver les signals de cache
_signals_disabled = threading.local()

# Runtime flag to enable/disable bulk signal optimization
# Set to False to rollback to old behavior (signals always fire)
BULK_SIGNALS_DISABLED = getattr(
    settings,
    'BULK_SIGNALS_DISABLED',
    True  # True by default (signals disabled during bulk = optimized behavior)
)


def _is_redis_backend() -> bool:
    """
    Check if the default cache backend is Redis.
    
    Returns:
        True if Redis, False otherwise (FileBasedCache, Memcached, etc.)
    """
    backend = settings.CACHES.get('default', {}).get('BACKEND', '')
    return 'redis' in backend.lower()


def is_redis_healthy(ttl: int = 10) -> bool:
    """
    Check if Redis is healthy with memoized result.
    
    Pings Redis with timeout and caches the result for TTL seconds
    to avoid repeated health checks during bulk operations.
    
    Args:
        ttl: Cache duration in seconds (default 10s)
    
    Returns:
        True if Redis responds within 100ms, False otherwise
    
    Example:
        >>> is_redis_healthy()  # First call: pings Redis
        True
        >>> is_redis_healthy()  # Within 10s: returns cached result
        True
    """
    # Vérifier si Redis est configuré
    if not _is_redis_backend():
        return False
    
    # Vérifier cache mémoïsé
    now = time.time()
    if now < _redis_health_cache["expires_at"]:
        return _redis_health_cache["healthy"]
    
    # Ping Redis avec timeout
    healthy = _ping_redis(timeout_ms=100)
    
    # Mémoriser résultat
    _redis_health_cache["healthy"] = healthy
    _redis_health_cache["expires_at"] = now + ttl
    
    # Log une seule fois par TTL si unhealthy
    if not healthy:
        logger.warning(
            "Redis health check failed - cache operations will use fallback",
            extra={"timeout_ms": 100, "ttl_seconds": ttl}
        )
    
    return healthy


def _ping_redis(timeout_ms: int = 100) -> bool:
    """
    Ping Redis with timeout.
    
    Args:
        timeout_ms: Timeout in milliseconds
    
    Returns:
        True if ping succeeds within timeout, False otherwise
    """
    try:
        cache_client = cache.client.get_client()
        
        # Configurer socket timeout temporairement
        connection_kwargs = cache_client.connection_pool.connection_kwargs
        original_timeout = connection_kwargs.get('socket_timeout')
        connection_kwargs['socket_timeout'] = timeout_ms / 1000.0
        
        # Ping Redis
        result = cache_client.ping()
        
        # Restaurer timeout original
        if original_timeout is not None:
            connection_kwargs['socket_timeout'] = original_timeout
        
        return result
        
    except (ConnectionRefusedError, TimeoutError, Exception) as e:
        logger.debug(f"Redis ping failed: {e}", exc_info=settings.DEBUG)
        return False


def get_tag_version(client_id: int, namespace: str) -> int:
    """
    Get current version for a cache tag.
    
    Uses Redis GET for versioning. Falls back to local memory if Redis unavailable.
    
    Args:
        client_id: Client account ID
        namespace: Cache namespace (e.g., 'users')
    
    Returns:
        Current tag version (integer)
    
    Example:
        >>> get_tag_version(42, 'users')
        5
    """
    tag_name = f"crm:tag_version:c{client_id}:{namespace}"
    
    # Si Redis down, utiliser fallback local
    if not is_redis_healthy():
        return _local_tag_versions[tag_name]
    
    try:
        cache_client = cache.client.get_client()
        version = cache_client.get(tag_name)
        
        # Initialiser si n'existe pas
        if version is None:
            cache_client.set(tag_name, 0, ex=86400)  # TTL 24h
            return 0
        
        return int(version)
        
    except Exception as e:
        logger.warning(f"Failed to get tag version for {tag_name}: {e}", exc_info=settings.DEBUG)
        return _local_tag_versions[tag_name]


def increment_tag_version(client_id: int, namespace: str) -> int:
    """
    Increment tag version to invalidate all associated cache keys.
    
    This is O(1) atomic operation, replacing smembers + delete pattern.
    All cache keys with old version become instantly stale.
    
    Args:
        client_id: Client account ID
        namespace: Cache namespace (e.g., 'users')
    
    Returns:
        New tag version (integer)
    
    Example:
        >>> increment_tag_version(42, 'users')
        6
    """
    tag_name = f"crm:tag_version:c{client_id}:{namespace}"
    
    # Si Redis down, utiliser fallback local
    if not is_redis_healthy():
        _local_tag_versions[tag_name] += 1
        logger.info(
            f"Tag version incremented locally: {tag_name} → {_local_tag_versions[tag_name]}"
        )
        return _local_tag_versions[tag_name]
    
    try:
        cache_client = cache.client.get_client()
        new_version = cache_client.incr(tag_name)
        cache_client.expire(tag_name, 86400)  # Refresh TTL 24h
        
        logger.info(f"Tag version incremented: {tag_name} → {new_version}")
        return new_version
        
    except Exception as e:
        logger.warning(
            f"Failed to increment tag version for {tag_name}: {e}",
            exc_info=settings.DEBUG
        )
        _local_tag_versions[tag_name] += 1
        return _local_tag_versions[tag_name]


# ============================================================================
# SIGNAL CONTROL SYSTEM
# ============================================================================

@contextmanager
def disable_signals():
    """
    Context manager to temporarily disable cache invalidation signals.
    
    Used during bulk operations to prevent N signal calls for N objects.
    Thread-safe using threading.local().
    
    Usage:
        with disable_signals():
            # Bulk operations here
            for user in users:
                user.save()  # Signal won't fire
            
            # Manual invalidation after all saves
            invalidate_tag(client_id, 'users')
    
    Example:
        >>> with disable_signals():
        ...     User.objects.bulk_create([user1, user2, user3])
        ...     invalidate_tag(42, 'users')  # Single invalidation
    """
    # Check runtime flag - if disabled, signals will fire normally
    if not BULK_SIGNALS_DISABLED:
        logger.info(
            "BULK_SIGNALS_DISABLED=False: Signals will fire normally (rollback mode)"
        )
        # Don't disable signals, just yield without modification
        yield
        return
        
    
    # Set flag to disable signals
    _signals_disabled.value = True
    
    try:
        yield
    finally:
        # Always restore signal state
        _signals_disabled.value = False


def are_signals_disabled() -> bool:
    """
    Check if cache invalidation signals are currently disabled.
    
    Called by signal receivers to determine if they should skip execution.
    
    Returns:
        True if signals are disabled, False otherwise
    
    Example:
        >>> are_signals_disabled()
        False
        >>> with disable_signals():
        ...     are_signals_disabled()
        True
    """
    return getattr(_signals_disabled, 'value', False)



@contextmanager
def disable_signals_with_invalidation(
    client_id: int,
    namespaces: Union[str, Sequence[str]],
    *,
    invalidate_on_error: bool = False,
):
    """
    Désactive temporairement les signaux (si BULK_SIGNALS_DISABLED=True) et invalide automatiquement les tags.
    - Invalidation auto :
        • en transaction : via transaction.on_commit()
        • hors transaction : immédiate
    - Top-level only : une seule invalidation si contextes imbriqués
    - Par défaut, pas d’invalidation si exception (invalidate_on_error=False)
    """
    if not client_id:
        raise ValueError("disable_signals_with_invalidation() requires a valid client_id")

    if isinstance(namespaces, str):
        namespaces = [namespaces]

    def _invalidate_all():
        for ns in namespaces:
            try:
                new_version = invalidate_tag(client_id, ns)
                logger.info(
                    "Auto-invalidation effectuée",
                    extra={"client_id": client_id, "namespace": ns, "new_version": new_version}
                )
            except Exception as e:
                logger.warning(
                    f"Auto-invalidation échouée pour namespace '{ns}': {e}",
                    exc_info=settings.DEBUG
                )

    def _schedule_invalidation():
        # Si on est dans une transaction: invalider après commit
        try:
            if transaction.get_connection().in_atomic_block:
                transaction.on_commit(_invalidate_all)
                return
        except Exception:
            # Fallback si pas de connection active
            pass
        _invalidate_all()

    # --- CAS 1 : signaux actifs (BULK_SIGNALS_DISABLED=False) ---
    # -> on laisse les signaux s'exécuter, mais on conserve l'invalidation auto pour éviter le stale cache
    if not BULK_SIGNALS_DISABLED:
        logger.info("BULK_SIGNALS_DISABLED=False: signals actifs + invalidation auto")
        success = False
        try:
            yield
            success = True
        finally:
            if success or invalidate_on_error:
                _schedule_invalidation()
        return

    # --- CAS 2 : signaux désactivés (BULK_SIGNALS_DISABLED=True) ---
    was_disabled = are_signals_disabled()
    top_level = not was_disabled
    _signals_disabled.value = True

    success = False
    try:
        yield
        success = True
    finally:
        if top_level:
            _signals_disabled.value = False

            if success or invalidate_on_error:
                _schedule_invalidation()
            else:
                logger.info(
                    "Auto-invalidation annulée (exception détectée et invalidate_on_error=False)",
                    extra={"client_id": client_id, "namespaces": list(namespaces)}
                )


# ============================================================================
# CACHE KEY BUILDING
# ============================================================================

def build_drf_cache_key(
    namespace: str,
    client_id: int,
    user_id: Optional[int] = None,
    perm_version: str = "v1",
    query_string: str = "",
    extra: str = "",
    version: int = 1,
    tag_namespace: Optional[str] = None,
) -> str:
    """
    Build a DRF-safe cache key for multi-tenant application.
    
    The key includes:
    - namespace: Feature/endpoint identifier (e.g., 'users_list')
    - client_id: Tenant identifier (prevents cross-tenant leaks)
    - user_id: User identifier (for user-specific caching)
    - perm_version: Permission version (bump to invalidate on perm changes)
    - query_string: Hashed query parameters (search, filters, ordering)
    - extra: Any additional context
    - version: Cache schema version (bump to invalidate all)
    - tag_namespace: Optional namespace for tag versioning (e.g., 'users')
                     If provided, includes tag version in key (e.g., tv5)
    
    Args:
        namespace: Cache namespace (e.g., 'users_list', 'user_detail')
        client_id: Client account ID (tenant)
        user_id: Optional user ID for user-specific caching
        perm_version: Permission version string (default: 'v1')
        query_string: Query parameters as string (will be hashed)
        extra: Additional context string
        version: Cache schema version (default: 1)
        tag_namespace: Optional tag namespace for versioning (e.g., 'users')
    
    Returns:
        Cache key string
        
    Example:
        >>> build_drf_cache_key('users_list', 42, user_id=7, query_string='search=john&ordering=name')
        'crm:v1:c42:u7:pv1:users_list:qe8f3a9b'
        
        >>> build_drf_cache_key('users_list', 42, tag_namespace='users')
        'crm:v1:c42:pv1:users_list:tv5'  # tv5 = tag version 5
    """
    # Hash query string to keep key length reasonable
    query_hash = ""
    if query_string:
        query_hash = f":q{hashlib.md5(query_string.encode()).hexdigest()[:8]}"
    
    # Build key components
    key_parts = [
        settings.CACHES["default"].get("KEY_PREFIX", "crm"),
        f"v{version}",
        f"c{client_id}",
    ]
    
    if user_id:
        key_parts.append(f"u{user_id}")
    
    key_parts.append(f"p{perm_version}")
    key_parts.append(namespace)
    
    # Include tag version if tag_namespace provided
    if tag_namespace:
        tag_version = get_tag_version(client_id, tag_namespace)
        key_parts.append(f"tv{tag_version}")
    
    if query_hash:
        key_parts.append(query_hash.lstrip(":"))
    
    if extra:
        extra_hash = hashlib.md5(extra.encode()).hexdigest()[:6]
        key_parts.append(f"x{extra_hash}")
    
    return ":".join(key_parts)


# ============================================================================
# CACHE INVALIDATION
# ============================================================================

def invalidate_tag(client_id: int, namespace: str) -> int:
    """
    Invalidate all cache keys associated with a tag using versioning.
    
    Increments tag version (O(1) atomic operation).
    Old cache keys become instantly stale without iteration or deletion.
    
    This replaces the old SET/smembers/delete pattern which could timeout
    with large datasets.
    
    Falls back gracefully if not using Redis backend.
    
    Args:
        client_id: Client account ID
        namespace: Cache namespace (e.g., 'users')
        
    Returns:
        New tag version (for logging compatibility)
        
    Example:
        >>> invalidate_tag(42, 'users')  # All user cache instantly stale
        6
    """
    if not _is_redis_backend():
        # Tagging not supported for non-Redis backends
        # Full cache clear as fallback (nuclear option)
        logger.info(f"Non-Redis backend: clearing entire cache for invalidation")
        cache.clear()
        return 0
    
    # Health check already done inside increment_tag_version()
    new_version = increment_tag_version(client_id, namespace)
    
    # Return version as "invalidated count" for backward compatibility with logs
    return new_version


# ============================================================================
# CACHE GET-OR-SET
# ============================================================================

def cache_get_set(
    key: str,
    producer: Callable[[], Any],
    ttl: int,
    tag: Optional[Tuple[int, str]] = None,
) -> Any:
    """
    Get value from cache or set it using producer function.
    
    With Redis: Includes best-effort lock to prevent cache stampede.
    With FileBasedCache: Simple get-or-set (no lock, no tagging).
    
    Note: The 'tag' parameter is kept for backward compatibility but is no longer
    used for tagging. Tagging is now handled automatically via tag_namespace
    in build_drf_cache_key().
    
    Args:
        key: Cache key (should include tag version via build_drf_cache_key)
        producer: Function that produces the value if cache miss
        ttl: Time-to-live in seconds
        tag: Optional (client_id, namespace) tuple (kept for compatibility, not used)
        
    Returns:
        Cached or freshly produced value
        
    Example:
        >>> def get_users():
        ...     return User.objects.filter(client_id=42).values()
        >>> cache_key = build_drf_cache_key('users_list', 42, tag_namespace='users')
        >>> users = cache_get_set(cache_key, get_users, 300)
    """
    # Try to get from cache
    value = cache.get(key)
    if value is not None:
        return value
    
    # Cache miss - need to produce value
    if _is_redis_backend():
        # Redis: Use lock to prevent stampede
        return _cache_get_set_redis(key, producer, ttl, tag)
    else:
        # FileBasedCache: Simple get-or-set
        return _cache_get_set_simple(key, producer, ttl)


def _cache_get_set_simple(
    key: str,
    producer: Callable[[], Any],
    ttl: int,
) -> Any:
    """
    Simple cache get-or-set for non-Redis backends.
    
    No lock, no tagging. Just produce and store.
    """
    try:
        # Produce value
        value = producer()
        
        # Store in cache
        cache.set(key, value, ttl)
        
        return value
    except Exception as e:
        # Graceful degradation: if cache fails, just produce value
        logger.warning(f"Cache set failed for key {key}: {e}", exc_info=settings.DEBUG)
        return producer()


def _cache_get_set_redis(
    key: str,
    producer: Callable[[], Any],
    ttl: int,
    tag: Optional[Tuple[int, str]] = None,
) -> Any:
    """
    Redis-specific cache get-or-set with lock.
    
    Note: Tagging is no longer performed here. It's handled automatically
    via tag versioning in build_drf_cache_key().
    """
    lock_key = f"{key}:lock"
    lock_acquired = False
    
    try:
        cache_client = cache.client.get_client()
        
        # Try to acquire lock (5 second TTL)
        lock_acquired = cache_client.set(lock_key, "1", nx=True, ex=5)
        
        if lock_acquired:
            # We got the lock, produce the value
            value = producer()
            
            # Store in cache
            cache.set(key, value, ttl)
            
            # Note: No need to call tag_key() anymore
            # Tagging is handled via version in cache key
            
            return value
        else:
            # Another process is building the cache, wait briefly then retry
            import time
            time.sleep(0.1)
            
            # Check cache again
            value = cache.get(key)
            if value is not None:
                return value
            
            # Still not there, produce anyway (stampede allowed in this edge case)
            value = producer()
            cache.set(key, value, ttl)
            
            return value
            
    except Exception as e:
        # Graceful degradation: if cache fails, just produce value without caching
        logger.warning(f"Redis cache operation failed for key {key}: {e}", exc_info=settings.DEBUG)
        return producer()
        
    finally:
        # Release lock if we acquired it
        if lock_acquired:
            try:
                cache_client.delete(lock_key)
            except Exception:
                pass  # Best effort


# ============================================================================
# UTILITIES
# ============================================================================

def get_permissions_version() -> str:
    """
    Get current permissions version for cache invalidation.
    
    When permissions change, bump this version to invalidate all
    permission-dependent cache entries.
    
    Returns:
        Permission version string (default: 'v1')
        
    Example:
        >>> get_permissions_version()
        'v1'
    """
    return getattr(settings, 'PERMISSIONS_VERSION', 'v1')