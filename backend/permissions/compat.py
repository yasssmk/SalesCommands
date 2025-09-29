"""
JWT → Permissions Context Adapter

This module provides compatibility between CustomJWTAuthentication 
and the permissions system without modifying JWT code.

The adapter extracts a standardized context from JWT claims for use
by the permission system. No database queries are performed.

IMPORTANT: No tier inference based on role names. Tier is kept for 
legacy UI compatibility only, not for permission decisions.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from django.contrib.auth.models import AnonymousUser
import logging

logger = logging.getLogger(__name__)

# P2-T5: Module-level flag to track initialization logging
_boot_logged = False
_using_dummy = False  # Track if we're in dummy mode


@dataclass
class AuthContext:
    """
    Standardized authentication context for permissions.
    
    This is a read-only container that provides a consistent interface
    regardless of the authentication source. No inference or DB queries.
    """
    # Core identity
    origin: str = 'unknown'
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    
    # Roles information (NO TIER INFERENCE)
    roles: List[Dict[str, Any]] = field(default_factory=list)  # List of role objects/dicts
    tier: str = 'individual'  # LEGACY UI ONLY - not for decisions
    
    # Team information
    teams: List[str] = field(default_factory=list)
    team_id: Optional[str] = None  # Primary team if exists
    
    # Flags
    is_superuser: bool = False
    is_impersonating: bool = False
    is_authenticated: bool = False
    
    # JWT standard claims (if available)
    iss: Optional[str] = None  # Issuer
    aud: Optional[str] = None  # Audience
    exp: Optional[int] = None  # Expiration
    nbf: Optional[int] = None  # Not before
    iat: Optional[int] = None  # Issued at
    jti: Optional[str] = None  # JWT ID
    
    def __repr__(self):
        return f"AuthContext(origin={self.origin}, user_id={self.user_id}, client_id={self.client_id}, roles={len(self.roles)})"


def _log_boot_once():
    """
    P2-T5: Log initialization status exactly once at module load.
    
    This helps diagnose whether the permissions system is properly configured
    without spamming logs on every request.
    """
    global _boot_logged, _using_dummy
    
    if _boot_logged:
        return
    
    _boot_logged = True
    
    # Determine what mode we're in
    mode = "DummyContext (fallback)" if _using_dummy else "AuthContext (normal)"
    message = f"permissions.compat initialized: mode={mode}"
    
    # Log at INFO level so it's visible in production logs
    logger.info(message)
    
    # Also log to console in DEBUG mode for immediate visibility
    try:
        from django.conf import settings
        if settings.DEBUG:
            import sys
            print(f"[PERMISSIONS] {message}", file=sys.stderr)
    except:
        pass  # Fail silently if settings not available


def get_auth_ctx(request) -> AuthContext:
    """
    Extract standardized auth context from request WITHOUT database queries.
    
    Priority order:
    1. request.auth.payload (JWT validated by authentication)
    2. request.user attributes (fallback)
    3. Default values (anonymous)
    
    Args:
        request: Django/DRF request object
        
    Returns:
        AuthContext: Standardized context for permission checks
        
    Note:
        This function does NOT perform any database queries or role inference.
        It only extracts and normalizes data already present in the request.
    """
    # P2-T5: Log initialization on first call
    _log_boot_once()
    
    ctx = AuthContext()
    
    # Check if user is authenticated
    if not hasattr(request, 'user') or isinstance(request.user, AnonymousUser):
        if settings.DEBUG:
            logger.debug("[COMPAT] Anonymous user - returning empty context")
        return ctx
    
    user = request.user
    ctx.is_authenticated = user.is_authenticated if hasattr(user, 'is_authenticated') else False
    
    if not ctx.is_authenticated:
        if settings.DEBUG:
            logger.debug("[COMPAT] User not authenticated - returning minimal context")
        return ctx
    
    # PRIORITÉ 1 : Extraire depuis request.auth (validated_token de JWT)
    if hasattr(request, 'auth') and request.auth:
        # request.auth est un Token object, on veut son payload
        if hasattr(request.auth, 'payload'):
            auth_dict = request.auth.payload
        elif hasattr(request.auth, '__getitem__'):
            auth_dict = dict(request.auth)
        else:
            auth_dict = {}
        
        if auth_dict:
            if settings.DEBUG:
                logger.debug(f"[COMPAT] Found JWT auth dict with keys: {list(auth_dict.keys())}")
            
            # Core fields
            ctx.origin = auth_dict.get('origin', 'end_users')
            ctx.user_id = str(auth_dict.get('user_id')) if auth_dict.get('user_id') else None
            ctx.client_id = str(auth_dict.get('client_account')) if auth_dict.get('client_account') else None
            
            
            # Extract role WITH flags
            if 'role' in auth_dict:
                role = auth_dict.get('role')
                if settings.DEBUG:
                    logger.debug(f"[COMPAT] Role in JWT: type={type(role)}, value={role}")
                if isinstance(role, dict):
                    # Nouveau format avec flags
                    ctx.roles = [{
                        'id': str(role.get('id')) if role.get('id') else None,
                        'name': role.get('name'),
                        'is_admin': role.get('is_admin', False),
                        'is_manager': role.get('is_manager', False),
                        'is_individual': role.get('is_individual', False),
                    }]
                    if settings.DEBUG:
                        logger.debug(f"[COMPAT] Extracted role with flags: {role.get('name')} "
                              f"(admin={role.get('is_admin')}, manager={role.get('is_manager')}, "
                              f"individual={role.get('is_individual')})")
                else:
                    # Ancien format sans flags
                    if settings.DEBUG:
                        logger.debug("[COMPAT] WARNING: Old JWT format without role flags")
                    ctx.roles = []
            
            # Teams
            if 'teams' in auth_dict:
                ctx.teams = auth_dict.get('teams', [])
            elif 'team_id' in auth_dict:
                ctx.team_id = str(auth_dict.get('team_id'))
                ctx.teams = [ctx.team_id] if ctx.team_id else []
            
            # Flags
            ctx.is_superuser = auth_dict.get('is_superuser', False)
            ctx.is_impersonating = auth_dict.get('is_impersonating', False)
            
            # JWT standard claims
            ctx.iss = auth_dict.get('iss')
            ctx.aud = auth_dict.get('aud')
            ctx.exp = auth_dict.get('exp')
            ctx.nbf = auth_dict.get('nbf')
            ctx.iat = auth_dict.get('iat')
            ctx.jti = auth_dict.get('jti')
    else:
        # PRIORITÉ 2 : Fallback sur user object
        if settings.DEBUG:
            logger.debug("[COMPAT] No JWT auth, using user object (LIMITED)")
        
        ctx.user_id = str(user.id) if hasattr(user, 'id') else None
        ctx.is_superuser = getattr(user, 'is_superuser', False)
        
        if hasattr(user, 'client_account_id'):
            ctx.client_id = str(user.client_account_id)
        
        # Extraire le rôle depuis l'objet user SI disponible avec flags
        if hasattr(user, 'role') and user.role:
            role = user.role
            if hasattr(role, 'is_admin'):
                # Le rôle a les flags
                ctx.roles = [{
                    'id': str(role.id) if hasattr(role, 'id') else None,
                    'name': getattr(role, 'name', 'Unknown'),
                    'is_admin': getattr(role, 'is_admin', False),
                    'is_manager': getattr(role, 'is_manager', False),
                    'is_individual': getattr(role, 'is_individual', False),
                }]
                if settings.DEBUG:
                    logger.debug(f"[COMPAT] Extracted role flags from user object: {role.name} "
                          f"(admin={role.is_admin}, manager={role.is_manager}, "
                          f"individual={role.is_individual})")
            else:
                if settings.DEBUG:
                    logger.debug("[COMPAT] Role on user object but no flags")
                ctx.roles = []
    
    # Set origin if not set
    if not ctx.origin or ctx.origin == 'unknown':
        ctx.origin = 'end_users'
    
    if settings.DEBUG:
        logger.debug(f"[COMPAT] Final context: user_id={ctx.user_id}, client_id={ctx.client_id}, "
              f"roles={len(ctx.roles)}, teams={len(ctx.teams)}, origin={ctx.origin}")
    
    return ctx


def get_client_id(request) -> Optional[str]:
    """
    Quick helper to extract client_id from request.
    
    Args:
        request: Django/DRF request
        
    Returns:
        Client ID string or None
    """
    ctx = get_auth_ctx(request)
    return ctx.client_id


def is_admin(request) -> bool:
    """
    DEPRECATED - Use role flags directly via get_auth_ctx().
    
    This checks tier which is legacy. Use ctx.roles[].is_admin instead.
    """
    logger.warning("[COMPAT] WARNING: is_admin() is deprecated, use role flags from get_auth_ctx()")
    ctx = get_auth_ctx(request)
    # Check if any role has is_admin flag
    for role in ctx.roles:
        if isinstance(role, dict) and role.get('is_admin'):
            return True
    return ctx.is_superuser


def is_manager(request) -> bool:
    """
    DEPRECATED - Use role flags directly via get_auth_ctx().
    
    This checks tier which is legacy. Use ctx.roles[].is_manager instead.
    """
    logger.warning("[COMPAT] WARNING: is_manager() is deprecated, use role flags from get_auth_ctx()")
    ctx = get_auth_ctx(request)
    # Check if any role has is_manager flag
    for role in ctx.roles:
        if isinstance(role, dict) and role.get('is_manager'):
            return True
    return False


def is_end_users_origin(request) -> bool:
    """
    Check if request originates from end_users (vs product_admin).
    
    Args:
        request: Django/DRF request
        
    Returns:
        True if origin is 'end_users'
    """
    ctx = get_auth_ctx(request)
    return ctx.origin == 'end_users'


def debug_auth_context(request) -> Dict[str, Any]:
    """
    Get a debug-friendly representation of the auth context.
    
    Useful for logging and troubleshooting permission issues.
    
    Args:
        request: Django/DRF request
        
    Returns:
        Dictionary with all context information
    """
    ctx = get_auth_ctx(request)
    return {
        'origin': ctx.origin,
        'user_id': ctx.user_id,
        'client_id': ctx.client_id,
        'tier': ctx.tier,  # LEGACY - UI only
        'roles': ctx.roles,
        'team_id': ctx.team_id,
        'teams': ctx.teams,
        'is_superuser': ctx.is_superuser,
        'is_impersonating': ctx.is_impersonating,
        'is_authenticated': ctx.is_authenticated,
        'jwt_claims': {
            'iss': ctx.iss,
            'aud': ctx.aud,
            'exp': ctx.exp,
            'nbf': ctx.nbf,
            'iat': ctx.iat,
            'jti': ctx.jti,
        }
    }


# P2-T5: Check if we're using settings (normal) or dummy mode
# This is set at module load time
try:
    from django.conf import settings
    _using_dummy = False
except ImportError:
    logger.warning("Django settings not available - permissions.compat may not work correctly")
    _using_dummy = True

# P2-T5: Log initialization status at module load
_log_boot_once()