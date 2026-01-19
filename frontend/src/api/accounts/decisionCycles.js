// frontend/src/api/accounts/decisionCycles.js
/**
 * API hooks and mutations for Decision Cycles module.
 * 
 * Follows the same patterns as territories.js for consistency.
 */

import useSWR from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey, revalidateMultiple } from 'api/_swr';
import { isValidUUID, sanitizeObject } from 'utils/validators';

// ==============================|| CONSTANTS ||============================== //
/**
 * Decision stages (matching backend DecisionStage choices)
 */
export const DECISION_STAGES = {
  EXPLORATION: 'EXPLORATION',
  CRITERIA_VALIDATION: 'CRITERIA_VALIDATION',
  SOLUTION_CONFIRMATION: 'SOLUTION_CONFIRMATION',
  BUSINESS_VALIDATION: 'BUSINESS_VALIDATION',
  FORMALIZATION: 'FORMALIZATION'
};

/**
 * Decision step statuses (matching backend DecisionStepStatus choices)
 */
export const DECISION_STEP_STATUSES = {
  NOT_STARTED: 'NOT_STARTED',
  PENDING_CLIENT: 'PENDING_CLIENT',
  IN_PROGRESS: 'IN_PROGRESS',
  IN_CHASING: 'IN_CHASING',
  VALIDATED: 'VALIDATED',
  REJECTED: 'REJECTED'
};

/**
 * Decision step types (matching backend DecisionStepType choices)
 */
export const DECISION_STEP_TYPES = {
  MEETING: 'MEETING',
  CALL: 'CALL',
  EMAIL: 'EMAIL',
  TASK_SELLER: 'TASK_SELLER',
  TASK_BUYER: 'TASK_BUYER',
  INTERNAL_VALIDATION: 'INTERNAL_VALIDATION',
  OTHER: 'OTHER'
};

/**
 * Step type labels for UI display
 */
export const STEP_TYPE_LABELS = {
  MEETING: 'Meeting',
  CALL: 'Call',
  EMAIL: 'Email',
  TASK_SELLER: 'Task (Seller)',
  TASK_BUYER: 'Task (Buyer)',
  INTERNAL_VALIDATION: 'Internal Validation',
  OTHER: 'Other'
};

/**
 * Step type icons mapping (icon component names from ant-design)
 */
export const STEP_TYPE_ICONS = {
  MEETING: 'TeamOutlined',
  CALL: 'PhoneOutlined',
  EMAIL: 'MailOutlined',
  TASK_SELLER: 'CheckSquareOutlined',
  TASK_BUYER: 'AuditOutlined',
  INTERNAL_VALIDATION: 'SafetyOutlined',
  OTHER: 'QuestionCircleOutlined'
};

/**
 * Status colors for UI display
 */
export const STATUS_COLORS = {
  NOT_STARTED: 'default',
  PENDING_CLIENT: 'warning',
  IN_PROGRESS: 'info',
  IN_CHASING: 'secondary',
  VALIDATED: 'success',
  REJECTED: 'error'
};

/**
 * Stage order for timeline display
 */
export const STAGE_ORDER = [
  'EXPLORATION',
  'CRITERIA_VALIDATION',
  'SOLUTION_CONFIRMATION',
  'BUSINESS_VALIDATION',
  'FORMALIZATION'
];

/**
 * Stage labels for UI display
 */
export const STAGE_LABELS = {
  EXPLORATION: 'Exploration',
  CRITERIA_VALIDATION: 'Criteria Validation',
  SOLUTION_CONFIRMATION: 'Solution Confirmation',
  BUSINESS_VALIDATION: 'Business Validation',
  FORMALIZATION: 'Formalization'
};

/**
 * Step status labels for UI display
 */
export const STATUS_LABELS = {
  NOT_STARTED: 'Not Started',
  PENDING_CLIENT: 'Pending Client',
  IN_PROGRESS: 'In Progress',
  IN_CHASING: 'In Chasing',
  VALIDATED: 'Validated',
  REJECTED: 'Rejected'
};

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  // Decision Cycles
  cycles: '/decision_cycles/',
  cycleDetail: (id) => `/decision_cycles/${id}/`,
  cyclesByAccount: (accountId) => `/decision_cycles/by-account/${accountId}/`,
  choices: '/decision_cycles/choices/',
  
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
      stepTypes: data?.data?.step_types || [],
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
 * GET DECISION STEP WITH CONTEXT - Step details with related data for workspace
 * 
 * Fetches step with:
 * - completeness_score and completeness_details
 * - linked cycle info
 * - linked account info
 * - activities count
 * - contacts
 * 
 * Used by Step detail workspace page.
 * 
 * @param {string} stepId - UUID of the step
 * @param {Object} options - Additional options
 * @param {boolean} options.includeActivities - Whether to fetch activities count
 * @returns {Object} {step, cycle, account, stepLoading, stepError, mutateStep}
 */
export function useGetDecisionStepWithContext(stepId, options = {}) {
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

  // Derive account from cycle
  const account = useMemo(() => {
    if (!cycle) return null;
    
    // Cycle should have account info
    if (cycle.account) {
      return typeof cycle.account === 'object' 
        ? cycle.account 
        : { id: cycle.account, name: cycle.account_name };
    }
    
    // Fallback: check step for account info
    if (step?.account) {
      return typeof step.account === 'object'
        ? step.account
        : { id: step.account };
    }
    
    return null;
  }, [cycle, step]);

  // Compute derived state
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
      statusName: step?.status ? (STATUS_LABELS[step.status] || step.status) : ''
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
 * GET DECISION STEP - Single step details
 * 
 * @param {string} stepId - UUID of the step
 * @returns {Object} {step, stepLoading, stepError, mutateStep}
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
 * DELETE DECISION CYCLE
 * 
 * @param {string} cycleId - UUID of the cycle
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
    revalidateMultiple([
      endpoints.cycles,
      '/company-accounts/'
    ]);
    return { success: true, status: result.status ?? 204 };
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
      endpoints.stepDetail(stepId)
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
      endpoints.stepDetail(stepId)
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
      endpoints.cycles
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