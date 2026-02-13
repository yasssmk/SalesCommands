// frontend/src/api/accounts/decisionCycles.js
/**
 * API hooks and mutations for Decision Cycles module.
 * 
 * Follows the same patterns as territories.js for consistency.
 */

import useSWR, { mutate }from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey, revalidateMultiple } from 'api/_swr';
import { isValidUUID, sanitizeObject } from 'utils/validators';

// ==============================|| CONSTANTS ||============================== //
/**
 * Pipeline Steps (matching backend PipelineStep choices)
 * 
 * These are FIXED steps auto-created with each Decision Cycle (5 steps).
 * Users CANNOT create/delete steps - only add activities within them.
 * 
 * Note: IMPLEMENTATION and GO_LIVE still exist in backend enum for
 * backward compatibility with existing cycles, but are NOT auto-created.
 */
export const PIPELINE_STEPS = {
  QUALIFICATION: 'QUALIFICATION',
  TECHNICAL_FIT: 'TECHNICAL_FIT',
  SOLUTION_VALIDATION: 'SOLUTION_VALIDATION',
  BUSINESS_CASE: 'BUSINESS_CASE',
  CLOSING: 'CLOSING'
};
// Legacy alias for backward compatibility
export const DECISION_STAGES = PIPELINE_STEPS;

/**
 * Decision step statuses (matching backend DecisionStepStatus choices)
 * 
 * Status is 100% DERIVED from activities by StepStatusDerivationService.
 * No manual status changes — status reflects observable reality.
 * 
 * Derivation priority (highest first):
 * 1. OVERDUE     — step deadline passed OR any PLANNED activity past scheduled/due date
 * 2. VALIDATED   — ALL completed (0 PLANNED) + later step has activities
 * 3. IN_PROGRESS — at least 1 PLANNED activity exists
 * 4. STALLED     — completed exist, no PLANNED, no later step activity, last completed step
 * 5. NOT_STARTED — no activities (or all cancelled)
 * 
 * IN_CHASING: Reserved for future Campaign/Sequence feature.
 * 
 * WON/REJECTED/ON_HOLD removed — now handled at cycle level via CycleOutcome.
 */
export const DECISION_STEP_STATUSES = {
  NOT_STARTED: 'NOT_STARTED',
  IN_PROGRESS: 'IN_PROGRESS',
  STALLED: 'STALLED',
  IN_CHASING: 'IN_CHASING',
  OVERDUE: 'OVERDUE',
  VALIDATED: 'VALIDATED'
};

/**
 * Status colors for MUI Chip color prop (generic palette keys).
 */
export const STATUS_COLORS = {
  OVERDUE: 'error',
  VALIDATED: 'primary',
  IN_PROGRESS: 'secondary',
  STALLED: 'error',
  IN_CHASING: 'warning',
  NOT_STARTED: 'default'
};

/**
 * Status → MUI theme token mapping.
 * Used for fine-grained styling: borders, backgrounds, custom sx.
 */
export const STATUS_THEME_TOKENS = {
  OVERDUE: 'error.light',
  VALIDATED: 'primary.dark',
  IN_PROGRESS: 'primary.light',
  STALLED: 'warning.light',
  IN_CHASING: 'warning.dark',
  NOT_STARTED: 'secondary.light'
};

/**
 * Step status labels for UI display.
 * Backend also returns derived_status_display — prefer that when available.
 */
export const STATUS_LABELS = {
  OVERDUE: 'Overdue',
  VALIDATED: 'Validated',
  IN_PROGRESS: 'In Progress',
  STALLED: 'Stalled',
  IN_CHASING: 'In Chasing',
  NOT_STARTED: 'Not Started'
};


/**
 * Pipeline steps order for display (left to right)
 * 5 auto-created steps: QUALIFICATION → CLOSING
 */
export const PIPELINE_STEPS_ORDER = [
  'QUALIFICATION',
  'TECHNICAL_FIT',
  'SOLUTION_VALIDATION',
  'BUSINESS_CASE',
  'CLOSING'
];

// Legacy alias for backward compatibility
export const STAGE_ORDER = PIPELINE_STEPS_ORDER;

/**
 * Pipeline step labels for UI display
 */
export const PIPELINE_STEP_LABELS = {
  QUALIFICATION: 'Qualification',
  TECHNICAL_FIT: 'Technical Fit',
  SOLUTION_VALIDATION: 'Solution Validation',
  BUSINESS_CASE: 'Business Case',
  CLOSING: 'Closing'
};

// Legacy alias for backward compatibility
export const STAGE_LABELS = PIPELINE_STEP_LABELS;

/**
 * Pipeline step configuration
 * 
 * All 5 steps require activities (no activity_optional steps).
 * description: Short description of what happens in this step
 */
export const PIPELINE_STEP_CONFIG = {
  QUALIFICATION: {
    order: 1,
    activity_optional: false,
    description: 'Identify needs and validate opportunity fit'
  },
  TECHNICAL_FIT: {
    order: 2,
    activity_optional: false,
    description: 'Validate technical and operational requirements'
  },
  SOLUTION_VALIDATION: {
    order: 3,
    activity_optional: false,
    description: 'Confirm solution meets buyer criteria'
  },
  BUSINESS_CASE: {
    order: 4,
    activity_optional: false,
    description: 'Secure budget and business approval'
  },
  CLOSING: {
    order: 5,
    activity_optional: false,
    description: 'Finalize contract and legal terms'
  }
};

/**
 * Derived cycle statuses (from CycleAggregationService)
 * 
 * Two-layer architecture:
 * - cycle.outcome (explicit): WON / LOST / ON_HOLD / NOT_QUALIFIED → overrides all
 * - cycle.cycle_status (derived): computed from step statuses when outcome is null
 */
export const CYCLE_DERIVED_STATUS = {
  NOT_STARTED: 'NOT_STARTED',
  IN_PROGRESS: 'IN_PROGRESS',
  OVERDUE: 'OVERDUE',
  STALLED: 'STALLED',
  WON: 'WON',
  LOST: 'LOST',
  ON_HOLD: 'ON_HOLD',
  NOT_QUALIFIED: 'NOT_QUALIFIED'
};

/**
 * Cycle derived status labels for UI display
 */
export const CYCLE_DERIVED_STATUS_LABELS = {
  NOT_STARTED: 'Not Started',
  IN_PROGRESS: 'In Progress',
  OVERDUE: 'Overdue',
  STALLED: 'Stalled',
  WON: 'Won',
  LOST: 'Lost',
  ON_HOLD: 'On Hold',
  NOT_QUALIFIED: 'Not Qualified'
};

/**
 * Cycle derived status colors for MUI Chip color prop
 */
export const CYCLE_STATUS_COLORS = {
  NOT_STARTED: 'default',
  IN_PROGRESS: 'info',
  OVERDUE: 'error',
  STALLED: 'warning',
  WON: 'success',
  LOST: 'error',
  ON_HOLD: 'warning',
  NOT_QUALIFIED: 'default'
};

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  // Decision Cycles
  cycles: '/decision_cycles/',
  cycleDetail: (id) => `/decision_cycles/${id}/`,
  cyclesByAccount: (accountId) => `/decision_cycles/by-account/${accountId}/`,
  choices: '/decision_cycles/choices/',
  closeCycle: (id) => `/decision_cycles/${id}/close/`,
  reopenCycle: (id) => `/decision_cycles/${id}/reopen/`,
  
  // Decision Steps
  steps: '/decision_cycles/steps/',
  stepDetail: (id) => `/decision_cycles/steps/${id}/`,
  stepStatus: (id) => `/decision_cycles/steps/${id}/status/`
};

// ==============================|| HELPER - BUILD URL WITH PARAMS ||============================== //

/**
 * Build URL with query params for server-side pagination/filtering
 */
const buildUrlWithParams = (baseUrl, params = {}) => {
  const { page, pageSize, search, ordering, filters = {} } = params;
  const queryParams = new URLSearchParams();
  
  if (page !== undefined && page !== null) {
    queryParams.append('page', page);
  }
  
  if (pageSize !== undefined && pageSize !== null) {
    queryParams.append('page_size', pageSize);
  }
  
  if (search !== undefined && search !== null && search !== '') {
    queryParams.append('search', search);
  }

  if (ordering !== undefined && ordering !== null && ordering !== '') {
    queryParams.append('ordering', ordering);
  }

  // Filters
  if (filters.account) {
    queryParams.append('account', filters.account);
  }
  
  if (filters.is_active !== undefined) {
    queryParams.append('is_active', filters.is_active);
  }

  if (filters.cycle_id) {
    queryParams.append('cycle', filters.cycle_id);
  }

  if (filters.stage) {
    queryParams.append('stage', filters.stage);
  }

  if (filters.status) {
    queryParams.append('status', filters.status);
  }
  
  const queryString = queryParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

// ==============================|| DECISION CYCLE HOOKS ||============================== //

/**
 * GET DECISION CYCLES - Paginated list with filters
 * 
 * @param {Object} options - {page, pageSize, search, ordering, filters}
 * @returns {Object} {cycles, cyclesCount, cyclesLoading, cyclesError, cyclesValidating, cyclesEmpty}
 */
export function useGetDecisionCycles(options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 50, search = '', ordering = '', filters = {} } = options;

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.cycles, { page, pageSize, search, ordering, filters });
  }, [page, pageSize, search, ordering, filters]);

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      cycles: data?.data?.results || data?.results || [],
      cyclesCount: data?.data?.count || data?.count || 0,
      cyclesLoading: isLoading,
      cyclesError: error,
      cyclesValidating: isValidating,
      cyclesEmpty: !isLoading && !(data?.data?.results?.length || data?.results?.length)
    }),
    [data, isLoading, error, isValidating]
  );

  return memoizedValue;
}

/**
 * GET DECISION CYCLE - Single cycle details with steps
 * 
 * @param {string} cycleId - UUID of the cycle
 * @returns {Object} {cycle, cycleLoading, cycleError, cycleValidating, mutateCycle}
 */
export function useGetDecisionCycle(cycleId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!cycleId || !isValidUUID(cycleId)) return null;
    return tenantKey(endpoints.cycleDetail(cycleId), tenantId);
  }, [cycleId, tenantId]);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      cycle: data?.data || null,
      cycleLoading: isLoading,
      cycleError: error,
      cycleValidating: isValidating,
      mutateCycle: mutate
    }),
    [data, isLoading, error, isValidating, mutate]
  );

  return memoizedValue;
}

/**
 * GET DECISION CYCLES BY ACCOUNT - All cycles for a specific account
 * 
 * @param {string} accountId - UUID of the account
 * @returns {Object} {cycles, cyclesLoading, cyclesError, mutateCycles}
 */
export function useGetDecisionCyclesByAccount(accountId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!accountId || !isValidUUID(accountId)) return null;
    return tenantKey(endpoints.cyclesByAccount(accountId), tenantId);
  }, [accountId, tenantId]);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
    // Performance: prevent redundant fetches on fast tab round-trips
    // SWR deduplicates requests with the same key within this window
    dedupingInterval: 10000,
    // Show stale data instantly while revalidating in background
    // Avoids loading skeleton flash on tab switch
    keepPreviousData: true,
  });

  const memoizedValue = useMemo(
    () => ({
      cycles: data?.data?.results || [],
      cyclesCount: data?.data?.count || 0,
      cyclesLoading: isLoading,
      cyclesError: error,
      cyclesValidating: isValidating,
      mutateCycles: mutate
    }),
    [data, isLoading, error, isValidating, mutate]
  );

  return memoizedValue;
}

/**
 * GET DECISION CYCLE CHOICES - Stages and statuses for dropdowns
 * 
 * @returns {Object} {choices, stages, statuses, choicesLoading, choicesError}
 */
export function useGetDecisionCycleChoices() {
  const { tenantId } = useAuth();

  const swrKey = tenantKey(endpoints.choices, tenantId);

  const { data, isLoading, error } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      choices: data?.data || {},
      stages: data?.data?.stages || [],
      statuses: data?.data?.statuses || [],
      choicesLoading: isLoading,
      choicesError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

// ==============================|| DECISION STEP HOOKS ||============================== //

/**
 * GET DECISION STEPS - List steps with filters
 * 
 * @param {Object} options - {page, pageSize, search, ordering, filters}
 * @returns {Object} {steps, stepsCount, stepsLoading, stepsError}
 */
export function useGetDecisionSteps(options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 100, search = '', ordering = '', filters = {} } = options;

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.steps, { page, pageSize, search, ordering, filters });
  }, [page, pageSize, search, ordering, filters]);

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      steps: data?.data?.results || data?.results || [],
      stepsCount: data?.data?.count || data?.count || 0,
      stepsLoading: isLoading,
      stepsError: error,
      stepsValidating: isValidating,
      mutateSteps: mutate
    }),
    [data, isLoading, error, isValidating, mutate]
  );

  return memoizedValue;
}

/**
 * GET DECISION STEPS BY CYCLE - All steps for a specific cycle
 * 
 * Lightweight hook for fetching steps linked to a decision cycle.
 * Used by ActivityOutcomeTab to display existing steps.
 * 
 * @param {string} cycleId - UUID of the decision cycle
 * @returns {Object} {steps, stepsCount, stepsLoading, stepsError, stepsEmpty, mutateSteps}
 */
export function useGetDecisionStepsByCycle(cycleId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!cycleId || !isValidUUID(cycleId)) return null;
    const url = `${endpoints.steps}?cycle_id=${cycleId}`;
    return tenantKey(url, tenantId);
  }, [cycleId, tenantId]);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      steps: data?.data?.results || data?.results || [],
      stepsCount: data?.data?.count || data?.count || 0,
      stepsLoading: isLoading,
      stepsError: error,
      stepsValidating: isValidating,
      stepsEmpty: !isLoading && !(data?.data?.results?.length || data?.results?.length),
      mutateSteps: mutate
    }),
    [data, isLoading, error, isValidating, mutate]
  );

  return memoizedValue;
}


/**
 * GET DECISION STEP WITH CONTEXT - Step details with cycle + account for workspace
 * 
 * Use this hook ONLY for workspace pages that need breadcrumbs,
 * cycle name, and account context. Makes 2 SWR calls (step + cycle).
 * 
 * For modals or lightweight displays, use useGetDecisionStep instead.
 * 
 * Returns convenience getters (cycleName, accountName, accountId, etc.)
 * derived from the cycle's account relationship.
 * 
 * @param {string} stepId - UUID of the step
 * @returns {Object} {step, cycle, account, stepLoading, stepError, stepValidating, mutateStep, ...convenience}
 */
export function useGetDecisionStepWithContext(stepId) {
  const { tenantId } = useAuth();

  // Fetch step detail
  const stepSwrKey = useMemo(() => {
    if (!stepId || !isValidUUID(stepId)) return null;
    return tenantKey(endpoints.stepDetail(stepId), tenantId);
  }, [stepId, tenantId]);

  const { 
    data: stepData, 
    isLoading: stepLoading, 
    error: stepError, 
    isValidating: stepValidating, 
    mutate: mutateStep 
  } = useSWR(stepSwrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const step = stepData?.data || null;

  // Extract cycle ID from step to fetch cycle details
  const cycleId = step?.cycle_id || step?.cycle?.id || step?.cycle;

  // Fetch cycle detail (for account info and cycle name)
  const cycleSwrKey = useMemo(() => {
    if (!cycleId || !isValidUUID(cycleId)) return null;
    return tenantKey(endpoints.cycleDetail(cycleId), tenantId);
  }, [cycleId, tenantId]);

  const { 
    data: cycleData, 
    isLoading: cycleLoading 
  } = useSWR(cycleSwrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const cycle = cycleData?.data || null;

  // Derive account from cycle or step
  const account = useMemo(() => {
    // Priority 1: cycle.account (most reliable — cycle always has account)
    if (cycle?.account) {
      return typeof cycle.account === 'object' 
        ? cycle.account 
        : { id: cycle.account, name: cycle.account_name || '' };
    }
    
    // Priority 2: step.account_id (available if backend includes it)
    if (step?.account_id) {
      return { id: step.account_id, name: step.account_name || '' };
    }
    
    return null;
  }, [cycle, step]);

  // Loading = step loading OR waiting for cycle (only if cycleId is known)
  const isLoading = stepLoading || (cycleId && cycleLoading);

  const memoizedValue = useMemo(
    () => ({
      // Step data with completeness
      step,
      completenessScore: step?.completeness_score ?? null,
      completenessDetails: step?.completeness_details ?? null,
      
      // Related entities
      cycle,
      account,
      
      // Loading states
      stepLoading: isLoading,
      stepError,
      stepValidating,
      
      // Mutation
      mutateStep,
      
      // Convenience getters
      stepName: step?.name || '',
      cycleName: cycle?.name || '',
      accountName: account?.name || '',
      accountId: account?.id || cycle?.account_id || cycle?.account || null,
      stageName: step?.stage ? (STAGE_LABELS[step.stage] || step.stage) : '',
      statusName: step?.derived_status_display || (step?.derived_status ? (STATUS_LABELS[step.derived_status] || step.derived_status) : '')
    }),
    [step, cycle, account, isLoading, stepError, stepValidating, mutateStep]
  );

  return memoizedValue;
}

/**
 * GET STEP CONTACTS - Contacts linked to a decision step
 * 
 * @param {string} stepId - UUID of the step
 * @returns {Object} {contacts, contactsLoading, contactsError, mutateContacts}
 */
export function useGetDecisionStepContacts(stepId) {
  const { tenantId } = useAuth();

  // For now, contacts come with the step detail
  // This hook is a placeholder for when we have a dedicated endpoint
  const { step, stepLoading, stepError, mutateStep } = useGetDecisionStep(stepId);

  const memoizedValue = useMemo(
    () => ({
      contacts: step?.contacts || [],
      contactsCount: step?.contacts?.length || 0,
      contactsLoading: stepLoading,
      contactsError: stepError,
      mutateContacts: mutateStep
    }),
    [step, stepLoading, stepError, mutateStep]
  );

  return memoizedValue;
}



/**
 * GET DECISION STEP - Single step details (lightweight)
 * 
 * Use this hook for modals, inline displays, and any context where
 * only step data is needed (no cycle name, no account breadcrumb).
 * 
 * For workspace pages that need cycle + account context (breadcrumbs,
 * navigation), use useGetDecisionStepWithContext instead.
 * 
 * @param {string} stepId - UUID of the step
 * @returns {Object} {step, stepLoading, stepError, stepValidating, mutateStep}
 */
export function useGetDecisionStep(stepId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!stepId || !isValidUUID(stepId)) return null;
    return tenantKey(endpoints.stepDetail(stepId), tenantId);
  }, [stepId, tenantId]);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      step: data?.data || null,
      stepLoading: isLoading,
      stepError: error,
      stepValidating: isValidating,
      mutateStep: mutate
    }),
    [data, isLoading, error, isValidating, mutate]
  );

  return memoizedValue;
}

// ==============================|| DECISION CYCLE MUTATIONS ||============================== //

/**
 * CREATE DECISION CYCLE
 * 
 * @param {Object} payload - {account_id, name, description, is_active}
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function createDecisionCycle(payload) {
  const sanitized = sanitizeObject(payload, ['name', 'description']);
  
  const result = await api.post(endpoints.cycles, sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.cycles,
      endpoints.cyclesByAccount(payload.account_id),
      '/company-accounts/'
    ]);
    // Extract nested data from backend response { success, data }
    const cycleData = result.data?.data || result.data;
    return { success: true, data: cycleData };
  }
    
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * UPDATE DECISION CYCLE
 * 
 * @param {string} cycleId - UUID of the cycle
 * @param {Object} payload - Cycle data to update
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function updateDecisionCycle(cycleId, payload) {
  if (!cycleId || !isValidUUID(cycleId)) {
    return {
      success: false,
      error: 'Invalid cycle ID format',
      status: 400
    };
  }
  
  const sanitized = sanitizeObject(payload, ['name', 'description']);
  
  const result = await api.patch(endpoints.cycleDetail(cycleId), sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.cycles,
      endpoints.cycleDetail(cycleId),
      '/company-accounts/',
      '/decision_cycles/by-account/'
    ]);
    // Extract nested data from backend response { success, data }
    const cycleData = result.data?.data || result.data;
    return { success: true, data: cycleData };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * DELETE DECISION CYCLE
 * 
 * @param {string} cycleId - UUID of the cycle
 * @param {string} accountId - UUID of the account (for cache invalidation)
 * @returns {Promise<Object>} {success: boolean, status?: number, error?: string}
 */
export async function deleteDecisionCycle(cycleId) {
  if (!cycleId || !isValidUUID(cycleId)) {
    return {
      success: false,
      error: 'Invalid cycle ID format',
      status: 400
    };
  }
  
  const result = await api.delete(endpoints.cycleDetail(cycleId));
  
  if (result.success || result.status === 204) {
    // Clear the deleted cycle and its steps from cache (don't refetch - it's gone)
    mutate(
      (key) => {
        const url = Array.isArray(key) ? key[0] : key;
        if (typeof url === 'string') {
          // Match cycle detail
          if (url.includes(`/decision_cycles/${cycleId}`)) return true;
          // Match steps by cycle_id
          if (url.includes(`cycle_id=${cycleId}`)) return true;
        }
        return false;
      },
      undefined,
      { revalidate: false }
    );
    
    // NOTE: Don't revalidate here - let the caller do it AFTER updating selection state
    return { success: true, status: result.status ?? 204, cycleId };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * CLOSE DECISION CYCLE
 * 
 * Sets explicit outcome on a cycle (WON / LOST / ON_HOLD / NOT_QUALIFIED).
 * Terminal outcomes (WON/LOST/NOT_QUALIFIED) auto-cancel all PLANNED activities.
 * ON_HOLD pauses the cycle (PLANNED activities kept).
 * 
 * @param {string} cycleId - UUID of the cycle
 * @param {Object} payload - { outcome, outcome_notes?, hold_until? }
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function closeCycle(cycleId, payload = {}) {
  if (!cycleId || !isValidUUID(cycleId)) {
    return {
      success: false,
      error: 'Invalid cycle ID format',
      status: 400
    };
  }
  
  const result = await api.post(endpoints.closeCycle(cycleId), payload);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.cycles,
      endpoints.cycleDetail(cycleId),
      '/decision_cycles/by-account/',
      '/module-activities/'
    ]);
    const cycleData = result.data?.data || result.data;
    return { success: true, data: cycleData };
  }
  
  return {
    success: false,
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * REOPEN DECISION CYCLE
 * 
 * Clears outcome fields, returning cycle to derived status mode.
 * 
 * @param {string} cycleId - UUID of the cycle
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function reopenCycle(cycleId) {
  if (!cycleId || !isValidUUID(cycleId)) {
    return {
      success: false,
      error: 'Invalid cycle ID format',
      status: 400
    };
  }
  
  const result = await api.post(endpoints.reopenCycle(cycleId), {});
  
  if (result.success) {
    revalidateMultiple([
      endpoints.cycles,
      endpoints.cycleDetail(cycleId),
      '/decision_cycles/by-account/',
      '/module-activities/'
    ]);
    const cycleData = result.data?.data || result.data;
    return { success: true, data: cycleData };
  }
  
  return {
    success: false,
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

// ==============================|| DECISION STEP MUTATIONS ||============================== //

/**
 * CREATE DECISION STEP
 * 
 * @param {Object} payload - {cycle_id, name, stage, status, previous_step_id, ...}
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function createDecisionStep(payload) {
  const sanitized = sanitizeObject(payload, ['name', 'description', 'goal', 'stakeholder']);
  
  const result = await api.post(endpoints.steps, sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.steps,
      endpoints.cycles,
      endpoints.cycleDetail(payload.cycle_id)
    ]);
    // Extract nested data from backend response { success, data }
    const stepData = result.data?.data || result.data;
    return { success: true, data: stepData };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * UPDATE DECISION STEP
 * 
 * @param {string} stepId - UUID of the step
 * @param {Object} payload - Step data to update
 * @param {string} cycleId - UUID of the parent cycle (for revalidation)
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function updateDecisionStep(stepId, payload, cycleId = null) {
  if (!stepId || !isValidUUID(stepId)) {
    return {
      success: false,
      error: 'Invalid step ID format',
      status: 400
    };
  }
  
  const sanitized = sanitizeObject(payload, ['name', 'description', 'goal', 'stakeholder']);
  
  const result = await api.patch(endpoints.stepDetail(stepId), sanitized);
  
  if (result.success) {
    const revalidatePaths = [
      endpoints.steps,
      endpoints.stepDetail(stepId),
      '/decision_cycles/by-account/'
    ];
    
    if (cycleId) {
      revalidatePaths.push(endpoints.cycleDetail(cycleId));
    }
    
    revalidateMultiple(revalidatePaths);
    // Extract nested data from backend response { success, data }
    const stepData = result.data?.data || result.data;
    return { success: true, data: stepData };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * UPDATE DECISION STEP STATUS
 * 
 * Quick status update endpoint
 * 
 * @param {string} stepId - UUID of the step
 * @param {string} status - New status value
 * @param {string} cycleId - UUID of the parent cycle (for revalidation)
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function updateDecisionStepStatus(stepId, status, cycleId = null) {
  if (!stepId || !isValidUUID(stepId)) {
    return {
      success: false,
      error: 'Invalid step ID format',
      status: 400
    };
  }
  
  const result = await api.patch(endpoints.stepStatus(stepId), { status });
  
  if (result.success) {
    const revalidatePaths = [
      endpoints.steps,
      endpoints.stepDetail(stepId),
      '/decision_cycles/by-account/'
    ];
    
    if (cycleId) {
      revalidatePaths.push(endpoints.cycleDetail(cycleId));
    }
    
    revalidateMultiple(revalidatePaths);
    // Extract nested data from backend response { success, data }
    const stepData = result.data?.data || result.data;
    return { success: true, data: stepData };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * DELETE DECISION STEP
 * 
 * @param {string} stepId - UUID of the step
 * @param {string} cycleId - UUID of the parent cycle (for revalidation)
 * @returns {Promise<Object>} {success: boolean, status?: number, error?: string}
 */
export async function deleteDecisionStep(stepId, cycleId = null) {
  if (!stepId || !isValidUUID(stepId)) {
    return {
      success: false,
      error: 'Invalid step ID format',
      status: 400
    };
  }
  
  const result = await api.delete(endpoints.stepDetail(stepId));
  
  if (result.success || result.status === 204) {
    const revalidatePaths = [
      endpoints.steps,
      endpoints.cycles,
      '/decision_cycles/by-account/'
    ];
    
    if (cycleId) {
      revalidatePaths.push(endpoints.cycleDetail(cycleId));
    }
    
    revalidateMultiple(revalidatePaths);
    return { success: true, status: result.status ?? 204 };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}