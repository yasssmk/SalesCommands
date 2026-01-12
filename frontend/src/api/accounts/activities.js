// frontend/src/api/activities/activities.js
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
  IN_PROGRESS: 'IN_PROGRESS',
  COMPLETED: 'COMPLETED',
  CANCELLED: 'CANCELLED'
};

/**
 * Activity status labels for UI display
 */
export const ACTIVITY_STATUS_LABELS = {
  PLANNED: 'Planned',
  IN_PROGRESS: 'In Progress',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled'
};

/**
 * Status colors for UI display
 */
export const ACTIVITY_STATUS_COLORS = {
  PLANNED: 'default',
  IN_PROGRESS: 'info',
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

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  // Activities
  activities: '/module-activities/',
  activityDetail: (id) => `/module-activities/${id}/`,
  choices: '/module-activities/choices/',
  
  // Custom actions
  complete: (id) => `/module-activities/${id}/complete/`,
  cancel: (id) => `/module-activities/${id}/cancel/`,
  
  // List actions
  myActivities: '/module-activities/my-activities/',
  byAccount: '/module-activities/by-account/',
  byStep: '/module-activities/by-step/',
  overdue: '/module-activities/overdue/',
  upcoming: '/module-activities/upcoming/'
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