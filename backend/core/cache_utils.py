"""
Cache utilities for DRF-safe multi-tenant caching with tagging.

Provides helpers for building cache keys, tagging for invalidation,
and get-or-set operations with anti-stampede locks.

SOC I compliant: No browser cache, server-side only, graceful fallbacks.
"""

import hashlib
import json
from typing import Any, Callable, Optional, Tuple
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def _is_redis_backend() -> bool:
    """
    Check if the default cache backend is Redis.
    
    Returns:
        True if Redis, False otherwise (FileBasedCache, Memcached, etc.)
    """
    backend = settings.CACHES.get('default', {}).get('BACKEND', '')
    return 'redis' in backend.lower()


def build_drf_cache_key(
    namespace: str,
    client_id: int,
    user_id: Optional[int] = None,
    perm_version: str = "v1",
    query_string: str = "",
    extra: str = "",
    version: int = 1,
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
    
    Args:
        namespace: Cache namespace (e.g., 'users_list', 'user_detail')
        client_id: Client account ID (tenant)
        user_id: Optional user ID for user-specific caching
        perm_version: Permission version string (default: 'v1')
        query_string: Query parameters as string (will be hashed)
        extra: Additional context string
        version: Cache schema version (default: 1)
    
    Returns:
        Cache key string
        
    Example:
        >>> build_drf_cache_key('users_list', 42, user_id=7, query_string='search=john&ordering=name')
        'crm:v1:c42:u7:pv1:users_list:qe8f3a9b'
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
    
    if query_hash:
        key_parts.append(query_hash.lstrip(":"))
    
    if extra:
        extra_hash = hashlib.md5(extra.encode()).hexdigest()[:6]
        key_parts.append(f"x{extra_hash}")
    
    return ":".join(key_parts)


def tag_key(client_id: int, namespace: str, key: str) -> None:
    """
    Tag a cache key for later invalidation (Redis only).
    
    Uses Redis SET to store the association between a tag and keys.
    Tag format: "crm:tag:c{client_id}:{namespace}"
    
    This avoids using KEYS pattern matching (forbidden in production Redis).
    
    Falls back gracefully if not using Redis backend.
    
    Args:
        client_id: Client account ID
        namespace: Cache namespace (e.g., 'users')
        key: Cache key to tag
        
    Example:
        >>> tag_key(42, 'users', 'crm:v1:c42:users_list:q1a2b3c4')
    """
    if not _is_redis_backend():
        # Tagging not supported for non-Redis backends
        return
    
    try:
        tag_name = f"crm:tag:c{client_id}:{namespace}"
        # Add key to the SET
        cache_client = cache.client.get_client()
        cache_client.sadd(tag_name, key)
        # Set TTL on tag (same as longest cache entry, e.g., 1 hour)
        cache_client.expire(tag_name, 3600)
    except Exception as e:
        # Graceful degradation: log but don't break request
        logger.warning(f"Failed to tag cache key {key}: {e}", exc_info=settings.DEBUG)


def invalidate_tag(client_id: int, namespace: str) -> int:
    """
    Invalidate all cache keys associated with a tag (Redis only).
    
    Retrieves all keys from the tag SET and deletes them.
    Does NOT use KEYS pattern matching.
    
    Falls back gracefully if not using Redis backend.
    
    Args:
        client_id: Client account ID
        namespace: Cache namespace (e.g., 'users')
        
    Returns:
        Number of keys invalidated
        
    Example:
        >>> invalidate_tag(42, 'users')  # Invalidates all user-related cache for client 42
        3
    """
    if not _is_redis_backend():
        # Tagging not supported for non-Redis backends
        # Full cache clear as fallback (nuclear option)
        logger.info(f"Non-Redis backend: clearing entire cache for invalidation")
        cache.clear()
        return 0
    
    try:
        tag_name = f"crm:tag:c{client_id}:{namespace}"
        cache_client = cache.client.get_client()
        
        # Get all keys in the SET
        keys_to_delete = cache_client.smembers(tag_name)
        
        if not keys_to_delete:
            return 0
        
        # Delete all keys
        deleted_count = cache_client.delete(*keys_to_delete)
        
        # Delete the tag SET itself
        cache_client.delete(tag_name)
        
        logger.info(f"Invalidated {deleted_count} cache keys for tag {tag_name}")
        return deleted_count
        
    except Exception as e:
        # Graceful degradation
        logger.warning(f"Failed to invalidate tag c{client_id}:{namespace}: {e}", exc_info=settings.DEBUG)
        return 0


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
    
    Args:
        key: Cache key
        producer: Function that produces the value if cache miss
        ttl: Time-to-live in seconds
        tag: Optional (client_id, namespace) tuple for tagging (Redis only)
        
    Returns:
        Cached or freshly produced value
        
    Example:
        >>> def get_users():
        ...     return User.objects.filter(client_id=42).values()
        >>> users = cache_get_set('crm:v1:c42:users_list', get_users, 300, tag=(42, 'users'))
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
    Redis-specific cache get-or-set with lock and tagging.
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
            
            # Tag for invalidation if requested
            if tag:
                client_id, namespace = tag
                tag_key(client_id, namespace, key)
            
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
            
            if tag:
                client_id, namespace = tag
                tag_key(client_id, namespace, key)
            
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