// frontend/src/api/accounts/activities.js
/**
 * API hooks and mutations for Activities module.
 * 
 * Follows the same patterns as decisionCycles.js for consistency.
 */

import useSWR from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey, revalidateMultiple } from 'api/_swr';
import { isValidUUID, sanitizeObject } from 'utils/validators';

// ==============================|| CONSTANTS ||============================== //

/**
 * Activity types (matching backend ActivityType choices)
 */
export const ACTIVITY_TYPES = {
  CALL: 'CALL',
  EMAIL: 'EMAIL',
  MEETING: 'MEETING',
  TASK: 'TASK',
  LINKEDIN: 'LINKEDIN',
  OTHER: 'OTHER'
};

/**
 * Activity type labels for UI display
 */
export const ACTIVITY_TYPE_LABELS = {
  CALL: 'Phone Call',
  EMAIL: 'Email',
  MEETING: 'Meeting',
  TASK: 'Task',
  LINKEDIN: 'LinkedIn Message',
  OTHER: 'Other'
};

/**
 * Activity type icons mapping (icon component names from ant-design)
 */
export const ACTIVITY_TYPE_ICONS = {
  CALL: 'PhoneOutlined',
  EMAIL: 'MailOutlined',
  MEETING: 'TeamOutlined',
  TASK: 'CheckSquareOutlined',
  LINKEDIN: 'LinkedinOutlined',
  OTHER: 'QuestionCircleOutlined'
};

/**
 * Activity statuses (matching backend ActivityStatus choices)
 */
export const ACTIVITY_STATUSES = {
  PLANNED: 'PLANNED',
  COMPLETED: 'COMPLETED',
  CANCELLED: 'CANCELLED'
};

/**
 * Activity status labels for UI display
 */
export const ACTIVITY_STATUS_LABELS = {
  PLANNED: 'Planned',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled'
};

/**
 * Status colors for UI display
 */
export const ACTIVITY_STATUS_COLORS = {
  PLANNED: 'default',
  COMPLETED: 'success',
  CANCELLED: 'error'
};

/**
 * Activity outcomes (matching backend ActivityOutcome choices)
 */
export const ACTIVITY_OUTCOMES = {
  SUCCESSFUL: 'SUCCESSFUL',
  NO_ANSWER: 'NO_ANSWER',
  CALLBACK_REQUESTED: 'CALLBACK_REQUESTED',
  NOT_INTERESTED: 'NOT_INTERESTED',
  WRONG_CONTACT: 'WRONG_CONTACT',
  MEETING_SCHEDULED: 'MEETING_SCHEDULED',
  FOLLOW_UP_NEEDED: 'FOLLOW_UP_NEEDED',
  OTHER: 'OTHER'
};

/**
 * Activity outcome labels for UI display
 */
export const ACTIVITY_OUTCOME_LABELS = {
  SUCCESSFUL: 'Successful',
  NO_ANSWER: 'No Answer',
  CALLBACK_REQUESTED: 'Callback Requested',
  NOT_INTERESTED: 'Not Interested',
  WRONG_CONTACT: 'Wrong Contact',
  MEETING_SCHEDULED: 'Meeting Scheduled',
  FOLLOW_UP_NEEDED: 'Follow-up Needed',
  OTHER: 'Other'
};

/**
 * Outcome colors for UI display
 */
export const ACTIVITY_OUTCOME_COLORS = {
  SUCCESSFUL: 'success',
  NO_ANSWER: 'warning',
  CALLBACK_REQUESTED: 'info',
  NOT_INTERESTED: 'error',
  WRONG_CONTACT: 'error',
  MEETING_SCHEDULED: 'success',
  FOLLOW_UP_NEEDED: 'warning',
  OTHER: 'default'
};

/**
 * No Next Step Reasons (matching backend NoNextStepReason choices)
 * 
 * Used when completing an activity without a planned follow-up.
 * Note: If prospect says "I'll call you back", create a TASK with due_date instead.
 */
export const NO_NEXT_STEP_REASONS = {
  CLOSE_WON: 'CLOSE_WON',
  CLOSE_LOST: 'CLOSE_LOST',
  ON_HOLD: 'ON_HOLD',
  NOT_QUALIFIED: 'NOT_QUALIFIED',
  OTHER: 'OTHER'
};

/**
 * No Next Step Reason labels for UI display
 */
export const NO_NEXT_STEP_REASON_LABELS = {
  CLOSE_WON: 'Close Won',
  CLOSE_LOST: 'Close Lost',
  ON_HOLD: 'On Hold',
  NOT_QUALIFIED: 'Not Qualified',
  OTHER: 'Other'
};

/**
 * No Next Step Reason colors for UI display
 */
export const NO_NEXT_STEP_REASON_COLORS = {
  CLOSE_WON: 'success',
  CLOSE_LOST: 'error',
  ON_HOLD: 'warning',
  NOT_QUALIFIED: 'default',
  OTHER: 'default'
};

/**
 * No Next Step Reason icons (ant-design icon names)
 */
export const NO_NEXT_STEP_REASON_ICONS = {
  CLOSE_WON: 'TrophyOutlined',
  CLOSE_LOST: 'CloseCircleOutlined',
  ON_HOLD: 'PauseCircleOutlined',
  NOT_QUALIFIED: 'StopOutlined',
  OTHER: 'QuestionCircleOutlined'
};


// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  activities: '/module-activities/',
  activityDetail: (id) => `/module-activities/${id}/`,
  myActivities: '/module-activities/my-activities/',
  byAccount: '/module-activities/by-account/',
  byStep: '/module-activities/by-step/',
  overdue: '/module-activities/overdue/',
  upcoming: '/module-activities/upcoming/',
  complete: (id) => `/module-activities/${id}/complete/`,
  cancel: (id) => `/module-activities/${id}/cancel/`,
  reopen: (id) => `/module-activities/${id}/reopen/`,
  createWithEntities: '/module-activities/create-with-entities/',
  unlinkedByAccount: (accountId) => `/module-activities/unlinked/by-account/${accountId}/`,
  choices: '/module-activities/choices/',
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
  if (filters.account_id) {
    queryParams.append('account_id', filters.account_id);
  }
  
  if (filters.owner_id) {
    queryParams.append('owner', filters.owner_id);
  }

  if (filters.activity_type) {
    queryParams.append('activity_type', filters.activity_type);
  }

  if (filters.status) {
    queryParams.append('status', filters.status);
  }

  if (filters.decision_cycle_id) {
    queryParams.append('decision_cycle', filters.decision_cycle_id);
  }

  if (filters.decision_step_id) {
    queryParams.append('decision_step', filters.decision_step_id);
  }

  if (filters.is_overdue !== undefined) {
    queryParams.append('is_overdue', filters.is_overdue);
  }

  if (filters.has_decision_step !== undefined) {
    queryParams.append('has_decision_step', filters.has_decision_step);
  }
  
  const queryString = queryParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

// ==============================|| ACTIVITY HOOKS ||============================== //

/**
 * GET ACTIVITIES - Paginated list with filters
 * 
 * @param {Object} options - {page, pageSize, search, ordering, filters}
 * @returns {Object} {activities, activitiesCount, activitiesLoading, activitiesError, activitiesValidating, activitiesEmpty, mutateActivities}
 */
export function useGetActivities(options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 50, search = '', ordering = '-scheduled_date', filters = {} } = options;

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.activities, { page, pageSize, search, ordering, filters });
  }, [page, pageSize, search, ordering, filters]);

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      activities: data?.data?.results || data?.results || [],
      activitiesCount: data?.data?.count || data?.count || 0,
      activitiesLoading: isLoading,
      activitiesError: error,
      activitiesValidating: isValidating,
      activitiesEmpty: !isLoading && !(data?.data?.results?.length || data?.results?.length),
      mutateActivities: mutate
    }),
    [data, isLoading, error, isValidating, mutate]
  );

  return memoizedValue;
}

/**
 * GET ACTIVITY - Single activity details
 * 
 * @param {string} activityId - UUID of the activity
 * @returns {Object} {activity, activityLoading, activityError, activityValidating, mutateActivity}
 */
export function useGetActivity(activityId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!activityId || !isValidUUID(activityId)) return null;
    return tenantKey(endpoints.activityDetail(activityId), tenantId);
  }, [activityId, tenantId]);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      activity: data?.data || null,
      activityLoading: isLoading,
      activityError: error,
      activityValidating: isValidating,
      mutateActivity: mutate
    }),
    [data, isLoading, error, isValidating, mutate]
  );

  return memoizedValue;
}

/**
 * GET ACTIVITIES BY ACCOUNT - All activities for a specific account
 * 
 * @param {string} accountId - UUID of the account
 * @param {Object} options - {page, pageSize, ordering, filters}
 * @returns {Object} {activities, activitiesCount, activitiesLoading, activitiesError, mutateActivities}
 */
export function useGetActivitiesByAccount(accountId, options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 50, ordering = '-scheduled_date', filters = {} } = options;

  const swrKey = useMemo(() => {
    if (!accountId || !isValidUUID(accountId)) return null;
    const url = buildUrlWithParams(endpoints.byAccount, { 
      page, 
      pageSize, 
      ordering, 
      filters: { ...filters, account_id: accountId }
    });
    return tenantKey(url, tenantId);
  }, [accountId, page, pageSize, ordering, filters, tenantId]);
  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      activities: data?.data?.results || data?.results || [],
      activitiesCount: data?.data?.count || data?.count || 0,
      activitiesLoading: isLoading,
      activitiesError: error,
      activitiesValidating: isValidating,
      activitiesEmpty: !isLoading && !(data?.data?.results?.length || data?.results?.length),
      mutateActivities: mutate
    }),
    [data, isLoading, error, isValidating, mutate]
  );

  return memoizedValue;
}

/**
 * GET ACTIVITIES BY STEP - All activities for a specific decision step
 * 
 * @param {string} stepId - UUID of the decision step
 * @param {Object} options - {page, pageSize, ordering}
 * @returns {Object} {activities, activitiesCount, activitiesLoading, activitiesError, mutateActivities}
 */
export function useGetActivitiesByStep(stepId, options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 50, ordering = '-scheduled_date' } = options;

  const swrKey = useMemo(() => {
    if (!stepId || !isValidUUID(stepId)) return null;
    const queryParams = new URLSearchParams();
    queryParams.append('step_id', stepId);
    if (page) queryParams.append('page', page);
    if (pageSize) queryParams.append('page_size', pageSize);
    if (ordering) queryParams.append('ordering', ordering);
    return tenantKey(`${endpoints.byStep}?${queryParams.toString()}`, tenantId);
  }, [stepId, page, pageSize, ordering, tenantId]);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      activities: data?.data?.results || data?.results || [],
      activitiesCount: data?.data?.count || data?.count || 0,
      activitiesLoading: isLoading,
      activitiesError: error,
      activitiesValidating: isValidating,
      activitiesEmpty: !isLoading && !(data?.data?.results?.length || data?.results?.length),
      mutateActivities: mutate
    }),
    [data, isLoading, error, isValidating, mutate]
  );

  return memoizedValue;
}

/**
 * GET UNLINKED ACTIVITIES FOR ACCOUNT
 * 
 * Retrieves activities not linked to any decision step.
 * Used for "Link Existing Activity" feature in pipeline timeline.
 * 
 * @param {string} accountId - UUID of the account
 * @param {Object} options - Query options
 * @param {boolean} options.excludeCancelled - Exclude cancelled activities (default: true)
 * @param {number} options.limit - Maximum results (default: 50, max: 100)
 * @returns {Promise<Object>} {success: boolean, data?: Array, error?: string}
 */
export async function getUnlinkedActivities(accountId, options = {}) {
  if (!accountId || !isValidUUID(accountId)) {
    return {
      success: false,
      error: 'Invalid account ID format',
      status: 400
    };
  }
  
  const { excludeCancelled = true, limit = 50 } = options;
  
  const params = new URLSearchParams();
  if (!excludeCancelled) params.append('exclude_cancelled', 'false');
  if (limit !== 50) params.append('limit', String(limit));
  
  const queryString = params.toString();
  const url = queryString 
    ? `${endpoints.unlinkedByAccount(accountId)}?${queryString}`
    : endpoints.unlinkedByAccount(accountId);
  
  const result = await api.get(url);
  
  if (result.success) {
    const data = result.data?.data || result.data;
    return { 
      success: true, 
      data: data?.results || data || [] 
    };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * LINK ACTIVITY TO DECISION STEP
 * 
 * Links an existing activity to a decision cycle and step.
 * Uses PATCH to update the activity's decision_cycle_id and decision_step_id.
 * 
 * @param {string} activityId - UUID of the activity to link
 * @param {string} cycleId - UUID of the decision cycle
 * @param {string} stepId - UUID of the decision step
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function linkActivityToStep(activityId, cycleId, stepId, accountId = null) {
  if (!activityId || !isValidUUID(activityId)) {
    return {
      success: false,
      error: 'Invalid activity ID format',
      status: 400
    };
  }
  
  if (!cycleId || !isValidUUID(cycleId)) {
    return {
      success: false,
      error: 'Invalid cycle ID format',
      status: 400
    };
  }
  
  if (!stepId || !isValidUUID(stepId)) {
    return {
      success: false,
      error: 'Invalid step ID format',
      status: 400
    };
  }
  
  const result = await api.patch(endpoints.activityDetail(activityId), {
    decision_cycle_id: cycleId,
    decision_step_id: stepId
  });
  
  if (result.success) {
    const revalidatePaths = [
      endpoints.activities,
      endpoints.activityDetail(activityId),
      endpoints.myActivities,
      endpoints.byStep,  // Prefix-based: revalidates all /module-activities/by-step/* queries
      '/module-decision-cycles/',
      `/module-decision-cycles/${cycleId}/`,
      '/module-decision-cycles/by-account/'
    ];
    
    // Also revalidate unlinked activities list if accountId provided
    if (accountId) {
      revalidatePaths.push(endpoints.unlinkedByAccount(accountId));
    }
    
    revalidateMultiple(revalidatePaths);
    const activityData = result.data?.data || result.data;
    return { success: true, data: activityData };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * UNLINK ACTIVITY FROM DECISION STEP
 * 
 * Removes an activity's link to decision cycle and step.
 * Sets decision_cycle_id and decision_step_id to null.
 * 
 * @param {string} activityId - UUID of the activity to unlink
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function unlinkActivityFromStep(activityId) {
  if (!activityId || !isValidUUID(activityId)) {
    return {
      success: false,
      error: 'Invalid activity ID format',
      status: 400
    };
  }
  
  const result = await api.patch(endpoints.activityDetail(activityId), {
    decision_cycle_id: null,
    decision_step_id: null
  });
  
  if (result.success) {
    revalidateMultiple([
      endpoints.activities,
      endpoints.activityDetail(activityId),
      endpoints.myActivities,
      '/module-decision-cycles/'
    ]);
    const activityData = result.data?.data || result.data;
    return { success: true, data: activityData };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * GET ACTIVITY CHOICES - Types, statuses, and outcomes for dropdowns
 * 
 * @returns {Object} {choices, types, statuses, outcomes, choicesLoading, choicesError}
 */
export function useGetActivityChoices() {
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
      types: data?.data?.activity_types || [],
      statuses: data?.data?.statuses || [],
      outcomes: data?.data?.outcomes || [],
      choicesLoading: isLoading,
      choicesError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

/**
 * GET MY ACTIVITIES - Current user's activities
 * 
 * @param {Object} options - {page, pageSize, ordering, filters}
 * @returns {Object} {activities, activitiesCount, activitiesLoading, activitiesError, mutateActivities}
 */
export function useGetMyActivities(options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 50, ordering = '-scheduled_date', filters = {} } = options;

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.myActivities, { page, pageSize, ordering, filters });
  }, [page, pageSize, ordering, filters]);

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      activities: data?.data?.results || data?.results || [],
      activitiesCount: data?.data?.count || data?.count || 0,
      activitiesLoading: isLoading,
      activitiesError: error,
      activitiesValidating: isValidating,
      activitiesEmpty: !isLoading && !(data?.data?.results?.length || data?.results?.length),
      mutateActivities: mutate
    }),
    [data, isLoading, error, isValidating, mutate]
  );

  return memoizedValue;
}

/**
 * GET OVERDUE ACTIVITIES - Activities past due date
 * 
 * @param {Object} options - {page, pageSize, ordering}
 * @returns {Object} {activities, activitiesCount, activitiesLoading, activitiesError, mutateActivities}
 */
export function useGetOverdueActivities(options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 50, ordering = 'due_date' } = options;

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.overdue, { page, pageSize, ordering });
  }, [page, pageSize, ordering]);

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      activities: data?.data?.results || data?.results || [],
      activitiesCount: data?.data?.count || data?.count || 0,
      activitiesLoading: isLoading,
      activitiesError: error,
      activitiesValidating: isValidating,
      mutateActivities: mutate
    }),
    [data, isLoading, error, isValidating, mutate]
  );

  return memoizedValue;
}

/**
 * GET UPCOMING ACTIVITIES - Upcoming activities
 * 
 * @param {Object} options - {page, pageSize, ordering}
 * @returns {Object} {activities, activitiesCount, activitiesLoading, activitiesError, mutateActivities}
 */
export function useGetUpcomingActivities(options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 50, ordering = 'scheduled_date' } = options;

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.upcoming, { page, pageSize, ordering });
  }, [page, pageSize, ordering]);

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      activities: data?.data?.results || data?.results || [],
      activitiesCount: data?.data?.count || data?.count || 0,
      activitiesLoading: isLoading,
      activitiesError: error,
      activitiesValidating: isValidating,
      mutateActivities: mutate
    }),
    [data, isLoading, error, isValidating, mutate]
  );

  return memoizedValue;
}

// ==============================|| ACTIVITY MUTATIONS ||============================== //

/**
 * CREATE ACTIVITY
 * 
 * @param {Object} payload - Activity data
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function createActivity(payload) {
  const sanitized = sanitizeObject(payload, ['title', 'description', 'call_to_action', 'outcome_notes']);
  
  const result = await api.post(endpoints.activities, sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.activities,
      endpoints.myActivities,
      endpoints.byAccount,
      '/company-accounts/',
      '/company-accounts/'
    ]);
    const activityData = result.data?.data || result.data;
    return { success: true, data: activityData };
  }
    
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * CREATE ACTIVITY WITH INLINE ENTITIES
 * 
 * Creates an activity with optional inline creation of contact, cycle, and step.
 * All entities are created in FK-safe order within a single transaction.
 * 
 * @param {Object} payload - Combined payload
 * @param {Object} payload.activity - Activity data (required)
 * @param {Object} [payload.inline_contact] - Optional inline contact to create
 * @param {Object} [payload.inline_cycle] - Optional inline cycle to create
 * @param {Object} [payload.inline_step] - Optional inline step to create (requires cycle)
 * @returns {Promise<Object>} {success: boolean, data?: {activity, created_entities}, error?: string}
 */
export async function createActivityWithEntities(payload) {
  // Sanitize activity data
  const sanitizedActivity = payload.activity 
    ? sanitizeObject(payload.activity, ['title', 'description', 'call_to_action', 'outcome_notes'])
    : null;
  
  // Sanitize inline contact if provided
  const sanitizedContact = payload.inline_contact
    ? sanitizeObject(payload.inline_contact, ['first_name', 'last_name', 'email', 'phone', 'job_title'])
    : null;
  
  // Sanitize inline cycle if provided
  const sanitizedCycle = payload.inline_cycle
    ? sanitizeObject(payload.inline_cycle, ['name', 'description'])
    : null;
  
  // Sanitize inline step if provided
  const sanitizedStep = payload.inline_step
    ? sanitizeObject(payload.inline_step, ['name', 'description', 'goal'])
    : null;
  
  // Build sanitized payload
  const sanitizedPayload = {
    activity: sanitizedActivity
  };
  
  if (sanitizedContact) {
    sanitizedPayload.inline_contact = sanitizedContact;
  }
  
  if (sanitizedCycle) {
    sanitizedPayload.inline_cycle = sanitizedCycle;
  }
  
  if (sanitizedStep) {
    sanitizedPayload.inline_step = sanitizedStep;
  }
  
  const result = await api.post(endpoints.createWithEntities, sanitizedPayload);
  
  if (result.success) {
    // Revalidate all potentially affected endpoints
    revalidateMultiple([
      endpoints.activities,
      endpoints.myActivities,
      '/company-accounts/',
      '/module-contacts/',
      '/module-decision-cycles/',
      '/module-activities/'
    ]);
    
    const responseData = result.data?.data || result.data;
    return { 
      success: true, 
      data: responseData
    };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * UPDATE ACTIVITY
 * 
 * @param {string} activityId - UUID of the activity
 * @param {Object} payload - Activity data to update
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function updateActivity(activityId, payload) {
  if (!activityId || !isValidUUID(activityId)) {
    return {
      success: false,
      error: 'Invalid activity ID format',
      status: 400
    };
  }
  
  const sanitized = sanitizeObject(payload, ['title', 'description', 'call_to_action', 'outcome_notes']);
  
  const result = await api.patch(endpoints.activityDetail(activityId), sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.activities,
      endpoints.activityDetail(activityId),
      endpoints.myActivities,
      '/company-accounts/'
    ]);
    const activityData = result.data?.data || result.data;
    return { success: true, data: activityData };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * DELETE ACTIVITY
 * 
 * @param {string} activityId - UUID of the activity
 * @returns {Promise<Object>} {success: boolean, status?: number, error?: string}
 */
export async function deleteActivity(activityId) {
  if (!activityId || !isValidUUID(activityId)) {
    return {
      success: false,
      error: 'Invalid activity ID format',
      status: 400
    };
  }
  
  const result = await api.delete(endpoints.activityDetail(activityId));
  
  if (result.success || result.status === 204) {
    revalidateMultiple([
      endpoints.activities,
      endpoints.myActivities,
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

/**
 * COMPLETE ACTIVITY
 * 
 * @param {string} activityId - UUID of the activity
 * @param {Object} payload - {outcome, outcome_notes}
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function completeActivity(activityId, payload = {}) {
  if (!activityId || !isValidUUID(activityId)) {
    return {
      success: false,
      error: 'Invalid activity ID format',
      status: 400
    };
  }
  
  const sanitized = sanitizeObject(payload, ['outcome_notes']);
  
  const result = await api.post(endpoints.complete(activityId), sanitized);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.activities,
      endpoints.activityDetail(activityId),
      endpoints.myActivities,
      endpoints.overdue,
      '/company-accounts/'
    ]);
    const activityData = result.data?.data || result.data;
    return { success: true, data: activityData };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * MARK ACTIVITY AS NO NEXT STEP
 * 
 * Sets next_step_agreed=false with optional reason.
 * This triggers stalled detection on linked DecisionStep.
 * 
 * @param {string} activityId - UUID of the activity
 * @param {Object} payload - {reason?: string}
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function markNoNextStep(activityId, payload = {}) {
  if (!activityId || !isValidUUID(activityId)) {
    return {
      success: false,
      error: 'Invalid activity ID format',
      status: 400
    };
  }
  
  const result = await api.patch(endpoints.activityDetail(activityId), {
    next_step_agreed: false,
    no_next_step_reason: payload.reason?.trim() || null
  });
  
  if (result.success) {
    revalidateMultiple([
      endpoints.activities,
      endpoints.activityDetail(activityId),
      endpoints.myActivities,
      '/company-accounts/',
      '/module-decision-cycles/'
    ]);
    const activityData = result.data?.data || result.data;
    return { success: true, data: activityData };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * MARK ACTIVITY AS NEXT STEP AGREED
 * 
 * Sets next_step_agreed=true (follow-up was scheduled).
 * Call this after creating a follow-up activity or decision step.
 * 
 * @param {string} activityId - UUID of the activity
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */

export async function markNextStepAgreed(activityId) {
  if (!activityId || !isValidUUID(activityId)) {
    return {
      success: false,
      error: 'Invalid activity ID format',
      status: 400
    };
  }
  
  const result = await api.patch(endpoints.activityDetail(activityId), {
    next_step_agreed: true,
    no_next_step_reason: null
  });
  
  if (result.success) {
    revalidateMultiple([
      endpoints.activities,
      endpoints.activityDetail(activityId),
      endpoints.myActivities,
      '/company-accounts/',
      '/module-decision-cycles/'
    ]);
    const activityData = result.data?.data || result.data;
    return { success: true, data: activityData };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * CANCEL ACTIVITY
 * 
 * @param {string} activityId - UUID of the activity
 * @param {Object} payload - {notes}
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function cancelActivity(activityId, payload = {}) {
  if (!activityId || !isValidUUID(activityId)) {
    return {
      success: false,
      error: 'Invalid activity ID format',
      status: 400
    };
  }
  
  const result = await api.post(endpoints.cancel(activityId), payload);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.activities,
      endpoints.activityDetail(activityId),
      endpoints.myActivities,
      endpoints.overdue,
      '/company-accounts/'
    ]);
    const activityData = result.data?.data || result.data;
    return { success: true, data: activityData };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}

/**
 * REOPEN ACTIVITY
 * 
 * Reopens a completed or cancelled activity.
 * Clears outcome, outcome_notes, and completed_at.
 * 
 * @param {string} activityId - UUID of the activity
 * @param {Object} payload - {status?: 'PLANNED' | 'IN_PROGRESS'} - defaults to 'PLANNED'
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function reopenActivity(activityId, payload = {}) {
  if (!activityId || !isValidUUID(activityId)) {
    return {
      success: false,
      error: 'Invalid activity ID format',
      status: 400
    };
  }
  
  const result = await api.post(endpoints.reopen(activityId), payload);
  
  if (result.success) {
    revalidateMultiple([
      endpoints.activities,
      endpoints.activityDetail(activityId),
      endpoints.myActivities,
      endpoints.overdue,
      '/company-accounts/'
    ]);
    const activityData = result.data?.data || result.data;
    return { success: true, data: activityData };
  }
  
  return { 
    success: false, 
    error: result.error,
    status: result.status || 0,
    response: result.response || null
  };
}