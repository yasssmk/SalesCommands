"""
JWT → Permissions Context Adapter

This module provides compatibility between CustomJWTAuthentication 
and the permissions system without modifying JWT code.

The adapter extracts a standardized context from JWT claims for use
by the permission system. No database queries are performed.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from django.contrib.auth.models import AnonymousUser
import logging

logger = logging.getLogger(__name__)


@dataclass
class AuthContext:
    """
    Standardized authentication context for permissions.
    
    This is a read-only container that provides a consistent interface
    regardless of the authentication source.
    """
    # Core identity
    origin: str = 'unknown'
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    
    # Role/tier information
    tier: str = 'individual'  # admin|manager|individual
    role_id: Optional[str] = None
    role_name: Optional[str] = None
    
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
        return f"AuthContext(origin={self.origin}, user_id={self.user_id}, tier={self.tier}, client_id={self.client_id})"


def get_auth_ctx(request) -> AuthContext:
    """
    Extract standardized auth context from request.
    
    This function provides a consistent authentication context regardless
    of whether we're using the old or new JWT system.
    
    Args:
        request: Django/DRF request object
        
    Returns:
        AuthContext with extracted information
        
    Note:
        No database queries are performed. All information comes from
        the JWT claims or request.user attributes already in memory.
    """
    # If a pre-built context exists, use it
    if hasattr(request, 'auth_ctx') and isinstance(request.auth_ctx, AuthContext):
        return request.auth_ctx
    
    # Build context from available information
    ctx = AuthContext()
    
    # Check if user is authenticated
    if hasattr(request, 'user') and request.user and not isinstance(request.user, AnonymousUser):
        ctx.is_authenticated = True
        user = request.user
        
        # Extract user ID
        if hasattr(user, 'id'):
            ctx.user_id = str(user.id)
        
        # Extract superuser flag
        if hasattr(user, 'is_superuser'):
            ctx.is_superuser = bool(user.is_superuser)
    
    # Extract JWT claims from request.auth (populated by CustomJWTAuthentication)
    if hasattr(request, 'auth') and request.auth:
        auth_data = request.auth
        
        # Origin (end_users or product_admin)
        ctx.origin = auth_data.get('origin', 'unknown')
        
        # Client/tenant ID (critical for multi-tenant isolation)
        ctx.client_id = auth_data.get('client_account') or auth_data.get('client_id')
        
        # User ID fallback from JWT
        if not ctx.user_id:
            ctx.user_id = auth_data.get('user_id')
        
        # Role information
        ctx.role_id = auth_data.get('role_id') or auth_data.get('role')
        ctx.role_name = auth_data.get('role_name')
        
        # Team information
        ctx.team_id = auth_data.get('team_id') or auth_data.get('team')
        if auth_data.get('teams'):
            ctx.teams = [str(t) for t in auth_data.get('teams', [])]
        elif ctx.team_id:
            ctx.teams = [str(ctx.team_id)]
        
        # Standard JWT claims
        ctx.iss = auth_data.get('iss')
        ctx.aud = auth_data.get('aud')
        ctx.exp = auth_data.get('exp')
        ctx.nbf = auth_data.get('nbf')
        ctx.iat = auth_data.get('iat')
        ctx.jti = auth_data.get('jti')
        
        # Impersonation flag
        ctx.is_impersonating = bool(auth_data.get('is_impersonating', False))
    
    # Derive tier from role or user attributes
    ctx.tier = resolve_tier_from_context(ctx, request.user if hasattr(request, 'user') else None)
    
    return ctx


# def resolve_tier_from_context(ctx: AuthContext, user=None) -> str:
#     """
#     Resolve the permission tier from available context.
    
#     Priority order:
#     1. Superuser → 'admin'
#     2. Role name contains 'admin' → 'admin'
#     3. Role name contains 'manager' → 'manager'
#     4. Role with is_admin flag → 'admin'
#     5. User.role.tier if available
#     6. Default → 'individual'
    
#     Args:
#         ctx: AuthContext with partial information
#         user: Django user object (optional)
        
#     Returns:
#         Tier string: 'admin' | 'manager' | 'individual'
#     """
#     # Superuser is always admin
#     if ctx.is_superuser:
#         return 'admin'
    
#     # Check role name (case-insensitive)
#     if ctx.role_name:
#         role_lower = ctx.role_name.lower()
#         if 'admin' in role_lower:
#             return 'admin'
#         elif 'manager' in role_lower:
#             return 'manager'
    
#     # Check user.role attributes if available
#     if user and hasattr(user, 'role'):
#         role = user.role
#         if role:
#             # Check is_admin flag
#             if hasattr(role, 'is_admin') and role.is_admin:
#                 return 'admin'
            
#             # Check tier attribute
#             if hasattr(role, 'tier'):
#                 return role.tier
            
#             # Check role name from object
#             if hasattr(role, 'name'):
#                 role_name_lower = role.name.lower()
#                 if 'admin' in role_name_lower:
#                     return 'admin'
#                 elif 'manager' in role_name_lower:
#                     return 'manager'
    
#     # Default to individual (least privilege)
#     return 'individual'
def resolve_tier_from_context(ctx: AuthContext, user=None) -> str:
    """
    Resolve the permission tier from available context.
    """
    print(f"[COMPAT DEBUG] Resolving tier...")
    print(f"[COMPAT DEBUG]   ctx.is_superuser: {ctx.is_superuser}")
    print(f"[COMPAT DEBUG]   ctx.role_name: {ctx.role_name}")
    
    # Superuser is always admin
    if ctx.is_superuser:
        print(f"[COMPAT DEBUG]   -> Tier: admin (superuser)")
        return 'admin'
    
    # Check role name (case-insensitive)
    if ctx.role_name:
        role_lower = ctx.role_name.lower()
        if 'admin' in role_lower:
            print(f"[COMPAT DEBUG]   -> Tier: admin (role name)")
            return 'admin'
        elif 'manager' in role_lower:
            print(f"[COMPAT DEBUG]   -> Tier: manager (role name)")
            return 'manager'
    
    # Check user.role attributes if available
    if user and hasattr(user, 'role'):
        print(f"[COMPAT DEBUG]   User.role: {user.role}")
        role = user.role
        if role:
            # Check is_admin flag
            if hasattr(role, 'is_admin') and role.is_admin:
                print(f"[COMPAT DEBUG]   -> Tier: admin (role.is_admin)")
                return 'admin'
            
            # Check role name from object
            if hasattr(role, 'name'):
                role_name_lower = role.name.lower()
                print(f"[COMPAT DEBUG]   Role.name: {role.name}")
                if 'admin' in role_name_lower:
                    print(f"[COMPAT DEBUG]   -> Tier: admin (role.name)")
                    return 'admin'
                elif 'manager' in role_name_lower:
                    print(f"[COMPAT DEBUG]   -> Tier: manager (role.name)")
                    return 'manager'
    
    # Default to individual
    print(f"[COMPAT DEBUG]   -> Tier: individual (default)")
    return 'individual'

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


def get_user_tier(request) -> str:
    """
    Quick helper to get user's permission tier.
    
    Args:
        request: Django/DRF request
        
    Returns:
        Tier string: 'admin' | 'manager' | 'individual'
    """
    ctx = get_auth_ctx(request)
    return ctx.tier


def is_admin(request) -> bool:
    """
    Check if the current request is from an admin user.
    
    Args:
        request: Django/DRF request
        
    Returns:
        True if admin tier
    """
    return get_user_tier(request) == 'admin'


def is_manager(request) -> bool:
    """
    Check if the current request is from a manager user.
    
    Args:
        request: Django/DRF request
        
    Returns:
        True if manager tier
    """
    return get_user_tier(request) == 'manager'


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
        'tier': ctx.tier,
        'role_id': ctx.role_id,
        'role_name': ctx.role_name,
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