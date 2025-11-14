# backend/core/logging/audit.py

"""
SOC 2 compliant audit logging helper.

Provides standardized audit logging for security-sensitive operations
like user/role CRUD, permission changes, and bulk operations.

Usage:
    from core.audit import audit_log
    
    audit_log(
        event='user_create_success',
        action='create',
        actor_id=str(request.user.id),
        client_id=str(client_id),
        target_type='user',
        target_id=str(user.id),
        outcome='success',
    )
"""

import logging
from typing import Optional, Dict, Any

from core.logging.context import get_correlation_id

audit_logger = logging.getLogger("audit")


def audit_log(
    *,
    event: str,
    action: str,
    actor_id: Optional[str],
    client_id: Optional[str],
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    target_count: Optional[int] = None,
    fields_changed: Optional[list[str]] = None,
    outcome: str = "success",
    reason: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log SOC 2 compliant audit event.
    
    Args:
        event: Event identifier (e.g., 'user_create_success', 'role_delete_failed')
        action: Action performed (create, read, update, delete, bulk_create, etc.)
        actor_id: UUID of user performing the action (PII-safe)
        client_id: UUID of tenant (PII-safe)
        target_type: Type of object affected (user, role, etc.)
        target_id: UUID of object affected (PII-safe)
        target_count: Number of objects affected (for bulk operations)
        fields_changed: List of field names modified (for updates)
        outcome: Result of operation (success, failure, not_found, started)
        reason: Optional reason for failure
        extra: Additional context (PII-safe only)
    
    Example:
        # Single object creation
        audit_log(
            event='role_create_success',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='role',
            target_id=str(role.id),
            outcome='success',
            extra={'role_name': role.name}
        )
        
        # Bulk operation
        audit_log(
            event='bulk_create_users',
            action='bulk_create',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='user',
            target_count=50,
            outcome='success',
            extra={'created': 48, 'failed': 2}
        )
        
        # Update with fields tracking
        audit_log(
            event='user_update_success',
            action='partial_update',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='user',
            target_id=str(user.id),
            fields_changed=['email', 'role_id'],
            outcome='success',
        )
    """
    ctx: Dict[str, Any] = extra.copy() if extra else {}

    ctx.update({
        "event": event,
        "action": action,
        "actor_id": actor_id or "-",
        "client_id": client_id or "-",
        "target_type": target_type or "-",
        "target_id": target_id or "-",
        "target_count": target_count if target_count is not None else "-",
        "fields_changed": ",".join(fields_changed) if fields_changed else "-",
        "outcome": outcome,
        "reason": reason or "-",
        "correlation_id": get_correlation_id(),
    })

    audit_logger.info(event, extra=ctx)