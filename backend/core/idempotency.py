"""
Idempotency utilities for bulk operations.

Provides Redis-backed idempotency store for long-running operations:
- Prevents duplicate execution (same key + payload → return cached result)
- Detects conflicts (same key + different payload → 409)
- Enables polling (GET /ops/{key} for status check)
- Graceful degradation in dev (warning if Redis unavailable)
- Hard fail in prod (503 if Redis required but unavailable)

Architecture:
- Redis Key: crm:idemp:op:{client_id}:{key}
- Lock Key: crm:idemp:lock:{client_id}:{key} (distributed lock with SET NX)
- Fields: status, payload_hash, owner, result, error, started_at, completed_at
- TTL: 600s default (10 minutes)

Public Endpoint Exclusions:
The following endpoints are excluded from idempotency checks:
- /client/login/ (authentication)
- /client/logout/ (session management)
- /client/refresh-token/ (token refresh)
- /product_admin/login/ (admin auth)
- /product_admin/register/ (admin registration)
- /healthz/ (health checks)
- /static/* (static files)
- /admin/* (Django admin)

These endpoints either:
1. Don't have tenant context (auth happens before tenant association)
2. Are idempotent by design (POST /login with same credentials → same result)
3. Are infrastructure endpoints (health checks)

For tenant-scoped endpoints (bulk operations, mutations):
- Dev (REQUIRE_REDIS_IDEMPOTENCY=False): Warning if tenant missing, continue with "unknown:anonymous"
- Prod (REQUIRE_REDIS_IDEMPOTENCY=True): ValueError (→ 400/403) if tenant missing

Usage:
    # Start operation
    op = start_op(
        client_id=42,
        key="bulk-delete-abc123",
        payload_hash=compute_payload_hash(request.data),
        owner=get_owner_from_request(request)
    )
    if op and op['status'] == 'succeeded':
        return op['result']  # Already done, return cached
    
    # Execute operation
    try:
        result = perform_bulk_delete(...)
        complete_op(client_id, key, result)
    except Exception as e:
        fail_op(client_id, key, str(e))
        raise
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from django.conf import settings
from django.core.cache import cache
from core.cache_utils import is_redis_healthy

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

# Default TTL for operation state (10 minutes)
DEFAULT_TTL = 600

# Require Redis in production (env var override)
REQUIRE_REDIS_IDEMPOTENCY = getattr(
    settings, 
    'REQUIRE_REDIS_IDEMPOTENCY', 
    False  # False by default, set True in prod
)

# Operation states
OP_STATUS_RUNNING = 'running'
OP_STATUS_SUCCEEDED = 'succeeded'
OP_STATUS_FAILED = 'failed'


# ============================================================================
# PAYLOAD HASH
# ============================================================================

def compute_payload_hash(payload: Any) -> str:
    """
    Compute SHA-256 hash of request payload for idempotency check.
    
    Uses canonical JSON representation:
    - Keys sorted alphabetically
    - No whitespace
    - UTF-8 encoding
    - Handles non-serializable objects with str() fallback
    
    Args:
        payload: Request data (dict, list, or any JSON-serializable type)
    
    Returns:
        64-character hex SHA-256 hash
    
    Example:
        >>> compute_payload_hash({"ids": [1, 2, 3], "mode": "partial"})
        'a1b2c3d4...'
        >>> compute_payload_hash({"mode": "partial", "ids": [1, 2, 3]})
        'a1b2c3d4...'  # Same hash (keys sorted)
    """
    try:
        # Canonical JSON: sorted keys, compact, UTF-8
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False,
            default=str  # Fallback for non-serializable objects (UUIDs, dates, etc.)
        )
        
        # SHA-256 hash
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    except Exception as e:
        logger.error(
            f"Failed to compute payload hash: {e}",
            extra={'payload_type': type(payload).__name__},
            exc_info=settings.DEBUG
        )
        # Fallback: hash the string representation
        return hashlib.sha256(str(payload).encode('utf-8')).hexdigest()


# ============================================================================
# REDIS KEY BUILDER
# ============================================================================

def _build_redis_key(client_id: int, key: str) -> str:
    """
    Build Redis key for operation state.
    
    Format: crm:idemp:op:{client_id}:{key}
    
    Args:
        client_id: Tenant ID
        key: Operation unique identifier (e.g., Idempotency-Key header)
    
    Returns:
        Full Redis key
    
    Example:
        >>> _build_redis_key(42, "bulk-delete-abc123")
        'crm:idemp:op:42:bulk-delete-abc123'
    """
    return f"crm:idemp:op:{client_id}:{key}"


def _build_lock_key(client_id: int, key: str) -> str:
    """
    Build Redis lock key for distributed locking.
    
    Format: crm:idemp:lock:{client_id}:{key}
    
    Used to prevent race conditions when multiple requests with same
    idempotency key arrive simultaneously.
    
    Args:
        client_id: Tenant ID
        key: Operation unique identifier
    
    Returns:
        Full Redis lock key
    
    Example:
        >>> _build_lock_key(42, "bulk-delete-abc123")
        'crm:idemp:lock:42:bulk-delete-abc123'
    """
    return f"crm:idemp:lock:{client_id}:{key}"


def _acquire_lock(client_id: int, key: str, ttl: int = 5) -> bool:
    """
    Acquire distributed lock using Redis SET NX.
    
    Prevents race condition where two simultaneous requests with same
    idempotency key both try to create the operation.
    
    Args:
        client_id: Tenant ID
        key: Operation unique identifier
        ttl: Lock expiration in seconds (default 5s, short-lived)
    
    Returns:
        True if lock acquired, False if already locked
    
    Example:
        >>> if _acquire_lock(42, "bulk-del-123"):
        ...     # We own the lock, safe to create operation
        ...     create_operation()
        ... else:
        ...     # Another request is handling this, wait and retry
    """
    lock_key = _build_lock_key(client_id, key)
    
    try:
        cache_client = cache.client.get_client()
        
        # SET NX (set if not exists) with expiration
        # Returns True if key was set, False if already exists
        acquired = cache_client.set(lock_key, '1', nx=True, ex=ttl)
        
        if acquired:
            logger.debug(f"Lock acquired: {lock_key}")
        
        return bool(acquired)
    
    except Exception as e:
        logger.warning(
            f"Failed to acquire lock (continuing anyway): {e}",
            extra={'client_id': client_id, 'key': key}
        )
        # Graceful degradation: if lock fails, allow operation
        # (better to have potential duplicate than to block all requests)
        return True


def _release_lock(client_id: int, key: str) -> None:
    """
    Release distributed lock.
    
    Should be called after operation creation or on error.
    
    Args:
        client_id: Tenant ID
        key: Operation unique identifier
    """
    lock_key = _build_lock_key(client_id, key)
    
    try:
        cache_client = cache.client.get_client()
        cache_client.delete(lock_key)
        logger.debug(f"Lock released: {lock_key}")
    
    except Exception as e:
        logger.debug(f"Failed to release lock (non-critical): {e}")
        # Non-critical: lock will expire automatically


# ============================================================================
# REDIS HEALTH CHECK
# ============================================================================

def _check_redis_available() -> bool:
    """
    Check if Redis is healthy and idempotency is enabled.
    
    Handles graceful degradation vs hard fail based on environment:
    - Dev (REQUIRE_REDIS_IDEMPOTENCY=False): Warning + continue without idempotency
    - Prod (REQUIRE_REDIS_IDEMPOTENCY=True): Exception if Redis unavailable
    
    Returns:
        True if Redis healthy, False if unavailable but allowed
    
    Raises:
        Exception: If Redis unavailable and REQUIRE_REDIS_IDEMPOTENCY=True
    """
    if not is_redis_healthy():
        if REQUIRE_REDIS_IDEMPOTENCY:
            # Production: Hard fail
            logger.error(
                "Idempotency store unavailable - Redis required in production",
                extra={'REQUIRE_REDIS_IDEMPOTENCY': True}
            )
            raise Exception(
                "Idempotency service unavailable. "
                "Please try again in a few moments. (Redis connection failed)"
            )
        else:
            # Development: Soft fail with warning
            logger.warning(
                "Redis unavailable - idempotency disabled (dev mode)",
                extra={'REQUIRE_REDIS_IDEMPOTENCY': False}
            )
            return False
    
    return True


# ============================================================================
# OPERATION STATE MANAGEMENT
# ============================================================================

def start_op(
    client_id: int,
    key: str,
    payload_hash: str,
    owner: str,
    ttl: int = DEFAULT_TTL
) -> Optional[Dict[str, Any]]:
    """
    Start a new idempotent operation or return existing state.
    
    Uses distributed lock (SET NX) to prevent race conditions when
    multiple requests with same idempotency key arrive simultaneously.
    
    Behavior:
    - If key doesn't exist → Acquire lock, create with status='running', return None
    - If key exists + same payload_hash → Return existing state (idempotent retry)
    - If key exists + different payload_hash → Raise ValueError (conflict, 409)
    
    Args:
        client_id: Tenant ID
        key: Operation unique identifier (e.g., Idempotency-Key header)
        payload_hash: SHA-256 hash of request payload
        owner: "{client_id}:{user_id}" for audit trail
        ttl: Time-to-live in seconds (default 600s = 10 min)
    
    Returns:
        None if new operation (caller should execute)
        Dict with existing state if operation already running/completed
    
    Raises:
        ValueError: If key exists with different payload (conflict)
    
    Example:
        >>> op = start_op(42, "bulk-del-123", "a1b2c3...", "42:user-uuid")
        >>> if op is None:
        ...     # New operation, execute it
        ...     result = perform_bulk_delete()
        ...     complete_op(42, "bulk-del-123", result)
        >>> elif op['status'] == 'succeeded':
        ...     # Already done, return cached result
        ...     return op['result']
    """
    # Check Redis availability
    if not _check_redis_available():
        # Dev mode without Redis: skip idempotency
        return None
    
    redis_key = _build_redis_key(client_id, key)
    
    try:
        cache_client = cache.client.get_client()
        
        # Check if operation already exists (fast path)
        existing = cache_client.hgetall(redis_key)
        
        if existing:
            # Decode bytes to strings (Redis returns bytes)
            existing_decoded = {
                k.decode('utf-8'): v.decode('utf-8') 
                for k, v in existing.items()
            }
            
            # Check payload hash match (idempotency vs conflict)
            if existing_decoded.get('payload_hash') != payload_hash:
                # Same key, different payload → CONFLICT (409)
                logger.warning(
                    f"Idempotency conflict: key={key}, "
                    f"expected_hash={existing_decoded.get('payload_hash')[:8]}..., "
                    f"got_hash={payload_hash[:8]}...",
                    extra={
                        'client_id': client_id,
                        'key': key,
                        'owner': owner
                    }
                )
                raise ValueError(
                    f"Operation conflict: key '{key}' already exists with different payload. "
                    "Please use a different idempotency key or wait for the current operation to complete."
                )
            
            # Same key, same payload → Return existing state (idempotent)
            logger.info(
                f"Idempotent retry detected: key={key}, status={existing_decoded.get('status')}",
                extra={
                    'client_id': client_id,
                    'key': key,
                    'owner': owner
                }
            )
            
            # Parse result if present
            result = existing_decoded.get('result')
            if result:
                try:
                    existing_decoded['result'] = json.loads(result)
                except json.JSONDecodeError:
                    pass  # Keep as string if not JSON
            
            return existing_decoded
        
        # New operation: Acquire distributed lock to prevent race condition
        lock_acquired = _acquire_lock(client_id, key, ttl=5)
        
        if not lock_acquired:
            # Another request is creating the operation, wait briefly and retry
            logger.debug(f"Lock busy, retrying: key={key}")
            time.sleep(0.1)  # 100ms wait
            
            # Re-check if operation was created by other request
            existing = cache_client.hgetall(redis_key)
            if existing:
                existing_decoded = {
                    k.decode('utf-8'): v.decode('utf-8')
                    for k, v in existing.items()
                }
                
                # Verify payload hash
                if existing_decoded.get('payload_hash') != payload_hash:
                    raise ValueError(
                        f"Operation conflict: key '{key}' already exists with different payload."
                    )
                
                logger.info(f"Operation created by concurrent request: key={key}")
                
                # Parse result
                result = existing_decoded.get('result')
                if result:
                    try:
                        existing_decoded['result'] = json.loads(result)
                    except json.JSONDecodeError:
                        pass
                
                return existing_decoded
            else:
                # Still doesn't exist, proceed to create (lock may have expired)
                pass
        
        try:
            # Create new operation with status='running'
            now_iso = datetime.now(timezone.utc).isoformat()
            
            op_data = {
                'status': OP_STATUS_RUNNING,
                'payload_hash': payload_hash,
                'owner': owner,
                'started_at': now_iso,
                'result': '',
                'error': ''
            }
            
            # Store in Redis with TTL
            cache_client.hset(redis_key, mapping=op_data)
            cache_client.expire(redis_key, ttl)
            
            logger.info(
                f"Started new operation: key={key}",
                extra={
                    'client_id': client_id,
                    'key': key,
                    'owner': owner,
                    'ttl': ttl
                }
            )
            
            return None  # Caller should execute the operation
        
        finally:
            # Always release lock after creation (or failure)
            _release_lock(client_id, key)
    
    except ValueError:
        # Conflict (409) - re-raise
        raise
    
    except Exception as e:
        logger.error(
            f"Failed to start operation: {e}",
            extra={
                'client_id': client_id,
                'key': key,
                'owner': owner
            },
            exc_info=settings.DEBUG
        )
        
        # Graceful degradation: allow operation to proceed
        if not REQUIRE_REDIS_IDEMPOTENCY:
            return None
        else:
            raise


def get_op(client_id: int, key: str) -> Optional[Dict[str, Any]]:
    """
    Get current state of an operation (for polling).
    
    Used by GET /ops/{key} endpoint to check operation status.
    
    Args:
        client_id: Tenant ID
        key: Operation unique identifier
    
    Returns:
        Dict with operation state, or None if not found
        {
            'status': 'running' | 'succeeded' | 'failed',
            'payload_hash': 'a1b2c3...',
            'owner': '42:user-uuid',
            'started_at': '2025-10-24T12:34:56.789Z',
            'completed_at': '2025-10-24T12:35:01.234Z',  # If completed
            'result': {...},  # If succeeded
            'error': 'Error message'  # If failed
        }
    
    Example:
        >>> op = get_op(42, "bulk-del-123")
        >>> if op['status'] == 'running':
        ...     return {'status': 'processing', 'progress': '50%'}
        >>> elif op['status'] == 'succeeded':
        ...     return op['result']
    """
    # Check Redis availability
    if not _check_redis_available():
        return None
    
    redis_key = _build_redis_key(client_id, key)
    
    try:
        cache_client = cache.client.get_client()
        op_data = cache_client.hgetall(redis_key)
        
        if not op_data:
            return None
        
        # Decode bytes to strings
        op_decoded = {
            k.decode('utf-8'): v.decode('utf-8')
            for k, v in op_data.items()
        }
        
        # Parse result if present
        result = op_decoded.get('result')
        if result:
            try:
                op_decoded['result'] = json.loads(result)
            except json.JSONDecodeError:
                pass  # Keep as string if not JSON
        
        return op_decoded
    
    except Exception as e:
        logger.error(
            f"Failed to get operation: {e}",
            extra={'client_id': client_id, 'key': key},
            exc_info=settings.DEBUG
        )
        return None


def complete_op(
    client_id: int,
    key: str,
    result: Any,
    ttl: int = DEFAULT_TTL
) -> bool:
    """
    Mark operation as successfully completed.
    
    Updates status to 'succeeded' and stores result for future idempotent retries.
    
    Args:
        client_id: Tenant ID
        key: Operation unique identifier
        result: Operation result (will be JSON-serialized)
        ttl: Extended TTL for completed operations (default 600s)
    
    Returns:
        True if updated successfully, False otherwise
    
    Example:
        >>> result = {'deleted': 42, 'failed': 0}
        >>> complete_op(42, "bulk-del-123", result)
        True
    """
    # Check Redis availability
    if not _check_redis_available():
        return False
    
    redis_key = _build_redis_key(client_id, key)
    now_iso = datetime.now(timezone.utc).isoformat()
    
    try:
        cache_client = cache.client.get_client()
        
        # Serialize result to JSON
        result_json = json.dumps(result, default=str)
        
        # Update operation state
        cache_client.hset(
            redis_key,
            mapping={
                'status': OP_STATUS_SUCCEEDED,
                'result': result_json,
                'completed_at': now_iso
            }
        )
        
        # Refresh TTL
        cache_client.expire(redis_key, ttl)
        
        logger.info(
            f"Operation completed: key={key}",
            extra={'client_id': client_id, 'key': key}
        )
        
        return True
    
    except Exception as e:
        logger.error(
            f"Failed to complete operation: {e}",
            extra={'client_id': client_id, 'key': key},
            exc_info=settings.DEBUG
        )
        return False


def fail_op(
    client_id: int,
    key: str,
    error: str,
    ttl: int = DEFAULT_TTL
) -> bool:
    """
    Mark operation as failed.
    
    Updates status to 'failed' and stores error message.
    
    Args:
        client_id: Tenant ID
        key: Operation unique identifier
        error: Error message or exception string
        ttl: TTL for failed operations (default 600s)
    
    Returns:
        True if updated successfully, False otherwise
    
    Example:
        >>> try:
        ...     result = perform_bulk_delete()
        ... except Exception as e:
        ...     fail_op(42, "bulk-del-123", str(e))
        ...     raise
    """
    # Check Redis availability
    if not _check_redis_available():
        return False
    
    redis_key = _build_redis_key(client_id, key)
    now_iso = datetime.now(timezone.utc).isoformat()
    
    try:
        cache_client = cache.client.get_client()
        
        # Update operation state
        cache_client.hset(
            redis_key,
            mapping={
                'status': OP_STATUS_FAILED,
                'error': str(error),
                'completed_at': now_iso
            }
        )
        
        # Refresh TTL
        cache_client.expire(redis_key, ttl)
        
        logger.warning(
            f"Operation failed: key={key}, error={error}",
            extra={'client_id': client_id, 'key': key}
        )
        
        return True
    
    except Exception as e:
        logger.error(
            f"Failed to mark operation as failed: {e}",
            extra={'client_id': client_id, 'key': key},
            exc_info=settings.DEBUG
        )
        return False


# ============================================================================
# HELPER: EXTRACT OWNER FROM REQUEST
# ============================================================================

# Public endpoints that should skip idempotency (no tenant context)
PUBLIC_ENDPOINTS = {
    '/client/login/',
    '/client/logout/',
    '/client/refresh-token/',
    '/product_admin/login/',
    '/product_admin/register/',
    '/healthz/',
}


def is_public_endpoint(request) -> bool:
    """
    Check if request is to a public endpoint (auth, health checks, etc.).
    
    Public endpoints should skip idempotency checks as they:
    - Don't have tenant context
    - Are typically idempotent by design (POST /login with same credentials → same result)
    - May be called before authentication
    
    Args:
        request: Django HttpRequest
    
    Returns:
        True if endpoint is public, False if tenant-scoped
    
    Example:
        >>> is_public_endpoint(request)  # POST /client/login/
        True
        >>> is_public_endpoint(request)  # DELETE /client/users/bulk-delete/
        False
    """
    path = request.path
    
    # Exact match
    if path in PUBLIC_ENDPOINTS:
        return True
    
    # Prefix match for health checks, static files, admin
    public_prefixes = ('/healthz', '/static/', '/admin/', '/media/')
    if any(path.startswith(prefix) for prefix in public_prefixes):
        return True
    
    return False


def get_owner_from_request(request, strict: bool = None) -> str:
    """
    Extract owner string from Django request with strict tenant validation.
    
    Format: "{client_id}:{user_id}"
    
    Behavior:
    - Public endpoints: Returns "public:anonymous" (no error)
    - Authenticated tenant-scoped: Returns "{client_id}:{user_id}"
    - Missing tenant in prod (strict=True): Raises ValueError → 400/403
    - Missing tenant in dev (strict=False): Returns "unknown:anonymous" + warning
    
    Args:
        request: Django HttpRequest with authenticated user
        strict: If True, raise exception on missing tenant (default: based on REQUIRE_REDIS_IDEMPOTENCY)
    
    Returns:
        Owner string for audit trail
    
    Raises:
        ValueError: If tenant missing and strict mode enabled
    
    Example:
        >>> owner = get_owner_from_request(request)
        >>> # "42:6d3f4a5b-7c8d-9e0f-1a2b-3c4d5e6f7a8b"
        
        >>> owner = get_owner_from_request(public_request)
        >>> # "public:anonymous"
        
        >>> owner = get_owner_from_request(missing_tenant_request, strict=True)
        >>> # ValueError: "Tenant context required for this operation"
    """
    # Default: strict mode follows REQUIRE_REDIS_IDEMPOTENCY setting
    if strict is None:
        strict = REQUIRE_REDIS_IDEMPOTENCY
    
    # Public endpoints: Allow without tenant
    if is_public_endpoint(request):
        return "public:anonymous"
    
    # Extract client_id (tenant)
    # Try multiple sources for compatibility with different middleware setups
    client_id = None
    
    # 1. Request attribute (set by custom middleware)
    if hasattr(request, 'client_id'):
        client_id = request.client_id
    
    # 2. User attribute (for authenticated users)
    elif hasattr(request, 'user') and hasattr(request.user, 'client_account_id'):
        client_id = request.user.client_account_id
    
    # 3. Headers (X-Client-ID, used by some APIs)
    elif 'HTTP_X_CLIENT_ID' in request.META:
        try:
            client_id = int(request.META['HTTP_X_CLIENT_ID'])
        except (ValueError, TypeError):
            pass
    
    # Extract user_id
    user_id = 'anonymous'
    if hasattr(request, 'user') and request.user and request.user.is_authenticated:
        user_id = str(request.user.id)
    
    # Validate tenant presence for tenant-scoped endpoints
    if not client_id:
        error_msg = (
            "Tenant context required for this operation. "
            "Please ensure you are authenticated and your request includes tenant information."
        )
        
        if strict:
            # Production: Hard fail
            logger.error(
                f"Missing tenant context for {request.method} {request.path}",
                extra={
                    'user_id': user_id,
                    'user_authenticated': hasattr(request, 'user') and request.user.is_authenticated,
                    'strict_mode': True
                }
            )
            raise ValueError(error_msg)
        else:
            # Development: Soft fail with warning
            logger.warning(
                f"Missing tenant context for {request.method} {request.path} (dev mode)",
                extra={
                    'user_id': user_id,
                    'strict_mode': False
                }
            )
            client_id = 'unknown'
    
    return f"{client_id}:{user_id}"