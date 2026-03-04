// frontend/src/api/campaigns/campaigns.js
/**
 * API hooks and mutations for Campaigns module.
 *
 * Follows the same patterns as territories.js for consistency.
 * Connected to backend: app_modules/campaigns/
 */

import useSWR from "swr";
import { useMemo } from "react";
import { useAuth } from "hooks/useAuth";
import { api } from "utils/axiosClient";
import { tenantKey, revalidateMultiple } from "api/_swr";
import { isValidUUID, sanitizeObject } from "utils/validators";

// ==============================|| CONSTANTS ||============================== //

/**
 * Campaign families — matches backend CampaignFamily choices
 */
export const CAMPAIGN_FAMILIES = {
  OUTBOUND: "OUTBOUND",
  TARGETED: "TARGETED",
};

/**
 * Campaign family labels for UI display
 */
export const CAMPAIGN_FAMILY_LABELS = {
  OUTBOUND: "Outbound",
  TARGETED: "Targeted",
};

/**
 * Campaign statuses — matches backend CampaignStatus choices
 */
export const CAMPAIGN_STATUSES = {
  DRAFT: "DRAFT",
  ACTIVE: "ACTIVE",
  PAUSED: "PAUSED",
  COMPLETED: "COMPLETED",
  CANCELLED: "CANCELLED",
};

/**
 * Campaign status labels for UI display
 */
export const CAMPAIGN_STATUS_LABELS = {
  DRAFT: "Draft",
  ACTIVE: "Active",
  PAUSED: "Paused",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

/**
 * Status colors for MUI Chip color prop
 */
export const CAMPAIGN_STATUS_COLORS = {
  DRAFT: "default",
  ACTIVE: "success",
  PAUSED: "warning",
  COMPLETED: "primary",
  CANCELLED: "error",
};

/**
 * Sequence types for outbound campaigns
 */
export const SEQUENCE_TYPES = {
  CALL_EMAIL_CALL: "CALL_EMAIL_CALL",
  EMAIL_CALL_EMAIL: "EMAIL_CALL_EMAIL",
  CALL_ONLY: "CALL_ONLY",
  EMAIL_ONLY: "EMAIL_ONLY",
};

/**
 * Sequence type labels for UI display
 */
export const SEQUENCE_TYPE_LABELS = {
  CALL_EMAIL_CALL: "Call → Email → Call",
  EMAIL_CALL_EMAIL: "Email → Call → Email",
  CALL_ONLY: "Call Only",
  EMAIL_ONLY: "Email Only",
};

/**
 * Campaign member roles — matches backend MemberRole choices
 */
export const MEMBER_ROLES = {
  OWNER: "OWNER",
  EXECUTOR: "EXECUTOR",
  RECEIVER: "RECEIVER",
  OBSERVER: "OBSERVER",
};

/**
 * Member role labels for UI display
 */
export const MEMBER_ROLE_LABELS = {
  OWNER: "Owner",
  EXECUTOR: "Executor",
  RECEIVER: "Receiver",
  OBSERVER: "Observer",
};

/**
 * Objective types — matches backend ObjectiveType choices
 */
export const OBJECTIVE_TYPES = {
  MEETINGS: "MEETINGS",
  DECISION_CYCLES: "DECISION_CYCLES",
  CONTACTS_REACHED: "CONTACTS_REACHED",
  PIPELINE_VALUE: "PIPELINE_VALUE",
  REVENUE_WON: "REVENUE_WON",
  NEW_LOGOS: "NEW_LOGOS",
};

/**
 * Objective type labels for UI display
 */
export const OBJECTIVE_TYPE_LABELS = {
  MEETINGS: "Meetings Booked",
  DECISION_CYCLES: "Decision Cycles Created",
  CONTACTS_REACHED: "Contacts Reached",
  PIPELINE_VALUE: "Pipeline Value",
  REVENUE_WON: "Revenue Won",
  NEW_LOGOS: "New Logos",
};

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  // Campaign CRUD
  campaigns: "/campaigns/",
  campaignDetail: (id) => `/campaigns/${id}/`,

  // Lifecycle actions
  campaignStart: (id) => `/campaigns/${id}/start/`,
  campaignPause: (id) => `/campaigns/${id}/pause/`,
  campaignResume: (id) => `/campaigns/${id}/resume/`,
  campaignComplete: (id) => `/campaigns/${id}/complete/`,
  campaignCancel: (id) => `/campaigns/${id}/cancel/`,

  // Analytics & execution
  campaignDashboard: (id) => `/campaigns/${id}/dashboard/`,
  campaignSummary: (id) => `/campaigns/${id}/summary/`,
  campaignPlaylist: (id) => `/campaigns/${id}/playlist/`,
  campaignGenerateActivities: (id) => `/campaigns/${id}/generate-activities/`,

  // Scoped list
  myCampaigns: "/campaigns/my-campaigns/",

  // Members
  members: "/campaigns/members/",
  memberDetail: (id) => `/campaigns/members/${id}/`,
  membersByCampaign: "/campaigns/members/by-campaign/",

  // Objectives
  objectives: "/campaigns/objectives/",
  objectiveDetail: (id) => `/campaigns/objectives/${id}/`,
  objectivesByCampaign: "/campaigns/objectives/by-campaign/",
  objectivesChoices: "/campaigns/objectives/choices/",

  // Campaign Accounts
  campaignAccounts: "/campaigns/accounts/",
  campaignAccountDetail: (id) => `/campaigns/accounts/${id}/`,
  accountsByCampaign: "/campaigns/accounts/by-campaign/",
  accountsBulkAdd: "/campaigns/accounts/bulk-add/",
  accountsBulkRemove: "/campaigns/accounts/bulk-remove/",

  // Activities (cross-module)
  activityComplete: (id) => `/module-activities/${id}/complete/`,

  // Bulk
  bulkDelete: "/campaigns/bulk-delete/",
};

// ==============================|| HELPER - BUILD URL WITH PARAMS ||============================== //

/**
 * Build URL with query params for server-side pagination/filtering
 * @param {string} baseUrl - Base URL
 * @param {Object} params - Optional params {page, pageSize, search, ordering, filters}
 * @returns {string} URL with query string
 */
const buildUrlWithParams = (baseUrl, params = {}) => {
  const { page, pageSize, search, ordering, filters = {} } = params;
  const queryParams = new URLSearchParams();

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

  // Owner scope filter (mine/team/all)
  if (filters.owner_scope) {
    queryParams.append("owner_scope", filters.owner_scope);
  }

  // Campaign-specific filters
  if (filters.status) {
    queryParams.append("status", filters.status);
  }

  if (filters.campaign_type) {
    queryParams.append("campaign_type", filters.campaign_type);
  }

  if (filters.territory) {
    queryParams.append("territory", filters.territory);
  }

  const queryString = queryParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

// ==============================|| READ HOOKS ||============================== //

/**
 * GET CAMPAIGNS - Paginated list with filters
 *
 * @param {Object} options - {page, pageSize, search, ordering, filters}
 * @returns {Object} {campaigns, campaignsCount, campaignsLoading, campaignsError, campaignsValidating, campaignsEmpty}
 */
export function useGetCampaigns(options = {}) {
  const { tenantId } = useAuth();
  const {
    page = 1,
    pageSize = 50,
    search = "",
    ordering = "",
    filters = {},
  } = options;

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.campaigns, {
      page,
      pageSize,
      search,
      ordering,
      filters,
    });
  }, [page, pageSize, search, ordering, filters]);

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      campaigns: data?.data?.results || data?.results || [],
      campaignsCount: data?.data?.count || data?.count || 0,
      campaignsLoading: isLoading,
      campaignsError: error,
      campaignsValidating: isValidating,
      campaignsEmpty:
        !isLoading && !(data?.data?.results?.length || data?.results?.length),
    }),
    [data, isLoading, error, isValidating],
  );

  return memoizedValue;
}

/**
 * GET CAMPAIGN - Single campaign details
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Object} {campaign, campaignLoading, campaignError, campaignValidating}
 */
export function useGetCampaign(campaignId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!campaignId || !isValidUUID(campaignId)) return null;
    return tenantKey(endpoints.campaignDetail(campaignId), tenantId);
  }, [campaignId, tenantId]);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      campaign: data?.data || data || null,
      campaignLoading: isLoading,
      campaignError: error,
      campaignValidating: isValidating,
    }),
    [data, isLoading, error, isValidating],
  );

  return memoizedValue;
}

/**
 * GET CAMPAIGN WORKSPACE - Campaign details + dashboard stats
 *
 * Uses the dashboard endpoint for stats alongside detail for campaign data.
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Object} {campaign, stats, loading, error, validating, mutate}
 */
export function useGetCampaignWorkspace(campaignId) {
  const { tenantId } = useAuth();

  // Campaign detail
  const campaignKey = useMemo(() => {
    if (!campaignId || !isValidUUID(campaignId)) return null;
    return tenantKey(endpoints.campaignDetail(campaignId), tenantId);
  }, [campaignId, tenantId]);

  const {
    data: campaignData,
    isLoading: campaignLoading,
    error: campaignError,
    isValidating: campaignValidating,
    mutate,
  } = useSWR(campaignKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  // Dashboard stats
  const dashboardKey = useMemo(() => {
    if (!campaignId || !isValidUUID(campaignId)) return null;
    return tenantKey(endpoints.campaignDashboard(campaignId), tenantId);
  }, [campaignId, tenantId]);

  const { data: dashboardData, isLoading: dashboardLoading } = useSWR(
    dashboardKey,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      shouldRetryOnError: true,
    },
  );

  const memoizedValue = useMemo(
    () => ({
      campaign: campaignData?.data || campaignData || null,
      stats: dashboardData?.data ||
        dashboardData || {
          total_accounts: 0,
          total_activities: 0,
          total_members: 0,
          completion_rate: 0,
        },
      loading: campaignLoading || dashboardLoading,
      error: campaignError,
      validating: campaignValidating,
      mutate,
    }),
    [
      campaignData,
      dashboardData,
      campaignLoading,
      dashboardLoading,
      campaignError,
      campaignValidating,
      mutate,
    ],
  );

  return memoizedValue;
}

/**
 * GET MY CAMPAIGNS - Current user's campaigns
 *
 * @param {Object} options - {page, pageSize, ordering, filters}
 * @returns {Object} {campaigns, campaignsCount, campaignsLoading, campaignsError}
 */
export function useGetMyCampaigns(options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 50, ordering = "", filters = {} } = options;

  const urlWithParams = useMemo(() => {
    return buildUrlWithParams(endpoints.myCampaigns, {
      page,
      pageSize,
      ordering,
      filters,
    });
  }, [page, pageSize, ordering, filters]);

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      campaigns: data?.data?.results || data?.results || [],
      campaignsCount: data?.data?.count || data?.count || 0,
      campaignsLoading: isLoading,
      campaignsError: error,
      campaignsValidating: isValidating,
      campaignsEmpty:
        !isLoading && !(data?.data?.results?.length || data?.results?.length),
    }),
    [data, isLoading, error, isValidating],
  );

  return memoizedValue;
}

/**
 * GET CAMPAIGN MEMBERS - Members for a specific campaign
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Object} {members, membersLoading, membersError}
 */
export function useGetCampaignMembers(campaignId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!campaignId || !isValidUUID(campaignId)) return null;
    const url = `${endpoints.membersByCampaign}?campaign_id=${campaignId}`;
    return tenantKey(url, tenantId);
  }, [campaignId, tenantId]);

  const { data, isLoading, error } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      members: data?.data?.results || data?.results || data?.data || [],
      membersLoading: isLoading,
      membersError: error,
    }),
    [data, isLoading, error],
  );

  return memoizedValue;
}

/**
 * GET CAMPAIGN OBJECTIVES - Objectives for a specific campaign
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Object} {objectives, objectivesLoading, objectivesError}
 */
export function useGetCampaignObjectives(campaignId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!campaignId || !isValidUUID(campaignId)) return null;
    const url = `${endpoints.objectivesByCampaign}?campaign_id=${campaignId}`;
    return tenantKey(url, tenantId);
  }, [campaignId, tenantId]);

  const { data, isLoading, error } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      objectives: data?.data?.results || data?.results || data?.data || [],
      objectivesLoading: isLoading,
      objectivesError: error,
    }),
    [data, isLoading, error],
  );

  return memoizedValue;
}

/**
 * GET OBJECTIVE CHOICES - Available objective types for dropdowns
 *
 * @returns {Object} {choices, choicesLoading, choicesError}
 */
export function useGetObjectiveChoices() {
  const { tenantId } = useAuth();

  const swrKey = tenantKey(endpoints.objectivesChoices, tenantId);

  const { data, isLoading, error } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      choices: data?.data || {},
      choicesLoading: isLoading,
      choicesError: error,
    }),
    [data, isLoading, error],
  );

  return memoizedValue;
}

// ==============================|| READ HOOKS - PLAYLIST ||============================== //

/**
 * GET CAMPAIGN PLAYLIST - Prioritized activity list
 *
 * @param {string} campaignId - UUID of the campaign
 * @param {Object} options - {executorId, limit}
 * @returns {Object} {activities, totalCount, playlistLoading, playlistError, playlistValidating, mutatePlaylist}
 */
export function useGetPlaylist(campaignId, options = {}) {
  const { tenantId } = useAuth();
  const { executorId, limit } = options;

  const swrKey = useMemo(() => {
    if (!campaignId || !isValidUUID(campaignId)) return null;
    const params = new URLSearchParams();
    if (executorId) params.append("executor_id", executorId);
    if (limit) params.append("limit", limit);
    const queryString = params.toString();
    const url = queryString
      ? `${endpoints.campaignPlaylist(campaignId)}?${queryString}`
      : endpoints.campaignPlaylist(campaignId);
    return tenantKey(url, tenantId);
  }, [campaignId, tenantId, executorId, limit]);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      activities: data?.data?.results || data?.results || [],
      totalCount: data?.data?.total_count || data?.total_count || 0,
      playlistLoading: isLoading,
      playlistError: error,
      playlistValidating: isValidating,
      mutatePlaylist: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );

  return memoizedValue;
}

// ==============================|| READ HOOKS - CAMPAIGN ACCOUNTS ||============================== //

/**
 * GET CAMPAIGN ACCOUNTS - Accounts enrolled in a campaign
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Object} {accounts, accountsCount, accountsLoading, accountsError, mutateAccounts}
 */
export function useGetCampaignAccounts(campaignId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!campaignId || !isValidUUID(campaignId)) return null;
    const url = `${endpoints.accountsByCampaign}?campaign_id=${campaignId}`;
    return tenantKey(url, tenantId);
  }, [campaignId, tenantId]);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  const memoizedValue = useMemo(
    () => ({
      accounts: data?.data?.results || data?.results || data?.data || [],
      accountsCount: data?.data?.count || data?.count || 0,
      accountsLoading: isLoading,
      accountsError: error,
      accountsValidating: isValidating,
      mutateAccounts: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );

  return memoizedValue;
}

// ==============================|| MUTATION FUNCTIONS - CAMPAIGN CRUD ||============================== //

/**
 * CREATE CAMPAIGN
 *
 * @param {Object} payload - Campaign data
 * @returns {Promise<Object>} {success, data?, error?, status?}
 */
export async function createCampaign(payload) {
  const sanitized = sanitizeObject(payload, ["name", "description"]);

  const result = await api.post(endpoints.campaigns, sanitized);

  if (result.success) {
    revalidateMultiple([endpoints.campaigns]);
    return { success: true, data: result.data };
  }

  return {
    success: false,
    error: result.error,
    status: result.status || 0,
    response: result.response || null,
  };
}

/**
 * UPDATE CAMPAIGN
 *
 * @param {string} campaignId - UUID of the campaign
 * @param {Object} payload - Campaign data to update
 * @returns {Promise<Object>} {success, data?, error?, status?}
 */
export async function updateCampaign(campaignId, payload) {
  if (!campaignId || !isValidUUID(campaignId)) {
    return { success: false, error: "Invalid campaign ID format", status: 400 };
  }

  const sanitized = sanitizeObject(payload, ["name", "description"]);

  const result = await api.patch(
    endpoints.campaignDetail(campaignId),
    sanitized,
  );

  if (result.success) {
    revalidateMultiple([
      endpoints.campaigns,
      endpoints.campaignDetail(campaignId),
    ]);
    return { success: true, data: result.data };
  }

  return {
    success: false,
    error: result.error,
    status: result.status || 0,
    response: result.response || null,
  };
}

/**
 * DELETE CAMPAIGN
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Promise<Object>} {success, status?, error?}
 */
export async function deleteCampaign(campaignId) {
  if (!campaignId || !isValidUUID(campaignId)) {
    return { success: false, error: "Invalid campaign ID format", status: 400 };
  }

  const result = await api.delete(endpoints.campaignDetail(campaignId));

  if (result.success || result.status === 204) {
    revalidateMultiple([endpoints.campaigns]);
    return { success: true, status: result.status ?? 204 };
  }

  return {
    success: false,
    error: result.error,
    status: result.status || 0,
    response: result.response || null,
  };
}

// ==============================|| MUTATION FUNCTIONS - LIFECYCLE ||============================== //

/**
 * START CAMPAIGN - DRAFT → ACTIVE
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Promise<Object>} {success, data?, error?}
 */
export async function startCampaign(campaignId) {
  const result = await api.post(endpoints.campaignStart(campaignId));

  if (result.success) {
    revalidateMultiple([
      endpoints.campaigns,
      endpoints.campaignDetail(campaignId),
      endpoints.campaignDashboard(campaignId),
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * PAUSE CAMPAIGN - ACTIVE → PAUSED
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Promise<Object>} {success, data?, error?}
 */
export async function pauseCampaign(campaignId) {
  const result = await api.post(endpoints.campaignPause(campaignId));

  if (result.success) {
    revalidateMultiple([
      endpoints.campaigns,
      endpoints.campaignDetail(campaignId),
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * RESUME CAMPAIGN - PAUSED → ACTIVE
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Promise<Object>} {success, data?, error?}
 */
export async function resumeCampaign(campaignId) {
  const result = await api.post(endpoints.campaignResume(campaignId));

  if (result.success) {
    revalidateMultiple([
      endpoints.campaigns,
      endpoints.campaignDetail(campaignId),
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * COMPLETE CAMPAIGN - ACTIVE/PAUSED → COMPLETED
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Promise<Object>} {success, data?, error?}
 */
export async function completeCampaign(campaignId) {
  const result = await api.post(endpoints.campaignComplete(campaignId));

  if (result.success) {
    revalidateMultiple([
      endpoints.campaigns,
      endpoints.campaignDetail(campaignId),
      endpoints.campaignDashboard(campaignId),
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * CANCEL CAMPAIGN - any non-final → CANCELLED
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Promise<Object>} {success, data?, error?}
 */
export async function cancelCampaign(campaignId) {
  const result = await api.post(endpoints.campaignCancel(campaignId));

  if (result.success) {
    revalidateMultiple([
      endpoints.campaigns,
      endpoints.campaignDetail(campaignId),
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

// ==============================|| MUTATION FUNCTIONS - MEMBERS ||============================== //

/**
 * ADD CAMPAIGN MEMBER
 *
 * @param {Object} payload - {campaign, user, role}
 * @returns {Promise<Object>} {success, data?, error?}
 */
export async function addCampaignMember(payload) {
  const result = await api.post(endpoints.members, payload);

  if (result.success) {
    revalidateMultiple([endpoints.members, endpoints.membersByCampaign]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * UPDATE CAMPAIGN MEMBER
 *
 * @param {string} memberId - UUID of the member
 * @param {Object} payload - Fields to update
 * @returns {Promise<Object>} {success, data?, error?}
 */
export async function updateCampaignMember(memberId, payload) {
  const result = await api.patch(endpoints.memberDetail(memberId), payload);

  if (result.success) {
    revalidateMultiple([endpoints.members, endpoints.membersByCampaign]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * REMOVE CAMPAIGN MEMBER
 *
 * @param {string} memberId - UUID of the member
 * @returns {Promise<Object>} {success, error?}
 */
export async function removeCampaignMember(memberId) {
  const result = await api.delete(endpoints.memberDetail(memberId));

  if (result.success || result.status === 204) {
    revalidateMultiple([endpoints.members, endpoints.membersByCampaign]);
    return { success: true };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

// ==============================|| MUTATION FUNCTIONS - PLAYLIST ||============================== //

/**
 * COMPLETE PLAYLIST ACTIVITY
 *
 * Completes an activity and revalidates campaign caches.
 *
 * @param {string} activityId - UUID of the activity
 * @param {string} campaignId - UUID of the campaign (for cache revalidation)
 * @param {Object} payload - {outcome, outcome_notes}
 * @returns {Promise<Object>} {success, data?, error?}
 */
export async function completePlaylistActivity(
  activityId,
  campaignId,
  payload,
) {
  if (!activityId) {
    return { success: false, error: "Activity ID is required", status: 400 };
  }

  const result = await api.post(
    endpoints.activityComplete(activityId),
    payload,
  );

  if (result.success) {
    revalidateMultiple([
      endpoints.campaignPlaylist(campaignId),
      endpoints.campaignDashboard(campaignId),
      endpoints.campaignDetail(campaignId),
      `${endpoints.accountsByCampaign}?campaign_id=${campaignId}`,
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

// ==============================|| MUTATION FUNCTIONS - CAMPAIGN ACCOUNTS ||============================== //

/**
 * ADD ACCOUNTS TO CAMPAIGN - Bulk enroll
 *
 * @param {string} campaignId - UUID of the campaign
 * @param {Array<string>} accountIds - Array of account UUIDs
 * @returns {Promise<Object>} {success, data?, error?}
 */
export async function addAccountsToCampaign(campaignId, accountIds) {
  if (!campaignId || !accountIds?.length) {
    return {
      success: false,
      error: "Campaign ID and account IDs are required",
      status: 400,
    };
  }

  const result = await api.post(endpoints.accountsBulkAdd, {
    campaign_id: campaignId,
    account_ids: accountIds,
  });

  if (result.success) {
    revalidateMultiple([
      `${endpoints.accountsByCampaign}?campaign_id=${campaignId}`,
      endpoints.campaignDashboard(campaignId),
      endpoints.campaignDetail(campaignId),
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * REMOVE ACCOUNT FROM CAMPAIGN - Single delete
 *
 * Only PENDING accounts can be removed.
 *
 * @param {string} campaignAccountId - UUID of the CampaignAccount record
 * @param {string} campaignId - UUID of the campaign (for cache revalidation)
 * @returns {Promise<Object>} {success, error?}
 */
export async function removeAccountFromCampaign(campaignAccountId, campaignId) {
  if (!campaignAccountId) {
    return {
      success: false,
      error: "Campaign account ID is required",
      status: 400,
    };
  }

  const result = await api.delete(
    endpoints.campaignAccountDetail(campaignAccountId),
  );

  if (result.success || result.status === 204) {
    revalidateMultiple([
      `${endpoints.accountsByCampaign}?campaign_id=${campaignId}`,
      endpoints.campaignDashboard(campaignId),
      endpoints.campaignDetail(campaignId),
    ]);
    return { success: true, status: result.status ?? 204 };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

// ==============================|| MUTATION FUNCTIONS - OBJECTIVES ||============================== //

/**
 * ADD CAMPAIGN OBJECTIVE
 *
 * @param {Object} payload - {campaign, objective_type, target_value, is_primary}
 * @returns {Promise<Object>} {success, data?, error?}
 */
export async function addCampaignObjective(payload) {
  const result = await api.post(endpoints.objectives, payload);

  if (result.success) {
    revalidateMultiple([endpoints.objectives, endpoints.objectivesByCampaign]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * UPDATE CAMPAIGN OBJECTIVE
 *
 * @param {string} objectiveId - UUID of the objective
 * @param {Object} payload - Fields to update
 * @returns {Promise<Object>} {success, data?, error?}
 */
export async function updateCampaignObjective(objectiveId, payload) {
  const result = await api.patch(
    endpoints.objectiveDetail(objectiveId),
    payload,
  );

  if (result.success) {
    revalidateMultiple([endpoints.objectives, endpoints.objectivesByCampaign]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * REMOVE CAMPAIGN OBJECTIVE
 *
 * @param {string} objectiveId - UUID of the objective
 * @returns {Promise<Object>} {success, error?}
 */
export async function removeCampaignObjective(objectiveId) {
  const result = await api.delete(endpoints.objectiveDetail(objectiveId));

  if (result.success || result.status === 204) {
    revalidateMultiple([endpoints.objectives, endpoints.objectivesByCampaign]);
    return { success: true };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

// ==============================|| MUTATION FUNCTIONS - EXECUTION ||============================== //

/**
 * GENERATE ACTIVITIES - Trigger activity generation for a campaign
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Promise<Object>} {success, data?, error?}
 */
export async function generateActivities(campaignId) {
  const result = await api.post(
    endpoints.campaignGenerateActivities(campaignId),
  );

  if (result.success) {
    revalidateMultiple([
      endpoints.campaignDetail(campaignId),
      endpoints.campaignDashboard(campaignId),
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Get activity completion progress percentage for a campaign
 * @param {Object} campaign - Campaign object with activities_total / activities_completed
 * @returns {number} Progress 0-100
 */
export const getCampaignProgress = (campaign) => {
  if (!campaign || !campaign.activities_total) return 0;
  return Math.round(
    (campaign.activities_completed / campaign.activities_total) * 100,
  );
};

/**
 * Get objective progress percentage for a campaign
 * @param {Object} campaign - Campaign object with objective_target / objective_current
 * @returns {number} Progress 0-100
 */
export const getObjectiveProgress = (campaign) => {
  if (!campaign || !campaign.objective_target) return 0;
  return Math.min(
    100,
    Math.round((campaign.objective_current / campaign.objective_target) * 100),
  );
};
