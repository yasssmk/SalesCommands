// frontend/src/api/campaigns/campaigns.js
/**
 * API hooks and mutations for Campaigns module.
 *
 * Connected to backend: app_modules/campaigns/
 * All endpoints verified against app_modules/campaigns/urls.py
 */

import useSWR from "swr";
import { useMemo } from "react";
import { useAuth } from "hooks/useAuth";
import { api } from "utils/axiosClient";
import { tenantKey, revalidateMultiple } from "api/_swr";
import { isValidUUID, sanitizeObject } from "utils/validators";

// ==============================|| CONSTANTS ||============================== //

export const CAMPAIGN_FAMILIES = {
  OUTBOUND: "OUTBOUND",
  TARGETED: "TARGETED",
};

export const CAMPAIGN_FAMILY_LABELS = {
  OUTBOUND: "Outbound",
  TARGETED: "Targeted",
};

export const CAMPAIGN_STATUSES = {
  DRAFT: "DRAFT",
  ACTIVE: "ACTIVE",
  PAUSED: "PAUSED",
  COMPLETED: "COMPLETED",
  CANCELLED: "CANCELLED",
};

export const CAMPAIGN_STATUS_LABELS = {
  DRAFT: "Draft",
  ACTIVE: "Active",
  PAUSED: "Paused",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

export const CAMPAIGN_STATUS_COLORS = {
  DRAFT: "default",
  ACTIVE: "success",
  PAUSED: "warning",
  COMPLETED: "primary",
  CANCELLED: "error",
};

export const SEQUENCE_TYPES = {
  CALL_EMAIL_CALL: "CALL_EMAIL_CALL",
  EMAIL_CALL_EMAIL: "EMAIL_CALL_EMAIL",
  CALL_ONLY: "CALL_ONLY",
  EMAIL_ONLY: "EMAIL_ONLY",
};

export const SEQUENCE_TYPE_LABELS = {
  CALL_EMAIL_CALL: "Call → Email → Call",
  EMAIL_CALL_EMAIL: "Email → Call → Email",
  CALL_ONLY: "Call Only",
  EMAIL_ONLY: "Email Only",
};

export const MEMBER_ROLES = {
  OWNER: "OWNER",
  EXECUTOR: "EXECUTOR",
  RECEIVER: "RECEIVER",
  OBSERVER: "OBSERVER",
};

export const MEMBER_ROLE_LABELS = {
  OWNER: "Owner",
  EXECUTOR: "Executor",
  RECEIVER: "Receiver",
  OBSERVER: "Observer",
};

export const OBJECTIVE_TYPES = {
  MEETINGS: "MEETINGS",
  DECISION_CYCLES: "DECISION_CYCLES",
  CONTACTS_REACHED: "CONTACTS_REACHED",
  PIPELINE_VALUE: "PIPELINE_VALUE",
  REVENUE_WON: "REVENUE_WON",
  NEW_LOGOS: "NEW_LOGOS",
};

export const OBJECTIVE_TYPE_LABELS = {
  MEETINGS: "Meetings Booked",
  DECISION_CYCLES: "Decision Cycles Created",
  CONTACTS_REACHED: "Contacts Reached",
  PIPELINE_VALUE: "Pipeline Value",
  REVENUE_WON: "Revenue Won",
  NEW_LOGOS: "New Logos",
};

// ==============================|| HELPERS ||============================== //

/**
 * Compute campaign completion progress percentage from stats.
 * Returns null if no data available.
 */
export function getCampaignProgress(campaign) {
  if (!campaign) return null;
  const total = campaign.activities_total || 0;
  const completed = campaign.activities_completed || 0;
  if (total === 0) return 0;
  return Math.round((completed / total) * 100);
}

export function getObjectiveProgress(campaign) {
  if (!campaign || !campaign.objective_target) return 0;
  return Math.min(
    100,
    Math.round((campaign.objective_current / campaign.objective_target) * 100),
  );
}

// ==============================|| ENDPOINTS ||============================== //

/**
 * All endpoints verified against app_modules/campaigns/urls.py
 */
const endpoints = {
  // Campaign CRUD
  campaigns: "/campaigns/",
  campaignDetail: (id) => `/campaigns/${id}/`,

  // Lifecycle
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

  // Members  (prefix: /campaigns/members/)
  members: "/campaigns/members/",
  memberDetail: (id) => `/campaigns/members/${id}/`,
  membersByCampaign: "/campaigns/members/by-campaign/",

  // Objectives  (prefix: /campaigns/objectives/)
  objectives: "/campaigns/objectives/",
  objectiveDetail: (id) => `/campaigns/objectives/${id}/`,
  objectivesByCampaign: "/campaigns/objectives/by-campaign/",
  objectivesChoices: "/campaigns/objectives/choices/",

  // Campaign Accounts  (prefix: /campaigns/accounts/)
  campaignAccounts: "/campaigns/accounts/",
  campaignAccountDetail: (id) => `/campaigns/accounts/${id}/`,
  accountsByCampaign: "/campaigns/accounts/by-campaign/",
  accountsBulkAdd: "/campaigns/accounts/bulk-add/",
  accountsBulkRemove: "/campaigns/accounts/bulk-remove/",

  // Cross-module: Activities
  activityComplete: (id) => `/module-activities/${id}/complete/`,
};

// ==============================|| HELPER - BUILD URL WITH PARAMS ||============================== //

const buildUrlWithParams = (baseUrl, params = {}) => {
  const { page, pageSize, search, ordering, filters = {} } = params;
  const queryParams = new URLSearchParams();

  if (page !== undefined && page !== null) queryParams.append("page", page);
  if (pageSize !== undefined && pageSize !== null)
    queryParams.append("page_size", pageSize);
  if (search) queryParams.append("search", search);
  if (ordering) queryParams.append("ordering", ordering);
  if (filters.owner_scope)
    queryParams.append("owner_scope", filters.owner_scope);
  if (filters.status) queryParams.append("status", filters.status);
  if (filters.campaign_type)
    queryParams.append("campaign_type", filters.campaign_type);
  if (filters.territory) queryParams.append("territory", filters.territory);

  const queryString = queryParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

// ==============================|| READ HOOKS - CAMPAIGNS ||============================== //

/**
 * GET CAMPAIGNS - Paginated list with filters
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

  const urlWithParams = useMemo(
    () =>
      buildUrlWithParams(endpoints.campaigns, {
        page,
        pageSize,
        search,
        ordering,
        filters,
      }),
    [page, pageSize, search, ordering, filters],
  );

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
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
}

/**
 * GET CAMPAIGN - Single campaign detail
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

  return useMemo(
    () => ({
      campaign: data?.data || data || null,
      campaignLoading: isLoading,
      campaignError: error,
      campaignValidating: isValidating,
    }),
    [data, isLoading, error, isValidating],
  );
}

/**
 * GET CAMPAIGN WORKSPACE - Campaign detail + dashboard stats combined
 */
export function useGetCampaignWorkspace(campaignId) {
  const { tenantId } = useAuth();

  const campaignKey = useMemo(() => {
    if (!campaignId || !isValidUUID(campaignId)) return null;
    return tenantKey(endpoints.campaignDetail(campaignId), tenantId);
  }, [campaignId, tenantId]);

  const dashboardKey = useMemo(() => {
    if (!campaignId || !isValidUUID(campaignId)) return null;
    return tenantKey(endpoints.campaignDashboard(campaignId), tenantId);
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

  const { data: dashboardData, isLoading: dashboardLoading } = useSWR(
    dashboardKey,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      shouldRetryOnError: true,
    },
  );

  return useMemo(
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
}

/**
 * GET MY CAMPAIGNS - Campaigns where current user is a member
 */
export function useGetMyCampaigns(options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 50, ordering = "", filters = {} } = options;

  const urlWithParams = useMemo(
    () =>
      buildUrlWithParams(endpoints.myCampaigns, {
        page,
        pageSize,
        ordering,
        filters,
      }),
    [page, pageSize, ordering, filters],
  );

  const swrKey = tenantKey(urlWithParams, tenantId);

  const { data, isLoading, error, isValidating } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
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
}

// ==============================|| READ HOOKS - PLAYLIST ||============================== //

/**
 * GET CAMPAIGN PLAYLIST - Prioritized activity list for a campaign
 *
 * @param {string} campaignId
 * @param {Object} options - {executorId, limit}
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

  return useMemo(
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
}

// ==============================|| READ HOOKS - CAMPAIGN ACCOUNTS ||============================== //

/**
 * GET CAMPAIGN ACCOUNTS - Accounts enrolled in a campaign, with server-side pagination
 *
 * @param {string} campaignId
 * @param {Object} options - {page, pageSize}
 */
export function useGetCampaignAccounts(campaignId, options = {}) {
  const { tenantId } = useAuth();
  const { page = 1, pageSize = 50 } = options;

  const swrKey = useMemo(() => {
    if (!campaignId || !isValidUUID(campaignId)) return null;
    const params = new URLSearchParams();
    params.append("campaign_id", campaignId);
    params.append("page", page);
    params.append("page_size", pageSize);
    const url = `${endpoints.accountsByCampaign}?${params.toString()}`;
    return tenantKey(url, tenantId);
  }, [campaignId, tenantId, page, pageSize]);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
    () => ({
      accounts: data?.data?.results || data?.results || [],
      accountsCount: data?.data?.count || data?.count || 0,
      accountsLoading: isLoading,
      accountsError: error,
      accountsValidating: isValidating,
      mutateAccounts: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );
}

// ==============================|| READ HOOKS - MEMBERS ||============================== //

/**
 * GET CAMPAIGN MEMBERS - Members for a specific campaign
 */
export function useGetCampaignMembers(campaignId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!campaignId || !isValidUUID(campaignId)) return null;
    const url = `${endpoints.membersByCampaign}?campaign_id=${campaignId}`;
    return tenantKey(url, tenantId);
  }, [campaignId, tenantId]);

  const { data, isLoading, error, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
    () => ({
      members: data?.data?.results || data?.results || [],
      membersLoading: isLoading,
      membersError: error,
      mutateMembers: mutate,
    }),
    [data, isLoading, error, mutate],
  );
}

// ==============================|| READ HOOKS - OBJECTIVES ||============================== //

/**
 * GET CAMPAIGN OBJECTIVES - Objectives for a specific campaign
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

  return useMemo(
    () => ({
      objectives: data?.data?.results || data?.results || data?.data || [],
      objectivesLoading: isLoading,
      objectivesError: error,
    }),
    [data, isLoading, error],
  );
}

/**
 * GET OBJECTIVE CHOICES - Available objective types for dropdowns
 */
export function useGetObjectiveChoices() {
  const { tenantId } = useAuth();
  const swrKey = tenantKey(endpoints.objectivesChoices, tenantId);

  const { data, isLoading, error } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
    () => ({
      choices: data?.data || {},
      choicesLoading: isLoading,
      choicesError: error,
    }),
    [data, isLoading, error],
  );
}

// ==============================|| MUTATION FUNCTIONS - CAMPAIGN CRUD ||============================== //

/**
 * CREATE CAMPAIGN
 */
export async function createCampaign(payload) {
  const sanitized = sanitizeObject(payload, ["name", "description"]);
  const result = await api.post(endpoints.campaigns, sanitized);

  if (result.success) {
    revalidateMultiple([endpoints.campaigns, endpoints.myCampaigns]);
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
 */
export async function deleteCampaign(campaignId) {
  if (!campaignId || !isValidUUID(campaignId)) {
    return { success: false, error: "Invalid campaign ID format", status: 400 };
  }

  const result = await api.delete(endpoints.campaignDetail(campaignId));

  if (result.success || result.status === 204) {
    revalidateMultiple([endpoints.campaigns, endpoints.myCampaigns]);
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
 */
export async function startCampaign(campaignId) {
  const result = await api.post(endpoints.campaignStart(campaignId));

  if (result.success) {
    revalidateMultiple([
      endpoints.campaigns,
      endpoints.campaignDetail(campaignId),
      endpoints.campaignDashboard(campaignId),
      endpoints.campaignPlaylist(campaignId),
      `${endpoints.accountsByCampaign}?campaign_id=${campaignId}&page=1&page_size=50`,
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * PAUSE CAMPAIGN - ACTIVE → PAUSED
 */
export async function pauseCampaign(campaignId) {
  const result = await api.post(endpoints.campaignPause(campaignId));

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
 * RESUME CAMPAIGN - PAUSED → ACTIVE
 */
export async function resumeCampaign(campaignId) {
  const result = await api.post(endpoints.campaignResume(campaignId));

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
 * COMPLETE CAMPAIGN - ACTIVE/PAUSED → COMPLETED
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
 * CANCEL CAMPAIGN
 */
export async function cancelCampaign(campaignId) {
  const result = await api.post(endpoints.campaignCancel(campaignId));

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
 * GENERATE CAMPAIGN ACTIVITIES
 * POST /campaigns/{id}/generate-activities/
 *
 * Generates activities for all enrolled accounts based on campaign sequence.
 *
 * @param {string} campaignId
 * @param {Object} payload - Optional { activity_type }
 */
export async function generateCampaignActivities(campaignId, payload = {}) {
  if (!campaignId || !isValidUUID(campaignId)) {
    return { success: false, error: "Invalid campaign ID format", status: 400 };
  }

  const result = await api.post(
    endpoints.campaignGenerateActivities(campaignId),
    payload,
  );

  if (result.success) {
    revalidateMultiple([
      endpoints.campaignPlaylist(campaignId),
      endpoints.campaignDashboard(campaignId),
      endpoints.campaignDetail(campaignId),
      `${endpoints.accountsByCampaign}?campaign_id=${campaignId}&page=1&page_size=50`,
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

// ==============================|| MUTATION FUNCTIONS - MEMBERS ||============================== //

/**
 * ADD CAMPAIGN MEMBER
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
 */
export async function updateCampaignMember(memberId, payload) {
  const result = await api.patch(endpoints.memberDetail(memberId), payload);

  if (result.success) {
    revalidateMultiple([
      endpoints.members,
      endpoints.membersByCampaign,
      endpoints.campaignDashboard(payload.campaign_id),
      endpoints.campaignDetail(payload.campaign_id),
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * REMOVE CAMPAIGN MEMBER
 *
 * @param {string} memberId - UUID of the member
 * @param {string} campaignId - UUID of the campaign (for dashboard revalidation)
 * @returns {Promise<Object>} {success, error?}
 */
export async function removeCampaignMember(memberId, campaignId) {
  const result = await api.delete(endpoints.memberDetail(memberId));

  if (result.success || result.status === 204) {
    revalidateMultiple([
      endpoints.members,
      endpoints.membersByCampaign,
      ...(campaignId
        ? [
            endpoints.campaignDashboard(campaignId),
            endpoints.campaignDetail(campaignId),
          ]
        : []),
    ]);
    return { success: true };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

// ==============================|| MUTATION FUNCTIONS - PLAYLIST ||============================== //

/**
 * COMPLETE PLAYLIST ACTIVITY
 * Calls /module-activities/{id}/complete/ (cross-module).
 *
 * @param {string} activityId
 * @param {string} campaignId - For cache revalidation
 * @param {Object} payload - {outcome, outcome_notes}
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
      `${endpoints.accountsByCampaign}?campaign_id=${campaignId}&page=1&page_size=50`,
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

// ==============================|| MUTATION FUNCTIONS - CAMPAIGN ACCOUNTS ||============================== //

/**
 * ADD ACCOUNTS TO CAMPAIGN - Bulk enroll
 * POST /campaigns/accounts/bulk-add/
 * Body: { campaign_id, account_ids: [UUID] }
 */
export async function addAccountsToCampaign(campaignId, accountIds) {
  if (!campaignId || !accountIds?.length) {
    return {
      success: false,
      error: "campaign_id and account_ids are required",
      status: 400,
    };
  }

  const result = await api.post(endpoints.accountsBulkAdd, {
    campaign_id: campaignId,
    account_ids: accountIds,
  });

  if (result.success) {
    revalidateMultiple([
      endpoints.campaignDashboard(campaignId),
      `${endpoints.accountsByCampaign}?campaign_id=${campaignId}&page=1&page_size=50`,
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * REMOVE ACCOUNT FROM CAMPAIGN
 * DELETE /campaigns/accounts/{campaignAccountId}/
 *
 * @param {string} campaignAccountId - UUID of the CampaignAccount record (not the account)
 * @param {string} campaignId - For cache revalidation
 */
export async function removeAccountFromCampaign(campaignAccountId, campaignId) {
  if (!campaignAccountId) {
    return {
      success: false,
      error: "campaignAccountId is required",
      status: 400,
    };
  }

  const result = await api.delete(
    endpoints.campaignAccountDetail(campaignAccountId),
  );

  if (result.success || result.status === 204) {
    revalidateMultiple([
      endpoints.campaignDashboard(campaignId),
      `${endpoints.accountsByCampaign}?campaign_id=${campaignId}&page=1&page_size=50`,
    ]);
    return { success: true };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}
