// frontend/src/hooks/useUserPermissions.js
/**
 * User Permissions Hook
 * 
 * Centralized hook for role detection and permission checks.
 * 
 * Handles multiple user object formats depending on the data source:
 * 
 * 1. FROM ADMIN API LIST (useGetUsers) - MOST RELIABLE:
 *    { role_tier: 'admin'|'manager'|'individual', is_superuser: boolean }
 * 
 * 2. FROM ADMIN API DETAIL (useGetUser):
 *    { is_manager: boolean, is_superuser: boolean, role_name: string }
 * 
 * 3. FROM AUTH CONTEXT (useAuth):
 *    { role: "Admin" (string), role_name: string }
 *    Note: Limited info, falls back to string matching
 * 
 * 4. FROM JWT PAYLOAD (future):
 *    { role: { is_admin, is_manager, is_individual }, is_superuser }
 */

'use client';

import { useMemo, useCallback } from 'react';
import { useAuth } from 'hooks/useAuth';

// ==============================|| CONSTANTS ||============================== //

/**
 * Role tier values from backend
 */
export const ROLE_TIERS = {
  ADMIN: 'admin',
  MANAGER: 'manager',
  INDIVIDUAL: 'individual'
};

/**
 * Role names used for string-based detection (fallback)
 */
const ADMIN_ROLE_NAMES = ['admin', 'administrator', 'super admin', 'superadmin'];
const MANAGER_ROLE_NAMES = ['manager', 'team manager', 'sales manager', 'supervisor', 'lead', 'direction'];

// ==============================|| ROLE DETECTION ||============================== //

/**
 * Determine user role from user object
 * Handles all possible formats from different API sources
 * 
 * Priority order:
 * 1. role_tier field (most reliable - from admin API list)
 * 2. is_manager method result (from admin API detail)
 * 3. role object with is_admin/is_manager flags (JWT format)
 * 4. is_superuser flag
 * 5. String matching on role/role_name (fallback)
 * 
 * @param {Object} user - User object from any source
 * @returns {Object} Role flags and metadata
 */
function detectUserRole(user) {
  const defaultResult = {
    isAdmin: false,
    isManager: false,
    isIndividual: true,
    roleName: 'Individual',
    roleTier: ROLE_TIERS.INDIVIDUAL,
    _detectionMethod: 'default'
  };

  if (!user) {
    return { ...defaultResult, roleName: null, roleTier: null };
  }

  // ================================================================
  // METHOD 1: role_tier field (from admin API list - MOST RELIABLE)
  // UserListSerializer returns: role_tier = 'admin' | 'manager' | 'individual'
  // ================================================================
  if (user.role_tier) {
    const tier = user.role_tier.toLowerCase();
    
    return {
      isAdmin: tier === ROLE_TIERS.ADMIN || user.is_superuser === true,
      isManager: tier === ROLE_TIERS.MANAGER && user.is_superuser !== true,
      isIndividual: tier === ROLE_TIERS.INDIVIDUAL && user.is_superuser !== true,
      roleName: user.role?.name || user.role_name || tier.charAt(0).toUpperCase() + tier.slice(1),
      roleTier: tier,
      _detectionMethod: 'role_tier'
    };
  }

  // ================================================================
  // METHOD 2: is_manager method result (from admin API detail)
  // UserSerializer returns: is_manager = boolean (from obj.is_manager())
  // ================================================================
  if (typeof user.is_manager === 'boolean') {
    const isAdmin = user.is_superuser === true;
    const isManager = !isAdmin && user.is_manager === true;
    const isIndividual = !isAdmin && !isManager;
    
    let roleTier = ROLE_TIERS.INDIVIDUAL;
    if (isAdmin) roleTier = ROLE_TIERS.ADMIN;
    else if (isManager) roleTier = ROLE_TIERS.MANAGER;
    
    return {
      isAdmin,
      isManager,
      isIndividual,
      roleName: user.role_name || (isAdmin ? 'Admin' : isManager ? 'Manager' : 'Individual'),
      roleTier,
      _detectionMethod: 'is_manager_field'
    };
  }

  // ================================================================
  // METHOD 3: Role object with boolean flags (JWT/future format)
  // JWT contains: role = { is_admin, is_manager, is_individual, name }
  // ================================================================
  const role = user.role;
  if (role && typeof role === 'object' && ('is_admin' in role || 'is_manager' in role)) {
    const isAdmin = role.is_admin === true || user.is_superuser === true;
    const isManager = !isAdmin && role.is_manager === true;
    const isIndividual = !isAdmin && !isManager;

    let roleTier = ROLE_TIERS.INDIVIDUAL;
    if (isAdmin) roleTier = ROLE_TIERS.ADMIN;
    else if (isManager) roleTier = ROLE_TIERS.MANAGER;

    return {
      isAdmin,
      isManager,
      isIndividual,
      roleName: role.name || user.role_name || roleTier,
      roleTier,
      _detectionMethod: 'role_object'
    };
  }

  // ================================================================
  // METHOD 4: is_superuser flag only
  // ================================================================
  if (user.is_superuser === true) {
    return {
      isAdmin: true,
      isManager: false,
      isIndividual: false,
      roleName: user.role_name || 'Super Admin',
      roleTier: ROLE_TIERS.ADMIN,
      _detectionMethod: 'is_superuser'
    };
  }

  // ================================================================
  // METHOD 5: String matching on role or role_name (FALLBACK)
  // Auth endpoints return: role = "Admin" (string)
  // ================================================================
  const roleString = (typeof role === 'string' ? role : user.role_name) || '';
  if (roleString) {
    const roleLower = roleString.toLowerCase().trim();
    
    const isAdmin = ADMIN_ROLE_NAMES.some(name => roleLower.includes(name));
    const isManager = !isAdmin && MANAGER_ROLE_NAMES.some(name => roleLower.includes(name));
    const isIndividual = !isAdmin && !isManager;

    let roleTier = ROLE_TIERS.INDIVIDUAL;
    if (isAdmin) roleTier = ROLE_TIERS.ADMIN;
    else if (isManager) roleTier = ROLE_TIERS.MANAGER;

    return {
      isAdmin,
      isManager,
      isIndividual,
      roleName: roleString,
      roleTier,
      _detectionMethod: 'string_match'
    };
  }

  return defaultResult;
}

// ==============================|| MAIN HOOK ||============================== //

/**
 * useUserPermissions Hook
 * 
 * Uses user from auth context by default.
 * Can accept an optional user object override (e.g., from useGetUser).
 * 
 * @param {Object} options
 * @param {Object} options.user - Optional user object override
 * @returns {Object} Permission context
 */
export function useUserPermissions(options = {}) {
  const { user: authUser, isLoading: authLoading } = useAuth();
  
  // Allow passing a specific user (e.g., from useGetUser for full permissions)
  const user = options.user || authUser;
  const isLoading = options.user ? false : authLoading;

  // Memoize role detection
  const roleInfo = useMemo(() => detectUserRole(user), [user]);

  // Current user ID
  const currentUserId = useMemo(() => user?.id || null, [user]);

  /**
   * Check if current user owns a resource
   */
  const isOwner = useCallback((resourceOwnerId) => {
    if (!currentUserId || !resourceOwnerId) return false;
    return currentUserId === resourceOwnerId;
  }, [currentUserId]);

  /**
   * Check if current user can manage a resource
   * (is admin, or is manager)
   * 
   * TODO Phase 2.5: Add team membership checks
   */
  const canManage = useCallback((resourceOwnerId) => {
    if (roleInfo.isAdmin) return true;
    if (roleInfo.isManager) return true;
    return false;
  }, [roleInfo.isAdmin, roleInfo.isManager]);

  /**
   * Managed user IDs placeholder
   * TODO: Phase 2.5 - Fetch from backend endpoint
   */
  const managedUserIds = useMemo(() => [], []);

  // ==============================|| RETURN ||============================== //

  return useMemo(() => ({
    // User info
    currentUser: user,
    currentUserId,
    
    // Role flags
    isAdmin: roleInfo.isAdmin,
    isManager: roleInfo.isManager,
    isIndividual: roleInfo.isIndividual,
    roleName: roleInfo.roleName,
    roleTier: roleInfo.roleTier,
    
    // Debug info
    _detectionMethod: roleInfo._detectionMethod,
    
    // Permission helpers
    isOwner,
    canManage,
    
    // Managed users (Phase 2.5)
    managedUserIds,
    
    // Loading state
    isLoading
  }), [user, currentUserId, roleInfo, isOwner, canManage, managedUserIds, isLoading]);
}

// ==============================|| PERMISSION CHECK HELPERS ||============================== //

/**
 * Check if user can edit manager notes
 */
export function canEditManagerNotes({
  isAdmin,
  isManager,
  currentUserId,
  resourceOwnerId,
  managedUserIds = []
}) {
  if (isAdmin) return true;
  
  if (isManager) {
    if (managedUserIds.length > 0) {
      return managedUserIds.includes(resourceOwnerId);
    }
    // Managers can edit for anyone except themselves
    return currentUserId !== resourceOwnerId;
  }
  
  return false;
}

/**
 * Check if user can view manager notes
 */
export function canViewManagerNotes({
  isAdmin,
  isManager,
  currentUserId,
  resourceOwnerId,
  managedUserIds = []
}) {
  if (isAdmin) return true;
  
  if (isManager) {
    if (managedUserIds.length > 0) {
      return managedUserIds.includes(resourceOwnerId) || currentUserId === resourceOwnerId;
    }
    return true;
  }
  
  // Resource owner can view their own notes
  if (currentUserId === resourceOwnerId) return true;
  
  return false;
}

/**
 * Check if user can delete a resource
 */
export function canDeleteResource({
  isAdmin,
  isManager,
  currentUserId,
  resourceOwnerId,
  managedUserIds = []
}) {
  if (isAdmin) return true;
  if (currentUserId === resourceOwnerId) return true;
  
  if (isManager) {
    if (managedUserIds.length > 0) {
      return managedUserIds.includes(resourceOwnerId);
    }
    return true;
  }
  
  return false;
}

// ==============================|| DEFAULT EXPORT ||============================== //

export default useUserPermissions;
