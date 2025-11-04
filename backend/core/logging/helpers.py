# backend/core/logging/helpers.py

"""
Logging Helpers - PII-Safe Context Extraction

This module provides utility functions to extract safe logging context
from User objects and user data dictionaries WITHOUT exposing PII.

Key Principle: ONLY log UUIDs and role flags, NEVER email or names.

Compliance: SOC I Type II, GDPR, CCPA

Usage:
    from core.logging.helpers import safe_user_context, safe_user_data_context
    
    # With User instance
    logger.info("User updated", extra=safe_user_context(user))
    
    # With user_data dict (bulk operations)
    logger.info("Creating user", extra=safe_user_data_context(user_data))
"""

from typing import Dict, Any, Optional

# Lazy import to avoid circular dependencies
def _get_user_model():
    """Lazy import of User model to prevent circular imports."""
    from django.contrib.auth import get_user_model
    return get_user_model()


def safe_user_context(user: Optional[Any]) -> Dict[str, Any]:
    """
    Extract safe logging context from User instance.
    
    Returns ONLY non-PII fields: UUID, role flags, status flags.
    NEVER returns: email, first_name, last_name, or any PII.
    
    This function is SOC I compliant and GDPR compliant for logging purposes.
    
    Args:
        user: User instance or None
        
    Returns:
        dict: Safe context with user_id and flags, no PII
        
    Examples:
        >>> user = User.objects.get(email='john@example.com')
        >>> safe_user_context(user)
        {
            'user_id': 'abc-123-def-456',
            'is_active': True,
            'is_superuser': False,
            'role_name': 'Admin'
        }
        
        >>> safe_user_context(None)
        {'user_id': None}
    
    Security Note:
        - UUID is NOT PII (cannot identify person without database access)
        - Role flags are NOT PII (organizational metadata)
        - This context is safe to log in CloudWatch, Elasticsearch, etc.
    """
    if user is None:
        return {'user_id': None}
    
    # Extract safe fields only
    context = {
        'user_id': str(user.id),
        'is_active': getattr(user, 'is_active', None),
        'is_superuser': getattr(user, 'is_superuser', None),
    }
    
    # Add role_name if available (denormalized field, safe to log)
    if hasattr(user, 'role_name'):
        context['role_name'] = user.role_name
    elif hasattr(user, 'role') and user.role:
        # Fallback to role.name if role_name not denormalized
        context['role_name'] = getattr(user.role, 'name', None)
    else:
        context['role_name'] = None
    
    # CRITICAL: NO email, NO names, NO PII
    # The following fields are FORBIDDEN in logs:
    # - user.email
    # - user.first_name
    # - user.last_name
    # - user.get_full_name()
    # - user.phone_number
    # - Any other personal data
    
    return context


def safe_user_data_context(user_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract safe logging context from user data dictionary.
    
    Used in bulk operations where User instance doesn't exist yet,
    but we have a user_data dict from request payload.
    
    Returns ONLY the user ID (if present), NEVER email or names.
    
    Args:
        user_data: Dictionary containing user data (e.g., from bulk create)
        
    Returns:
        dict: Safe context with user_id only (or 'pending' if not created yet)
        
    Examples:
        >>> user_data = {
        ...     'email': 'test@example.com',
        ...     'first_name': 'John',
        ...     'id': 'abc-123-def-456'
        ... }
        >>> safe_user_data_context(user_data)
        {'user_id': 'abc-123-def-456'}
        
        >>> user_data = {'email': 'test@example.com'}  # No ID yet (pre-creation)
        >>> safe_user_data_context(user_data)
        {'user_id': 'pending'}
        
        >>> safe_user_data_context(None)
        {'user_id': None}
        
        >>> safe_user_data_context({})
        {'user_id': 'pending'}
    
    Security Note:
        - Only extracts 'id' field from dict
        - Ignores all PII fields (email, names, phone, etc.)
        - Safe for logging in all environments
    """
    # ✅ FIX: Explicit check for None only (not falsy values like {})
    if user_data is None:
        return {'user_id': None}
    
    # Extract only the ID field
    user_id = user_data.get('id')
    
    if user_id:
        return {'user_id': str(user_id)}
    else:
        # User not created yet (bulk create pre-validation)
        # This includes empty dict {} - which should return 'pending'
        return {'user_id': 'pending'}


def safe_batch_context(users_data: Optional[list]) -> Dict[str, Any]:
    """
    Extract safe logging context for batch/bulk operations.
    
    Returns aggregate stats about the batch WITHOUT individual PII.
    Useful for logging bulk operations like "Processing 50 users".
    
    Args:
        users_data: List of user dicts or User instances
        
    Returns:
        dict: Safe aggregate context (count, first/last IDs)
        
    Examples:
        >>> users_data = [
        ...     {'id': 'id-1', 'email': 'a@test.com'},
        ...     {'id': 'id-2', 'email': 'b@test.com'},
        ...     {'id': 'id-3', 'email': 'c@test.com'}
        ... ]
        >>> safe_batch_context(users_data)
        {
            'batch_size': 3,
            'first_user_id': 'id-1',
            'last_user_id': 'id-3'
        }
        
        >>> safe_batch_context([])
        {'batch_size': 0, 'first_user_id': None, 'last_user_id': None}
    
    Security Note:
        - Provides aggregate stats only
        - No individual PII exposed
        - UUIDs are safe (not PII)
    """
    if not users_data:
        return {
            'batch_size': 0,
            'first_user_id': None,
            'last_user_id': None
        }
    
    batch_size = len(users_data)
    
    # Extract first and last IDs (for debugging batch boundaries)
    first_item = users_data[0]
    last_item = users_data[-1]
    
    # Handle both dict and object types
    if isinstance(first_item, dict):
        first_id = first_item.get('id', 'unknown')
        last_id = last_item.get('id', 'unknown')
    else:
        # Assume it's a User instance
        first_id = str(getattr(first_item, 'id', 'unknown'))
        last_id = str(getattr(last_item, 'id', 'unknown'))
    
    return {
        'batch_size': batch_size,
        'first_user_id': str(first_id),
        'last_user_id': str(last_id)
    }


# ============================================================================
# USAGE EXAMPLES (for documentation)
# ============================================================================

"""
CORRECT USAGE EXAMPLES:

✅ GOOD - Using helper for User instance:
    user = User.objects.get(id=user_id)
    logger.info("User logged in", extra=safe_user_context(user))
    # Log output: user_id=abc-123-def-456 is_active=true role_name=Admin

✅ GOOD - Using helper for user_data dict:
    user_data = request.data.get('user')
    logger.info("Creating user", extra=safe_user_data_context(user_data))
    # Log output: user_id=pending (or actual UUID if already created)

✅ GOOD - Using helper for batch operations:
    users_list = [...]
    logger.info("Processing batch", extra=safe_batch_context(users_list))
    # Log output: batch_size=50 first_user_id=id-1 last_user_id=id-50

✅ GOOD - Combining with other context:
    ctx = {
        'event': 'user_updated',
        'client_id': str(client.id),
        **safe_user_context(user)  # Spread operator
    }
    logger.info("User updated fields", extra=ctx)

❌ BAD - Logging email directly:
    logger.info(f"User {user.email} updated")  # ❌ PII LEAK

❌ BAD - Logging names:
    logger.info(f"User {user.get_full_name()} created")  # ❌ PII LEAK

❌ BAD - PII in extra dict:
    logger.info("User created", extra={'email': user.email})  # ❌ PII LEAK

❌ BAD - PII in f-string:
    logger.warning(f"Invalid email: {user.email}")  # ❌ PII LEAK
"""


# ============================================================================
# VALIDATION CHECKS (optional runtime assertions)
# ============================================================================

def _validate_context_no_pii(context: Dict[str, Any]) -> None:
    """
    Optional validation to ensure context dict contains no PII.
    
    Can be enabled in development/staging to catch PII leaks early.
    
    Raises:
        AssertionError: If PII fields detected in context
    """
    forbidden_keys = {
        'email', 'e_mail', 'user_email',
        'first_name', 'firstname', 'fname',
        'last_name', 'lastname', 'lname',
        'full_name', 'fullname', 'name',
        'phone', 'phone_number', 'mobile',
        'address', 'street', 'city', 'zip',
        'ssn', 'social_security',
    }
    
    for key in context.keys():
        key_lower = key.lower()
        assert key_lower not in forbidden_keys, (
            f"PII field detected in logging context: '{key}'. "
            f"Use safe_user_context() to extract only UUIDs."
        )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'safe_user_context',
    'safe_user_data_context',
    'safe_batch_context',
]