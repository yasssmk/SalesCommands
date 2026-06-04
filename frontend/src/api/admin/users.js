// frontend/src/api/admin/users.js

import useSWR from "swr";
import { useMemo, useRef } from "react";
import { useAuth } from "hooks/useAuth";
import { debounce } from "lodash";

// utils
import { api } from "utils/axiosClient";
import {
  tenantKey,
  revalidateByPrefix,
  revalidateMultiple,
  handleBulkRevalidation,
  handleBulkTimeout,
} from "api/_swr";
import { isValidUUID, sanitizeObject } from "utils/validators";

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  users: "/client/users/",
  organizations: "/client/organizations/",
  teams: "/client/teams/",
  roles: "/client/roles/",
  clientAccountSeats: (clientId) =>
    `/client/client-accounts/${clientId}/seats/`,
  clientAccountStats: (clientId) =>
    `/client/client-accounts/${clientId}/stats/`,
};

// ==============================|| DEBOUNCED REVALIDATION (1.4) ||============================== //

/**
 * ✅ Debounced revalidation pour éviter rafales
 *
 * Groupe les revalidations multiples en 300ms max pour éviter :
 * - Les rafales HTTP lors de bulk operations successives
 * - La surcharge serveur avec requests concurrentes
 *
 * Exemple : 3 bulk ops en 200ms → 1 seule revalidation users finale
 */
const debouncedRevalidate = debounce((paths) => {
  revalidateMultiple(paths);
}, 300);

// ==============================|| HELPER - BUILD URL WITH PARAMS ||============================== //

/**
 * Construit une URL avec query params pour la pagination serveur
 * @param {string} baseUrl - URL de base
 * @param {Object} params - Paramètres optionnels {page, pageSize, search}
 * @returns {string} URL avec query string
 */
const buildUrlWithParams = (baseUrl, params = {}) => {
  const { page, pageSize, search, ordering, filters } = params;
  const queryParams = new URLSearchParams();

  // Ajouter les paramètres s'ils sont définis
  if (page !== undefined && page !== null) {
    queryParams.append("page", page);
  }

  if (pageSize !== undefined && pageSize !== null) {
    queryParams.append("page_size", pageSize);
  }

  if (search !== undefined && search !== null && search !== "") {
    queryParams.append("search", search);
  }

  if (ordering !== undefined && ordering !== null && ordering !== "") {
    queryParams.append("ordering", ordering);
  }

  // Add filters (team, role, is_active, etc.)
  if (filters.team) {
    queryParams.append("team", filters.team);
  }

  if (filters.role) {
    queryParams.append("role", filters.role);
  }

  if (filters.is_active !== undefined && filters.is_active !== null) {
    queryParams.append("is_active", filters.is_active);
  }

  if (filters.role_tier) {
    queryParams.append("role_tier", filters.role_tier);
  }

  const queryString = queryParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

// ==============================|| HOOKS SWR STANDARDISÉS ||============================== //

/**
 * ✅ GET USERS LIST - Avec pagination serveur Django REST
 *
 * @param {Object} options - Options de pagination et filtres
 * @param {number} options.page - Numéro de page (1-indexed, défaut: 1)
 * @param {number} options.pageSize - Taille de page (défaut: 10)
 * @param {string} options.search - Terme de recherche
 * @param {string} options.ordering - Tri (ex: 'name', '-created_at')
 * @param {Object} options.filters - Filtres {team, role, is_active}
 *
 * @returns {Object} {users, usersCount, usersLoading, usersError, usersValidating, usersEmpty}
 *
 * @example
 * // Sans paramètres (page 1, taille 10)
 * const { users, usersCount } = useGetUsers();
 *
 * @example
 * // Avec pagination
 * const { users, usersCount } = useGetUsers({ page: 2, pageSize: 25 });
 *
 * @example
 * // Avec recherche
 * const { users, usersCount } = useGetUsers({ search: 'john', page: 1, pageSize: 10 });
 *
 * @example
 * // Avec filtres
 * const { users, usersCount } = useGetUsers({ filters: { team: 'team-uuid', role: 'role-uuid' } });
 */
export function useGetUsers(options = {}) {
  const { tenantId } = useAuth();
  const {
    page = 1,
    pageSize = 10,
    search = "",
    ordering = "",
    filters = {},
  } = options;

  // Extract filter values for stable dependencies
  const teamFilter = filters.team || "";
  const roleFilter = filters.role || "";
  const isActiveFilter =
    filters.is_active !== undefined ? String(filters.is_active) : "";
  const roleTierFilter = filters.role_tier || "";

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.users, {
      page,
      pageSize,
      search,
      ordering,
      filters: {
        ...(teamFilter && { team: teamFilter }),
        ...(roleFilter && { role: roleFilter }),
        ...(isActiveFilter !== "" && { is_active: isActiveFilter === "true" }),
        ...(roleTierFilter && { role_tier: roleTierFilter }),
      },
    });
  }, [
    page,
    pageSize,
    search,
    ordering,
    teamFilter,
    roleFilter,
    isActiveFilter,
    roleTierFilter,
  ]);

  // ✅ STANDARDISÉ: Utilise toujours tenantKey()
  const swrKey = tenantKey(urlWithParams, tenantId);
  // const { data, isLoading, error, isValidating } = useSWR(swrKey);
  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
    // dedupingInterval: 5000, // Évite les requêtes dupliquées pendant 5s - redondant avec ProviderWrapper
  });

  const memoizedValue = useMemo(
    () => ({
      users: data?.data?.results || data?.results || [],
      usersCount: data?.data?.count || data?.count || 0,
      usersEmpty:
        !isLoading && !(data?.data?.results?.length || data?.results?.length),
      usersLoading: isLoading,
      usersError: error,
      usersValidating: isValidating,
    }),
    [data, error, isLoading, isValidating],
  );

  if (process.env.NODE_ENV === "development") {
    console.log("🔍 [useGetUsers]", {
      rawData: data,
      users: data?.data?.results || data?.results || [],
      count: data?.data?.count || data?.count || 0,
    });
  }

  return memoizedValue;
}

/**
 * ✅ GET SINGLE USER - Pour UN utilisateur spécifique
 * @param {string} userId - ID de l'utilisateur à récupérer
 *
 * ⚠️ IMPORTANT: Pour le current user, utiliser useCurrentUser() à la place
 */
export function useGetUser(userId) {
  const { tenantId, user: currentUser } = useAuth();

  // Detect if we're requesting the current user
  const isRequestingCurrentUser =
    !userId || userId === "current" || userId === "me";
  const shouldUseCurrentUser =
    isRequestingCurrentUser || userId === currentUser?.id;

  // ✅ Always call useSWR (passing null disables the fetch when not needed)
  // This respects Rules of Hooks: same hook order on every render.
  const swrKey =
    !shouldUseCurrentUser && userId && tenantId
      ? tenantKey(`${endpoints.users}${userId}/`, tenantId)
      : null;

  const { data, isLoading, error, isValidating } = useSWR(swrKey);

  // ✅ Always call useMemo, branch the return value inside
  const memoizedValue = useMemo(() => {
    // If requesting current user, return data from Auth context
    if (shouldUseCurrentUser) {
      return {
        user: currentUser,
        userLoading: false,
        userError: null,
        userValidating: false,
      };
    }

    // Otherwise return the fetched data
    return {
      user: data?.data || data,
      userLoading: isLoading,
      userError: error,
      userValidating: isValidating,
    };
  }, [shouldUseCurrentUser, currentUser, data, error, isLoading, isValidating]);

  if (process.env.NODE_ENV === "development") {
    console.log("🔍 [useGetUser]", {
      mode: shouldUseCurrentUser ? "current-user-from-context" : "fetched",
      rawData: data,
      user: memoizedValue.user,
    });
  }

  return memoizedValue;
}

/**
 * ✅ GET CLIENT SEATS STATS - Clé tenant standardisée
 * seats = client.max_users
 * seats_used = # active users
 * seats_left = seats - seats_used
 */
export function useGetClientSeats(clientId) {
  const { tenantId } = useAuth();

  // ✅ NOUVEAU: Utilise l'endpoint /seats/ au lieu de /stats/
  const swrKey =
    clientId && tenantId
      ? tenantKey(endpoints.clientAccountSeats(clientId), tenantId)
      : null;

  const { data, isLoading, error, isValidating } = useSWR(swrKey);

  // Debug pour vérifier la structure
  // if (process.env.NODE_ENV === 'development' && data) {
  //   console.log('[useGetClientSeats] Response:', data);
  // }

  // ✅ Structure correcte: data.data contient directement seats, seats_used, seats_left
  const seatData = data?.data || {};

  const seats = Number(seatData.seats ?? 0);
  const seatsUsed = Number(seatData.seats_used ?? 0);
  const seatsLeft = Number(seatData.seats_left ?? 0);

  const memoizedValue = useMemo(
    () => ({
      seats,
      seatsUsed,
      seatsLeft,
      seatsLoading: isLoading,
      seatsError: error,
      seatsValidating: isValidating,
      // Métadonnées de performance
      timing: data?._meta?.timing_ms,
      raw: data, // Pour debug si besoin
    }),
    [seats, seatsUsed, seatsLeft, isLoading, error, isValidating, data],
  );

  return memoizedValue;
}

// ==============================|| CRUD FUNCTIONS AVEC REVALIDATIONS STANDARDISÉES ||============================== //

/**
 * ✅ CREATE USER - Revalidation standardisée + validation client
 *
 * ✅ PHASE 5.3.2: Added UUID validation and string sanitization
 *
 * @param {Object} userData - User data to create
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const insertUser = async (userData) => {
  // ✅ PHASE 5.3.2: Validate UUID fields before API call
  const uuidFields = ["role", "organization", "team"];
  for (const field of uuidFields) {
    const value = userData[field];

    // Skip validation if field is null/undefined/empty (nullable fields)
    if (!value || value === "") continue;

    // Validate UUID format
    if (!isValidUUID(value)) {
      return {
        success: false,
        error: `Invalid ${field} ID format. Please select a valid ${field}.`,
      };
    }
  }

  // Sanitize string fields (trim whitespace)
  const sanitized = sanitizeObject(userData, [
    "email",
    "first_name",
    "last_name",
  ]);

  const result = await api.post(endpoints.users, sanitized);

  console.log(result);
  if (result.success) {
    // ✅ STANDARDISÉ: revalidateByPrefix pour tous les endpoints impactés
    revalidateMultiple([
      endpoints.users, // Liste users
      "/client/client-accounts/", // Stats seats
      "/client/roles/",
      "/client/teams/",
    ]);

    return { success: true, user: result.data };
  } else {
    return {
      success: false,
      error: result.error,
      status: result.status || 0,
      response: result.response || null,
    };
  }
};

/**
 * ✅ UPDATE USER (PATCH) - Revalidation standardisée + validation client
 *
 * ✅ Added UUID validation for userId and related fields
 *
 * @param {string} userId - User ID to update
 * @param {Object} userData - User data to update
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const updateUser = async (userId, userData) => {
  // ✅ PHASE 5.3.2: Validate userId is a valid UUID
  if (!userId || !isValidUUID(userId)) {
    return {
      success: false,
      error: "Invalid user ID format. Cannot update user.",
    };
  }

  // ✅ Validate UUID fields in userData
  const uuidFields = ["role", "organization", "team"];
  for (const field of uuidFields) {
    const value = userData[field];

    // Skip validation if field is null/undefined/empty (nullable fields)
    if (!value || value === "") continue;

    // Validate UUID format
    if (!isValidUUID(value)) {
      return {
        success: false,
        error: `Invalid ${field} ID format. Please select a valid ${field}.`,
      };
    }
  }

  // ✅ Sanitize string fields (trim whitespace)
  const sanitized = sanitizeObject(userData, ["first_name", "last_name"]);

  const result = await api.patch(`${endpoints.users}${userId}/`, sanitized);

  if (result.success) {
    // ✅ STANDARDISÉ: revalidation ciblée avec prefixes
    revalidateMultiple([
      endpoints.users, // Liste users
      `${endpoints.users}${userId}/`, // User spécifique
      "/client/client-accounts/", // Stats seats
      "/client/roles/",
      "/client/teams/",
    ]);

    return { success: true, user: result.data };
  } else {
    return {
      success: false,
      error: result.error,
      status: result.status || 0,
      response: result.response || null,
    };
  }
};

/**
 * ✅ CHANGE USER PASSWORD - Revalidation standardisée + validation client
 *
 * ✅ PHASE 5.3.2: Added UUID validation for userId
 *
 * @param {string} userId - ID de l'utilisateur
 * @param {string} password - Nouveau mot de passe
 * @param {string} passwordConfirm - Confirmation du mot de passe
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: Object, error?: string}
 */
export const changePassword = async (userId, password, passwordConfirm) => {
  // ✅ PHASE 5.3.2: Validate userId is a valid UUID
  if (!userId || !isValidUUID(userId)) {
    return {
      success: false,
      error: "Invalid user ID format. Cannot change password.",
    };
  }

  // ✅ Additional validation: password length (client-side quick check)
  if (!password || password.length < 8) {
    return {
      success: false,
      error: "Password must be at least 8 characters long.",
    };
  }

  // ✅ Additional validation: passwords match
  if (password !== passwordConfirm) {
    return {
      success: false,
      error: "Passwords do not match.",
    };
  }

  const result = await api.patch(
    `${endpoints.users}${userId}/change-password/`,
    {
      password,
      password_confirm: passwordConfirm,
    },
  );

  if (result.success) {
    // ✅ STANDARDISÉ: revalidation ciblée uniquement sur l'user modifié
    revalidateByPrefix(`${endpoints.users}${userId}/`);

    return {
      success: true,
      message: result.data?.message || "Password changed successfully",
      user: result.data?.user,
    };
  } else {
    return {
      success: false,
      error: result.error || "Failed to change password",
      status: result.status || 0,
      response: result.response || null,
    };
  }
};

/**
 * ✅ DELETE USER - Revalidation standardisée + validation client
 *
 * ✅ PHASE 5.3.2: Added UUID validation for userId
 *
 * @param {string} userId - User ID to delete
 * @returns {Promise<Object>} {success: boolean, status?: number, error?: string}
 */
export const deleteUser = async (userId) => {
  if (!userId || !isValidUUID(userId)) {
    return {
      success: false,
      error: "Invalid user ID format. Cannot delete user.",
      status: 400,
    };
  }

  const result = await api.delete(`${endpoints.users}${userId}/`);

  if (result.success) {
    // ✅ revalidation multiple après suppression
    revalidateMultiple([
      endpoints.users, // Liste users
      "/client/client-accounts/", // Stats seats (seats_used diminue)
      "/client/roles/",
      "/client/teams/",
    ]);

    return { success: true, status: result.status ?? 204 };
  } else {
    return {
      success: false,
      error: result.error,
      status: result.status || 0,
      response: result.response || null,
    };
  }
};

/**
 * ✅ TOGGLE USER STATUS - Revalidation standardisée + validation client
 *
 * ✅ PHASE 5.3.2: Added UUID validation for userId
 *
 * @param {string} userId - User ID to toggle status
 * @returns {Promise<Object>} {success: boolean, user?: Object, error?: string}
 */
export const toggleUserStatus = async (userId) => {
  // ✅ PHASE 5.3.2: Validate userId is a valid UUID
  if (!userId || !isValidUUID(userId)) {
    return {
      success: false,
      error: "Invalid user ID format. Cannot toggle user status.",
    };
  }

  const result = await api.post(`${endpoints.users}${userId}/toggle-status/`);

  if (result.success) {
    // ✅ STANDARDISÉ: revalidation après changement de statut
    revalidateMultiple([
      endpoints.users, // Liste users
      `${endpoints.users}${userId}/`, // User spécifique
      "/client/client-accounts/", // Stats seats (active/inactive impact),
    ]);

    return { success: true, user: result.data };
  } else {
    return {
      success: false,
      error: result.error,
      status: result.status || 0,
      response: result.response || null,
    };
  }
};

// ==============================|| MODIFICATION 1: createBulkUsers ||============================== //

/**
 * ✅ BULK CREATE USERS
 *
 * Crée plusieurs utilisateurs en une seule requête
 * ✅ STEP 4.2: Uses 'bulk' profile (60s timeout)
 *
 * @param {Array} users - Array of user objects
 * @param {string} mode - 'partial' (continue on error) or 'strict' (all or nothing)
 * @param {Function} onSyncProgress - Optional callback: (attempt, maxAttempts) => void
 * @param {Function} onSyncComplete - Optional callback: () => void (called when sync is done)
 * @returns {Promise<Object>} {success: boolean, summary: Object, results: Object}
 */
export const createBulkUsers = async (
  users,
  mode = "partial",
  onSyncProgress = null,
  onSyncComplete = null,
) => {
  let result = null;

  try {
    console.log("[createBulkUsers] start", { count: users?.length ?? 0, mode });

    result = await api.post(
      "/client/users/bulk-create/",
      { users, mode },
      { profile: "bulk" },
    );

    console.log("[createBulkUsers] API response received:", {
      success: result.success,
      status: result.status,
      hasData: !!result.data,
      is202: result?.data?.__is202,
    });

    // ✅ CAS 202 : Attendre le polling AVANT de retourner
    if (result?.data?.__is202) {
      console.log("[createBulkUsers] 🔄 202 detected, starting polling...");

      const finalResult = await handleBulkRevalidation(
        result,
        [
          endpoints.users,
          "/client/client-accounts/",
          "/client/roles/",
          "/client/teams/",
        ],
        onSyncProgress,
        onSyncComplete,
      );

      console.log("[createBulkUsers] 📥 Polling complete:", {
        hasFinalResult: !!finalResult,
        finalResultType: typeof finalResult,
        hasData: finalResult?.data !== undefined,
        dataKeys: finalResult?.data ? Object.keys(finalResult.data) : [],
        fullStructure: finalResult,
      });

      // handleBulkRevalidation retourne pollResult.result = { data: {...}, http_status: 201 }
      if (finalResult?.data) {
        console.log("[createBulkUsers] ✅ Returning polling result");
        if (finalResult.data?.status === "pending") {
          console.log(
            "[createBulkUsers] ⏳ Polling reached max attempts, marking operation as pending",
          );
          return {
            ...finalResult.data,
            success: false,
            status: finalResult.data.status || "pending",
            isPending: true,
          };
        }

        return finalResult.data;
      }

      // Peut-être que finalResult EST directement le data ?
      if (finalResult && (finalResult.summary || finalResult.results)) {
        console.log(
          "[createBulkUsers] ✅ Returning finalResult directly (no nesting)",
        );
        return finalResult;
      }

      // Si pas de data, fallback sur erreur
      console.error("[createBulkUsers] ❌ finalResult missing data structure");
      return {
        success: false,
        message: "Polling completed but no result data",
        summary: {
          total: users?.length ?? 0,
          success: 0,
          failed: users?.length ?? 0,
          skipped: 0,
        },
        results: { success: [], failed: [], skipped: [] },
      };
    }

    // ✅ CAS SYNC : Retourner immédiatement
    if (result.success) {
      console.log("[createBulkUsers] ✅ Sync success", {
        status: result.status ?? 200,
        created: result.data?.summary?.success ?? 0,
      });

      // Revalidation immédiate pour mode sync
      revalidateMultiple([
        endpoints.users,
        "/client/client-accounts/",
        "/client/roles/",
        "/client/teams/",
      ]);

      return result.data;
    }

    // CAS TIMEOUT - Trigger polling (apiRequest returns, doesn't throw)
    if (result.isTimeout) {
      console.log(
        "[createBulkUsers] ⏱️ Timeout detected in result, starting polling...",
      );

      const pollResult = await handleBulkTimeout(
        { idempotencyKey: result.idempotencyKey },
        [
          endpoints.users,
          "/client/client-accounts/",
          "/client/roles/",
          "/client/teams/",
        ],
        onSyncProgress,
        onSyncComplete,
      );

      if (pollResult?.status === "succeeded") {
        // Backend stores: { data: {...}, http_status: 200 }
        // We need to unwrap .data to get the actual result
        const actualResult = pollResult.result?.data || pollResult.result || {};
        return {
          success: true,
          ...actualResult,
        };
      }

      return {
        success: false,
        isTimeout: true,
        isPending: pollResult?.status === "still_running",
        message:
          pollResult?.error || "Operation may have completed in background",
        summary: {
          total: users?.length ?? 0,
          success: 0,
          failed: 0,
          skipped: 0,
        },
        results: { success: [], failed: [], skipped: [] },
      };
    }

    // ❌ Gestion d'erreur
    const status = result.status || 0;
    const message = result.error || "Bulk create failed";
    console.error("[createBulkUsers] api.post error", { status, message });

    if (result.data && typeof result.data === "object") {
      if (result.data.results || result.data.summary) {
        console.log(
          "[createBulkUsers] returning structured error from backend",
        );
        return {
          ...result.data,
          success: false,
          isTimeout: result.isTimeout || false,
        };
      }
    }

    return {
      success: false,
      isTimeout: result.isTimeout || false,
      message: message,
      error: { status, message, response: result.response || null },
      summary: {
        total: users?.length ?? 0,
        success: 0,
        failed: users?.length ?? 0,
        skipped: 0,
      },
      results: {
        success: [],
        failed: (users || []).map((u, i) => ({
          row: i + 1,
          email: u?.email || "(unknown)",
          errors: [message],
        })),
        skipped: [],
      },
    };
  } catch (err) {
    console.error("[createBulkUsers] thrown", err);

    const isTimeout =
      err?.code === "ECONNABORTED" ||
      err?.message?.toLowerCase()?.includes("timeout") ||
      err?.response?.status === 408 ||
      err?.response?.status === 504;

    if (isTimeout) {
      console.log("[createBulkUsers] ⏱️ Timeout detected, starting polling...");

      const pollResult = await handleBulkTimeout(
        err,
        [
          endpoints.users,
          "/client/client-accounts/",
          "/client/roles/",
          "/client/teams/",
        ],
        onSyncProgress,
        onSyncComplete,
      );

      if (pollResult?.status === "succeeded") {
        // Backend stores: { data: {...}, http_status: 200 }
        // We need to unwrap .data to get the actual result
        const actualResult = pollResult.result?.data || pollResult.result || {};
        return {
          success: true,
          ...actualResult,
        };
      }

      // Polling terminé mais pas de succès confirmé
      return {
        success: false,
        isTimeout: true,
        isPending: pollResult?.status === "still_running",
        message:
          pollResult?.error || "Operation may have completed in background",
        summary: {
          total: users?.length ?? 0,
          success: 0,
          failed: 0,
          skipped: 0,
        },
        results: { success: [], failed: [], skipped: [] },
      };
    }

    // Autres erreurs (non-timeout)
    return {
      success: false,
      isTimeout: false,
      message: err?.message || "Unknown error",
      error: { message: err?.message || String(err) },
      summary: {
        total: users?.length ?? 0,
        success: 0,
        failed: users?.length ?? 0,
        skipped: 0,
      },
      results: {
        success: [],
        failed: (users || []).map((u, i) => ({
          row: i + 1,
          email: u?.email || "(unknown)",
          errors: [err?.message || "Unknown error"],
        })),
        skipped: [],
      },
    };
  }
};
// ==============================|| MODIFICATION 2: bulkDeleteUsers ||============================== //

/**
 * ✅ BULK DELETE USERS
 *
 * Supprime plusieurs utilisateurs en une seule requête
 * ✅ STEP 4.2: Uses 'bulk' profile (60s timeout)
 * ⚠️ En MVP/dev: suppression PHYSIQUE (hard delete)
 * ⚠️ En prod: utiliser bulkSoftDeleteUsers à la place
 *
 * @param {Array<string>} userIds - Array of user IDs to delete
 * @param {string} mode - 'partial' (continue on error) or 'strict' (all or nothing)
 * @param {Function} onSyncProgress - Optional callback: (attempt, maxAttempts) => void
 * @param {Function} onSyncComplete - Optional callback: () => void (called when sync is done)
 * @returns {Promise<Object>} {success: boolean, isTimeout?: boolean, summary: Object, results: Object}
 */
export const bulkDeleteUsers = async (
  userIds,
  mode = "partial",
  onSyncProgress = null,
  onSyncComplete = null,
) => {
  let result = null;

  try {
    console.log("[bulkDeleteUsers] start", {
      count: userIds?.length ?? 0,
      mode,
    });

    if (!Array.isArray(userIds) || userIds.length === 0) {
      return {
        success: false,
        message: "No user IDs provided",
        summary: { requested: 0, deleted: 0, failed: 0 },
        results: { success: [], failed: [] },
      };
    }

    const invalidIds = userIds.filter((id) => !isValidUUID(id));
    if (invalidIds.length > 0) {
      console.error("[bulkDeleteUsers] invalid UUIDs", {
        count: invalidIds.length,
      });
      return {
        success: false,
        message: `${invalidIds.length} invalid user ID(s) detected`,
        summary: {
          requested: userIds.length,
          deleted: 0,
          failed: userIds.length,
        },
        results: {
          success: [],
          failed: invalidIds.map((id) => ({
            id,
            errors: ["Invalid UUID format"],
          })),
        },
      };
    }

    result = await api.delete("/client/users/bulk-delete/", {
      data: { ids: userIds, mode },
      profile: "bulk",
    });

    console.log("[bulkDeleteUsers] API response received:", {
      success: result.success,
      status: result.status,
      hasData: !!result.data,
      is202: result?.data?.__is202,
    });

    // ✅ CAS 202 : Attendre le polling
    if (result?.data?.__is202) {
      console.log("[bulkDeleteUsers] 🔄 202 detected, starting polling...");

      const finalResult = await handleBulkRevalidation(
        result,
        [
          endpoints.users,
          "/client/client-accounts/",
          "/client/roles/",
          "/client/teams/",
        ],
        onSyncProgress,
        onSyncComplete,
      );

      console.log("[bulkDeleteUsers] 📥 Polling complete:", {
        hasFinalResult: !!finalResult,
        hasData: finalResult?.data !== undefined,
      });

      if (finalResult?.data) {
        console.log("[bulkDeleteUsers] ✅ Returning polling result");
        if (finalResult.data?.status === "pending") {
          console.log(
            "[bulkDeleteUsers] ⏳ Polling reached max attempts, marking operation as pending",
          );
          return {
            ...finalResult.data,
            success: false,
            status: finalResult.data.status || "pending",
            isPending: true,
          };
        }

        return finalResult.data;
      }

      if (finalResult && (finalResult.summary || finalResult.results)) {
        console.log("[bulkDeleteUsers] ✅ Returning finalResult directly");
        return finalResult;
      }

      console.error("[bulkDeleteUsers] ❌ finalResult missing data");
      return {
        success: false,
        message: "Polling completed but no result data",
        summary: {
          requested: userIds.length,
          deleted: 0,
          failed: userIds.length,
        },
        results: { success: [], failed: [] },
      };
    }

    // ✅ CAS SYNC
    if (result.success) {
      console.log("[bulkDeleteUsers] ✅ Sync success", {
        status: result.status ?? 200,
        deleted: result.data?.summary?.deleted ?? 0,
      });

      revalidateMultiple([
        endpoints.users,
        "/client/client-accounts/",
        "/client/roles/",
        "/client/teams/",
      ]);
      return result.data;
    }

    // CAS TIMEOUT - Trigger polling (apiRequest returns, doesn't throw)
    if (result.isTimeout) {
      console.log(
        "[bulkDeleteUsers] ⏱️ Timeout detected in result, starting polling...",
      );

      const pollResult = await handleBulkTimeout(
        { idempotencyKey: result.idempotencyKey },
        [
          endpoints.users,
          "/client/client-accounts/",
          "/client/roles/",
          "/client/teams/",
        ],
        onSyncProgress,
        onSyncComplete,
      );

      if (pollResult?.status === "succeeded") {
        // Backend stores: { data: {...}, http_status: 200 }
        // We need to unwrap .data to get the actual result
        const actualResult = pollResult.result?.data || pollResult.result || {};
        return {
          success: true,
          ...actualResult,
        };
      }

      return {
        success: false,
        isTimeout: true,
        isPending: pollResult?.status === "still_running",
        message:
          pollResult?.error || "Operation may have completed in background",
        summary: { requested: userIds?.length ?? 0, deleted: 0, failed: 0 },
        results: { success: [], failed: [] },
      };
    }

    // ❌ Gestion erreur
    const status = result.status || 0;
    const message = result.error || "Bulk delete failed";
    console.error("[bulkDeleteUsers] api.delete error", { status, message });

    if (result.data && typeof result.data === "object") {
      if (result.data.results || result.data.summary) {
        console.log(
          "[bulkDeleteUsers] returning structured error from backend",
        );
        return {
          ...result.data,
          success: false,
          status: result.status,
          isTimeout: result.isTimeout || false,
        };
      }
    }

    return {
      success: false,
      isTimeout: result.isTimeout || false,
      message: message,
      error: { status, message, response: result.response || null },
      summary: {
        requested: userIds.length,
        deleted: 0,
        failed: userIds.length,
      },
      results: {
        success: [],
        failed: userIds.map((id) => ({ id, errors: [message] })),
      },
    };
  } catch (err) {
    console.error("[bulkDeleteUsers] thrown", err);

    const isTimeout =
      err?.code === "ECONNABORTED" ||
      err?.message?.toLowerCase()?.includes("timeout") ||
      err?.response?.status === 408 ||
      err?.response?.status === 504;

    if (isTimeout) {
      console.log("[bulkDeleteUsers] ⏱️ Timeout detected, starting polling...");

      const pollResult = await handleBulkTimeout(
        err,
        [
          endpoints.users,
          "/client/client-accounts/",
          "/client/roles/",
          "/client/teams/",
        ],
        onSyncProgress,
        onSyncComplete,
      );

      if (pollResult?.status === "succeeded") {
        // Backend stores: { data: {...}, http_status: 200 }
        // We need to unwrap .data to get the actual result
        const actualResult = pollResult.result?.data || pollResult.result || {};
        return {
          success: true,
          ...actualResult,
        };
      }

      // Polling terminé mais pas de succès confirmé
      return {
        success: false,
        isTimeout: true,
        isPending: pollResult?.status === "still_running",
        message:
          pollResult?.error || "Operation may have completed in background",
        summary: { requested: userIds?.length ?? 0, deleted: 0, failed: 0 },
        results: { success: [], failed: [] },
      };
    }

    // Autres erreurs (non-timeout)
    return {
      success: false,
      isTimeout: false,
      message: err?.message || "Unknown error",
      error: { message: err?.message || String(err) },
      summary: {
        requested: userIds?.length ?? 0,
        deleted: 0,
        failed: userIds?.length ?? 0,
      },
      results: {
        success: [],
        failed: (userIds || []).map((id) => ({
          id,
          errors: [err?.message || "Unknown error"],
        })),
      },
    };
  }
};
// ==============================|| MODIFICATION 3: bulkUpdateUsers ||============================== //

/**
 * ✅ BULK UPDATE USERS
 *
 * Met à jour plusieurs utilisateurs en une seule requête
 * ✅ STEP 4.2: Uses 'bulk' profile (60s timeout)
 *
 * @param {Array<string>} userIds - Array of user IDs to update
 * @param {Object} patchData - Data to apply to all selected users
 * @param {string} mode - 'partial' (continue on error) or 'strict' (all or nothing)
 * @param {Function} onSyncProgress - Optional callback: (attempt, maxAttempts) => void
 * @param {Function} onSyncComplete - Optional callback: () => void (called when sync is done)
 * @returns {Promise<Object>} {success: boolean, isTimeout?: boolean, summary: Object, results: Object}
 */
export const bulkUpdateUsers = async (
  userIds,
  patchData,
  mode = "partial",
  onSyncProgress = null,
  onSyncComplete = null,
) => {
  let result = null;

  try {
    console.log("[bulkUpdateUsers] start", {
      count: userIds?.length ?? 0,
      mode,
      fields: Object.keys(patchData || {}),
    });

    if (!Array.isArray(userIds) || userIds.length === 0) {
      return {
        success: false,
        message: "No user IDs provided",
        summary: { requested: 0, updated: 0, failed: 0 },
        results: { success: [], failed: [] },
      };
    }

    const invalidIds = userIds.filter((id) => !isValidUUID(id));
    if (invalidIds.length > 0) {
      console.error("[bulkUpdateUsers] invalid UUIDs", {
        count: invalidIds.length,
      });
      return {
        success: false,
        message: `${invalidIds.length} invalid user ID(s) detected`,
        summary: {
          requested: userIds.length,
          updated: 0,
          failed: userIds.length,
        },
        results: {
          success: [],
          failed: invalidIds.map((id) => ({
            id,
            errors: ["Invalid UUID format"],
          })),
        },
      };
    }

    result = await api.patch(
      "/client/users/bulk-update/",
      {
        ids: userIds,
        patch: patchData,
        mode,
      },
      { profile: "bulk" },
    );

    console.log("[bulkUpdateUsers] API response received:", {
      success: result.success,
      status: result.status,
      hasData: !!result.data,
      is202: result?.data?.__is202,
    });

    // ✅ CAS 202 : Attendre le polling
    if (result?.data?.__is202) {
      console.log("[bulkUpdateUsers] 🔄 202 detected, starting polling...");

      const finalResult = await handleBulkRevalidation(
        result,
        [
          endpoints.users,
          "/client/client-accounts/",
          "/client/roles/",
          "/client/teams/",
        ],
        onSyncProgress,
        onSyncComplete,
      );

      console.log("[bulkUpdateUsers] 📥 Polling complete:", {
        hasFinalResult: !!finalResult,
        hasData: finalResult?.data !== undefined,
      });

      if (finalResult?.data) {
        console.log("[bulkUpdateUsers] ✅ Returning polling result");
        if (finalResult.data?.status === "pending") {
          console.log(
            "[bulkUpdateUsers] ⏳ Polling reached max attempts, marking operation as pending",
          );
          return {
            ...finalResult.data,
            success: false,
            status: finalResult.data.status || "pending",
            isPending: true,
          };
        }
        return finalResult.data;
      }

      if (finalResult && (finalResult.summary || finalResult.results)) {
        console.log("[bulkUpdateUsers] ✅ Returning finalResult directly");
        return finalResult;
      }

      console.error("[bulkUpdateUsers] ❌ finalResult missing data");
      return {
        success: false,
        message: "Polling completed but no result data",
        summary: {
          requested: userIds.length,
          updated: 0,
          failed: userIds.length,
        },
        results: { success: [], failed: [] },
      };
    }

    // ✅ CAS SYNC
    if (result.success) {
      console.log("[bulkUpdateUsers] ✅ Sync success", {
        status: result.status ?? 200,
        updated: result.data?.summary?.updated ?? 0,
      });

      revalidateMultiple([
        endpoints.users,
        "/client/client-accounts/",
        "/client/roles/",
        "/client/teams/",
      ]);
      return result.data;
    }

    // CAS TIMEOUT - Trigger polling (apiRequest returns, doesn't throw)
    if (result.isTimeout) {
      console.log(
        "[bulkUpdateUsers] ⏱️ Timeout detected in result, starting polling...",
      );

      const pollResult = await handleBulkTimeout(
        { idempotencyKey: result.idempotencyKey },
        [
          endpoints.users,
          "/client/client-accounts/",
          "/client/roles/",
          "/client/teams/",
        ],
        onSyncProgress,
        onSyncComplete,
      );

      if (pollResult?.status === "succeeded") {
        // Backend stores: { data: {...}, http_status: 200 }
        // We need to unwrap .data to get the actual result
        const actualResult = pollResult.result?.data || pollResult.result || {};
        return {
          success: true,
          ...actualResult,
        };
      }

      return {
        success: false,
        isTimeout: true,
        isPending: pollResult?.status === "still_running",
        message:
          pollResult?.error || "Operation may have completed in background",
        summary: { requested: userIds?.length ?? 0, updated: 0, failed: 0 },
        results: { success: [], failed: [] },
      };
    }

    // ❌ Gestion erreur
    const status = result.status || 0;
    const message = result.error || "Bulk update failed";
    console.error("[bulkUpdateUsers] api.patch error", { status, message });

    if (result.data && typeof result.data === "object") {
      if (result.data.results || result.data.summary) {
        console.log(
          "[bulkUpdateUsers] returning structured error from backend",
        );
        return {
          ...result.data,
          status: status,
          success: false,
          isTimeout: result.isTimeout || false,
        };
      }
    }

    return {
      success: false,
      isTimeout: result.isTimeout || false,
      message: message,
      error: { status, message, response: result.response || null },
      summary: {
        requested: userIds.length,
        updated: 0,
        failed: userIds.length,
      },
      results: {
        success: [],
        failed: userIds.map((id) => ({ id, errors: [message] })),
      },
    };
  } catch (err) {
    console.error("[bulkUpdateUsers] thrown", err);

    const isTimeout =
      err?.code === "ECONNABORTED" ||
      err?.message?.toLowerCase()?.includes("timeout") ||
      err?.response?.status === 408 ||
      err?.response?.status === 504;

    if (isTimeout) {
      console.log("[bulkUpdateUsers] ⏱️ Timeout detected, starting polling...");

      const pollResult = await handleBulkTimeout(
        err,
        [
          endpoints.users,
          "/client/client-accounts/",
          "/client/roles/",
          "/client/teams/",
        ],
        onSyncProgress,
        onSyncComplete,
      );

      if (pollResult?.status === "succeeded") {
        // Backend stores: { data: {...}, http_status: 200 }
        // We need to unwrap .data to get the actual result
        const actualResult = pollResult.result?.data || pollResult.result || {};
        return {
          success: true,
          ...actualResult,
        };
      }

      // Polling terminé mais pas de succès confirmé
      return {
        success: false,
        isTimeout: true,
        isPending: pollResult?.status === "still_running",
        message:
          pollResult?.error || "Operation may have completed in background",
        summary: { requested: userIds?.length ?? 0, updated: 0, failed: 0 },
        results: { success: [], failed: [] },
      };
    }

    // Autres erreurs (non-timeout)
    return {
      success: false,
      isTimeout: false,
      message: err?.message || "Unknown error",
      error: { message: err?.message || String(err) },
      summary: {
        requested: userIds?.length ?? 0,
        updated: 0,
        failed: userIds?.length ?? 0,
      },
      results: {
        success: [],
        failed: (userIds || []).map((id) => ({
          id,
          errors: [err?.message || "Unknown error"],
        })),
      },
    };
  }
};

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * ✅ REFRESH USERS LIST - Utilise les nouveaux helpers
 */
export const refreshUsers = () => revalidateByPrefix(endpoints.users);

/**
 * ✅ REFRESH CLIENT SEATS - Utilise les nouveaux helpers
 */
export const refreshClientSeats = () =>
  revalidateByPrefix("/client/client-accounts/");

/**
 * ✅ FILTER USERS - Support des filtres avec clés tenant
 */
export const filterUsers = (filters) => {
  const queryParams = new URLSearchParams(filters).toString();
  const url = `${endpoints.users}?${queryParams}`;
  return revalidateByPrefix(url);
};
