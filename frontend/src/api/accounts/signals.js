// frontend/src/api/accounts/signals.js
/**
 * API hooks and mutations for the Signals module.
 *
 * Two signal types share the same URL structure:
 *   /module-signals/qualification/   → QualificationSignal
 *   /module-signals/tech-stack/      → TechStackSignal
 *
 * Mutations accept a `signalType` param ('qualification' | 'tech-stack')
 * to resolve the correct endpoint prefix.
 *
 * Follows the same patterns as api/accounts/activities.js.
 */

import useSWR from "swr";
import { useMemo } from "react";
import { useAuth } from "hooks/useAuth";
import { api } from "utils/axiosClient";
import { tenantKey, revalidateMultiple } from "api/_swr";
import { isValidUUID } from "utils/validators";

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  // Choices (shared across signal types)
  choices: "/module-signals/choices/",

  // Qualification
  qualification: "/module-signals/qualification/",
  qualificationDetail: (id) => `/module-signals/qualification/${id}/`,
  qualificationValidate: (id) =>
    `/module-signals/qualification/${id}/validate/`,
  qualificationReject: (id) => `/module-signals/qualification/${id}/reject/`,
  qualificationMerge: (id) => `/module-signals/qualification/${id}/merge/`,
  qualificationSupersede: (id) =>
    `/module-signals/qualification/${id}/supersede/`,

  // Tech Stack
  techStack: "/module-signals/tech-stack/",
  techStackDetail: (id) => `/module-signals/tech-stack/${id}/`,
  techStackValidate: (id) => `/module-signals/tech-stack/${id}/validate/`,
  techStackReject: (id) => `/module-signals/tech-stack/${id}/reject/`,
  techStackMerge: (id) => `/module-signals/tech-stack/${id}/merge/`,
  techStackSupersede: (id) => `/module-signals/tech-stack/${id}/supersede/`,
};

// ==============================|| ENDPOINT HELPERS ||============================== //

/**
 * Resolve base list endpoint for a given signal type.
 *
 * @param {'qualification'|'tech-stack'} signalType
 * @returns {string} Base URL
 */
function getBaseEndpoint(signalType) {
  return signalType === "tech-stack"
    ? endpoints.techStack
    : endpoints.qualification;
}

/**
 * Resolve detail endpoint for a given signal type + id.
 *
 * @param {'qualification'|'tech-stack'} signalType
 * @param {string} id - Signal UUID
 * @returns {string} Detail URL
 */
function getDetailEndpoint(signalType, id) {
  return signalType === "tech-stack"
    ? endpoints.techStackDetail(id)
    : endpoints.qualificationDetail(id);
}

/**
 * Resolve action endpoint (validate / reject / merge / supersede).
 *
 * @param {'qualification'|'tech-stack'} signalType
 * @param {string} id - Signal UUID
 * @param {'validate'|'reject'|'merge'|'supersede'} action
 * @returns {string} Action URL
 */
function getActionEndpoint(signalType, id, action) {
  const map = {
    qualification: {
      validate: endpoints.qualificationValidate(id),
      reject: endpoints.qualificationReject(id),
      merge: endpoints.qualificationMerge(id),
      supersede: endpoints.qualificationSupersede(id),
    },
    "tech-stack": {
      validate: endpoints.techStackValidate(id),
      reject: endpoints.techStackReject(id),
      merge: endpoints.techStackMerge(id),
      supersede: endpoints.techStackSupersede(id),
    },
  };

  return map[signalType]?.[action] ?? null;
}

/**
 * Revalidate all list caches for both signal types.
 * Called after any write that could affect either list.
 */
function revalidateSignalLists() {
  revalidateMultiple([endpoints.qualification, endpoints.techStack]);
}

// ==============================|| URL BUILDER ||============================== //

/**
 * Build a list URL with query params for server-side filtering / pagination.
 *
 * Supported filters:
 *   account_id, source_activity_id, status, field_name,
 *   signal_category, source
 *
 * @param {string} baseUrl   - Base endpoint URL
 * @param {Object} params    - { page, pageSize, search, ordering, filters }
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
    query.append("account_id", filters.account_id);
  }
  if (filters.source_activity_id) {
    query.append("source_activity", filters.source_activity_id);
  }
  if (filters.status) {
    query.append("status", filters.status);
  }
  if (filters.field_name) {
    query.append("field_name", filters.field_name);
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
 * @param {'qualification'|'tech-stack'} signalType
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

  const baseUrl = getBaseEndpoint(signalType);

  const urlWithParams = useMemo(
    () =>
      buildUrlWithParams(baseUrl, {
        page,
        pageSize,
        search,
        ordering,
        filters,
      }),
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
 * @param {string} accountId   - Account UUID
 * @param {'qualification'|'tech-stack'} signalType
 * @param {Object} options     - { page, pageSize, search, ordering, filters }
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
 * @param {string} activityId  - Activity UUID
 * @param {'qualification'|'tech-stack'} signalType
 * @param {Object} options     - { page, pageSize, search, ordering, filters }
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
 * Returns frontend-ready choice lists for status, source, signal_category,
 * qualification_fields, and tech_stack_fields.
 *
 * Response shape:
 * {
 *   status:               [{ value, label }, ...],
 *   source:               [...],
 *   signal_category:      [...],
 *   qualification_fields: [...],
 *   tech_stack_fields:    [...],
 * }
 *
 * @returns {Object} { choices, choicesLoading, choicesError, mutateChoices }
 */
export function useGetSignalChoices() {
  const { tenantId } = useAuth();

  const swrKey = tenantKey(endpoints.choices, tenantId);

  const { data, isLoading, error, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    // Choices are stable — long cache, no retry noise
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
 * @param {'qualification'|'tech-stack'} signalType
 * @param {Object} payload - Signal creation payload (see BaseSignalCreateSerializer)
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
 * Allowed fields: value, signal_category, source_department,
 *                 source_contact, source_quote, metadata.
 *
 * @param {'qualification'|'tech-stack'} signalType
 * @param {string} signalId  - Signal UUID
 * @param {Object} payload   - Partial update payload
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
 * @param {'qualification'|'tech-stack'} signalType
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
 * @param {'qualification'|'tech-stack'} signalType
 * @param {string} signalId - Signal UUID
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function validateSignal(signalType, signalId) {
  if (!signalId || !isValidUUID(signalId)) {
    return { success: false, error: "Invalid signal ID format", status: 400 };
  }

  const url = getActionEndpoint(signalType, signalId, "validate");
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
 * @param {'qualification'|'tech-stack'} signalType
 * @param {string} signalId    - Signal UUID
 * @param {string|null} reason - Optional rejection reason
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function rejectSignal(signalType, signalId, reason = null) {
  if (!signalId || !isValidUUID(signalId)) {
    return { success: false, error: "Invalid signal ID format", status: 400 };
  }

  const url = getActionEndpoint(signalType, signalId, "reject");
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

/**
 * MERGE SIGNAL
 *
 * POST /module-signals/{signalType}/{id}/merge/
 * Body: { target_signal_id: string }
 *
 * Source signal is merged into target signal.
 * Both must be the same type and field_name.
 *
 * @param {'qualification'|'tech-stack'} signalType
 * @param {string} signalId       - Source signal UUID
 * @param {string} targetSignalId - Target signal UUID
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function mergeSignal(signalType, signalId, targetSignalId) {
  if (!signalId || !isValidUUID(signalId)) {
    return { success: false, error: "Invalid signal ID format", status: 400 };
  }
  if (!targetSignalId || !isValidUUID(targetSignalId)) {
    return {
      success: false,
      error: "Invalid target signal ID format",
      status: 400,
    };
  }

  const url = getActionEndpoint(signalType, signalId, "merge");
  const result = await api.post(url, { target_signal_id: targetSignalId });

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
 * SUPERSEDE SIGNAL
 *
 * POST /module-signals/{signalType}/{id}/supersede/
 * Body: { new_data: { <same shape as create payload> } }
 *
 * Marks the existing signal as superseded and creates a replacement.
 *
 * @param {'qualification'|'tech-stack'} signalType
 * @param {string} signalId  - Signal UUID to supersede
 * @param {Object} newData   - Create payload for the replacement signal
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function supersedeSignal(signalType, signalId, newData) {
  if (!signalId || !isValidUUID(signalId)) {
    return { success: false, error: "Invalid signal ID format", status: 400 };
  }

  const url = getActionEndpoint(signalType, signalId, "supersede");
  const result = await api.post(url, { new_data: newData });

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
