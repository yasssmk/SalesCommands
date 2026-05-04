// frontend/src/api/signals/signals.js
/**
 * API hooks and mutations for the Signals module.
 *
 * Three signal types, each with its own endpoint group:
 *   'pain'       → /module-signals/pain/
 *   'objective'  → /module-signals/objective/
 *   'tech-stack' → /module-signals/tech-stack/
 *
 * Mutations accept a `signalType` param:
 *   'pain' | 'objective' | 'tech-stack'
 *
 * Follows the same patterns as api/accounts/activities.js.
 */

import useSWR from "swr";
import { useMemo } from "react";
import { useAuth } from "hooks/useAuth";
import { api } from "utils/axiosClient";
import { tenantKey, revalidateMultiple } from "api/_swr";
import { isValidUUID } from "utils/validators";

// ==============================|| SIGNAL TYPES ||============================== //

const SIGNAL_TYPES = ["pain", "objective", "tech-stack"];

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  // Choices (shared across all signal types)
  choices: "/module-signals/choices/",

  // Pain
  pain: "/module-signals/pain/",
  painDetail: (id) => `/module-signals/pain/${id}/`,
  painValidate: (id) => `/module-signals/pain/${id}/validate/`,
  painReject: (id) => `/module-signals/pain/${id}/reject/`,

  // Objective
  objective: "/module-signals/objective/",
  objectiveDetail: (id) => `/module-signals/objective/${id}/`,
  objectiveValidate: (id) => `/module-signals/objective/${id}/validate/`,
  objectiveReject: (id) => `/module-signals/objective/${id}/reject/`,

  // Tech Stack
  techStack: "/module-signals/tech-stack/",
  techStackDetail: (id) => `/module-signals/tech-stack/${id}/`,
  techStackValidate: (id) => `/module-signals/tech-stack/${id}/validate/`,
  techStackReject: (id) => `/module-signals/tech-stack/${id}/reject/`,
};

// ==============================|| ENDPOINT HELPERS ||============================== //

/**
 * Resolve base list endpoint for a given signal type.
 *
 * @param {'pain'|'objective'|'tech-stack'} signalType
 * @returns {string} Base URL
 */
function getBaseEndpoint(signalType) {
  switch (signalType) {
    case "pain":
      return endpoints.pain;
    case "objective":
      return endpoints.objective;
    case "tech-stack":
      return endpoints.techStack;
    default:
      return null;
  }
}

/**
 * Resolve detail endpoint for a given signal type + id.
 *
 * @param {'pain'|'objective'|'tech-stack'} signalType
 * @param {string} id - Signal UUID
 * @returns {string} Detail URL
 */
function getDetailEndpoint(signalType, id) {
  switch (signalType) {
    case "pain":
      return endpoints.painDetail(id);
    case "objective":
      return endpoints.objectiveDetail(id);
    case "tech-stack":
      return endpoints.techStackDetail(id);
    default:
      return null;
  }
}

/**
 * Resolve validate endpoint for a given signal type + id.
 *
 * @param {'pain'|'objective'|'tech-stack'} signalType
 * @param {string} id - Signal UUID
 * @returns {string} Validate URL
 */
function getValidateEndpoint(signalType, id) {
  switch (signalType) {
    case "pain":
      return endpoints.painValidate(id);
    case "objective":
      return endpoints.objectiveValidate(id);
    case "tech-stack":
      return endpoints.techStackValidate(id);
    default:
      return null;
  }
}

/**
 * Resolve reject endpoint for a given signal type + id.
 *
 * @param {'pain'|'objective'|'tech-stack'} signalType
 * @param {string} id - Signal UUID
 * @returns {string} Reject URL
 */
function getRejectEndpoint(signalType, id) {
  switch (signalType) {
    case "pain":
      return endpoints.painReject(id);
    case "objective":
      return endpoints.objectiveReject(id);
    case "tech-stack":
      return endpoints.techStackReject(id);
    default:
      return null;
  }
}

/**
 * Revalidate all 3 signal list caches.
 * Called after any write that could affect any signal list.
 */
function revalidateSignalLists() {
  revalidateMultiple([
    endpoints.pain,
    endpoints.objective,
    endpoints.techStack,
  ]);
}

// ==============================|| URL BUILDER ||============================== //

/**
 * Build a list URL with query params for server-side filtering / pagination.
 *
 * Supported filters:
 *   account_id, source_activity_id, status, signal_category, source
 *
 * Note: signal_type routing is handled by the URL itself, not a query param.
 *
 * @param {string} baseUrl - Base endpoint URL
 * @param {Object} params  - { page, pageSize, search, ordering, filters }
 * @returns {string} URL with query string
 */
function buildUrlWithParams(baseUrl, params = {}) {
  const { page, pageSize, search, ordering, filters = {} } = params;

  const query = new URLSearchParams();

  if (page !== undefined && page !== null) {
    query.append("page", page);
  }
  if (pageSize !== undefined && pageSize !== null) {
    query.append("page_size", pageSize);
  }
  if (search) {
    query.append("search", search);
  }
  if (ordering) {
    query.append("ordering", ordering);
  }

  // --- signal-specific filters ---
  if (filters.account_id) {
    query.append("account", filters.account_id);
  }
  if (filters.source_activity_id) {
    query.append("source_activity", filters.source_activity_id);
  }
  if (filters.status) {
    query.append("status", filters.status);
  }
  if (filters.signal_category) {
    query.append("signal_category", filters.signal_category);
  }
  if (filters.source) {
    query.append("source", filters.source);
  }

  const qs = query.toString();
  return qs ? `${baseUrl}?${qs}` : baseUrl;
}

// ==============================|| BASE HOOK ||============================== //

/**
 * Generic SWR hook for a signal list endpoint.
 *
 * Used internally by the public convenience hooks below.
 * Not exported — callers use useGetSignalsByAccount / useGetSignalsByActivity.
 *
 * @param {'people'|'pain'|'objective'|'tech-stack'|null} signalType
 * @param {Object} options - { page, pageSize, search, ordering, filters }
 * @returns {Object} { signals, signalsCount, signalsLoading, signalsError,
 *                     signalsValidating, signalsEmpty, mutateSignals }
 */
function useGetSignals(signalType, options = {}) {
  const { tenantId } = useAuth();
  const {
    page = 1,
    pageSize = 50,
    search = "",
    ordering = "-created_at",
    filters = {},
  } = options;

  const baseUrl = signalType ? getBaseEndpoint(signalType) : null;

  const urlWithParams = useMemo(
    () =>
      baseUrl
        ? buildUrlWithParams(baseUrl, {
            page,
            pageSize,
            search,
            ordering,
            filters,
          })
        : null,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [baseUrl, page, pageSize, search, ordering, JSON.stringify(filters)],
  );

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
    () => ({
      signals: data?.data?.results ?? data?.results ?? [],
      signalsCount: data?.data?.count ?? data?.count ?? 0,
      signalsLoading: isLoading,
      signalsError: error,
      signalsValidating: isValidating,
      signalsEmpty:
        !isLoading && !(data?.data?.results?.length ?? data?.results?.length),
      mutateSignals: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );
}

// ==============================|| PUBLIC HOOKS ||============================== //

/**
 * GET SIGNALS BY ACCOUNT
 *
 * Fetches signals of a given type for a specific account.
 *
 * @param {string} accountId - Account UUID
 * @param {'pain'|'objective'|'tech-stack'} signalType
 * @param {Object} options   - { page, pageSize, search, ordering, filters }
 * @returns {Object} { signals, signalsCount, signalsLoading, signalsError,
 *                     signalsValidating, signalsEmpty, mutateSignals }
 */
export function useGetSignalsByAccount(accountId, signalType, options = {}) {
  const enabled = Boolean(accountId && isValidUUID(accountId));

  const mergedOptions = useMemo(
    () => ({
      ...options,
      filters: {
        ...options.filters,
        account_id: enabled ? accountId : undefined,
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [accountId, enabled, JSON.stringify(options)],
  );

  return useGetSignals(enabled ? signalType : null, mergedOptions);
}

/**
 * GET SIGNALS BY ACTIVITY
 *
 * Fetches signals of a given type linked to a specific source activity.
 *
 * @param {string} activityId - Activity UUID
 * @param {'pain'|'objective'|'tech-stack'} signalType
 * @param {Object} options    - { page, pageSize, search, ordering, filters }
 * @returns {Object} { signals, signalsCount, signalsLoading, signalsError,
 *                     signalsValidating, signalsEmpty, mutateSignals }
 */
export function useGetSignalsByActivity(activityId, signalType, options = {}) {
  const enabled = Boolean(activityId && isValidUUID(activityId));

  const mergedOptions = useMemo(
    () => ({
      ...options,
      filters: {
        ...options.filters,
        source_activity_id: enabled ? activityId : undefined,
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activityId, enabled, JSON.stringify(options)],
  );

  return useGetSignals(enabled ? signalType : null, mergedOptions);
}

/**
 * GET SIGNAL CHOICES
 *
 * Fetches all enum choices for signal forms.
 *
 * Response shape (from backend):
 * {
 *   status:            [...],   // SignalStatus    (lifecycle shared by all types)
 *   source:            [...],   // SignalSource    (MANUAL / LLM_* / EXTERNAL_RESEARCH)
 *   signal_category:   [...],   // SignalCategory  (legacy, being deprecated)
 *   signal_whats:      [...],   // SignalWhat      (1st axis of canonical_key —
 *                                                   shared Pain + Objective)
 *   signal_dimensions: [...],   // SignalDimension (2nd axis of canonical_key —
 *                                                   same shared scope)
 *   human_impacts:     [...],   // HumanImpact     (orthogonal axis on PainImpact)
 *   scope_levels:      [...],   // ScopeLevel      (BUSINESS / DEPARTMENT /
 *                                                   PERSONAL — drives PainImpact
 *                                                   scope and ObjectiveSignal
 *                                                   scope_level)
 *   usage_scopes:      [...],   // UsageScope      (TechStackSignal — TEAM /
 *                                                   DEPARTMENT / COMPANY / UNKNOWN)
 * }
 *
 * Notes:
 *   - signal_whats × signal_dimensions form the canonical_key
 *     "pain:<what>:<dimension>" on PainSignal and
 *     "objective:<what>:<dimension>" on ObjectiveSignal. See
 *     InlinePainForm / InlineObjectiveForm for rendering.
 *   - scope_levels drives PainImpact creation — see AddPainImpactDialog.
 *
 * Wave A renames (destructive, no back-compat):
 *   - pain_whats      → signal_whats
 *   - pain_dimensions → signal_dimensions
 *   - impact_levels   → scope_levels
 *   - goal_levels     → removed (Objective adopts scope_levels since Wave B)
 *
 * Sprint TechStack changes:
 *   - tech_categories → removed (TechCategory enum dropped)
 *   - satisfaction    → removed (Satisfaction enum dropped)
 *   - usage_scopes    → added (drives conditional usage_department on
 *                              TechStackSignal)
 *
 * Sprint 2 removals (PeopleSignal sunset):
 *   - people_roles     → removed
 *   - influence_levels → removed
 *
 * @returns {Object} { choices, choicesLoading, choicesError, mutateChoices }
 */

export function useGetSignalChoices() {
  const { tenantId } = useAuth();

  const swrKey = tenantKey(endpoints.choices, tenantId);

  const { data, isLoading, error, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    dedupingInterval: 300_000,
    shouldRetryOnError: false,
  });

  return useMemo(
    () => ({
      choices: data?.data ?? null,
      choicesLoading: isLoading,
      choicesError: error,
      mutateChoices: mutate,
    }),
    [data, isLoading, error, mutate],
  );
}

// ==============================|| MUTATIONS ||============================== //

/**
 * CREATE SIGNAL
 *
 * POST /module-signals/{signalType}/
 *
 * @param {'people'|'pain'|'objective'|'tech-stack'} signalType
 * @param {Object} payload - Signal creation payload
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function createSignal(signalType, payload) {
  const url = getBaseEndpoint(signalType);
  const result = await api.post(url, payload);

  if (result.success) {
    revalidateSignalLists();
    const data = result.data?.data ?? result.data;
    return { success: true, data };
  }

  return {
    success: false,
    error: result.error,
    status: result.status ?? 0,
    response: result.response ?? null,
  };
}

/**
 * UPDATE SIGNAL (PATCH)
 *
 * PATCH /module-signals/{signalType}/{id}/
 *
 * @param {'people'|'pain'|'objective'|'tech-stack'} signalType
 * @param {string} signalId - Signal UUID
 * @param {Object} payload  - Partial update payload
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function updateSignal(signalType, signalId, payload) {
  if (!signalId || !isValidUUID(signalId)) {
    return { success: false, error: "Invalid signal ID format", status: 400 };
  }

  const url = getDetailEndpoint(signalType, signalId);
  const result = await api.patch(url, payload);

  if (result.success) {
    revalidateSignalLists();
    const data = result.data?.data ?? result.data;
    return { success: true, data };
  }

  return {
    success: false,
    error: result.error,
    status: result.status ?? 0,
    response: result.response ?? null,
  };
}

/**
 * DELETE SIGNAL
 *
 * DELETE /module-signals/{signalType}/{id}/
 *
 * @param {'people'|'pain'|'objective'|'tech-stack'} signalType
 * @param {string} signalId - Signal UUID
 * @returns {Promise<{success: boolean, status?: number, error?: string}>}
 */
export async function deleteSignal(signalType, signalId) {
  if (!signalId || !isValidUUID(signalId)) {
    return { success: false, error: "Invalid signal ID format", status: 400 };
  }

  const url = getDetailEndpoint(signalType, signalId);
  const result = await api.delete(url);

  if (result.success || result.status === 204) {
    revalidateSignalLists();
    return { success: true, status: result.status ?? 204 };
  }

  return {
    success: false,
    error: result.error,
    status: result.status ?? 0,
    response: result.response ?? null,
  };
}

/**
 * VALIDATE SIGNAL
 *
 * POST /module-signals/{signalType}/{id}/validate/
 * Transitions signal from PENDING → VALIDATED.
 *
 * @param {'people'|'pain'|'objective'|'tech-stack'} signalType
 * @param {string} signalId - Signal UUID
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function validateSignal(signalType, signalId) {
  if (!signalId || !isValidUUID(signalId)) {
    return { success: false, error: "Invalid signal ID format", status: 400 };
  }

  const url = getValidateEndpoint(signalType, signalId);
  const result = await api.post(url, {});

  if (result.success) {
    revalidateSignalLists();
    const data = result.data?.data ?? result.data;
    return { success: true, data };
  }

  return {
    success: false,
    error: result.error,
    status: result.status ?? 0,
    response: result.response ?? null,
  };
}

/**
 * REJECT SIGNAL
 *
 * POST /module-signals/{signalType}/{id}/reject/
 * Body (optional): { reason: string }
 *
 * @param {'people'|'pain'|'objective'|'tech-stack'} signalType
 * @param {string} signalId    - Signal UUID
 * @param {string|null} reason - Optional rejection reason
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function rejectSignal(signalType, signalId, reason = null) {
  if (!signalId || !isValidUUID(signalId)) {
    return { success: false, error: "Invalid signal ID format", status: 400 };
  }

  const url = getRejectEndpoint(signalType, signalId);
  const payload = reason ? { reason } : {};
  const result = await api.post(url, payload);

  if (result.success) {
    revalidateSignalLists();
    const data = result.data?.data ?? result.data;
    return { success: true, data };
  }

  return {
    success: false,
    error: result.error,
    status: result.status ?? 0,
    response: result.response ?? null,
  };
}
