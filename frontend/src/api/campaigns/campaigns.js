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

export const CAMPAIGN_TYPES = {
  OUTBOUND: "OUTBOUND",
};

export const CAMPAIGN_TYPE_LABELS = {
  OUTBOUND: "Outbound Sequence",
  TARGETED: "Targeted Campaign",
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
  campaignLogResponse: (id) => `/campaigns/${id}/log-response/`,
  campaignCancelPlanned: (id) => `/campaigns/${id}/cancel-planned/`,

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
  accountsEnrollTarget: "/campaigns/accounts/enroll-target/",
  accountToggleContact: (id) => `/campaigns/accounts/${id}/toggle-contact/`,

  // Targeted campaign singleton
  campaignTargeted: "/campaigns/targeted/",

  // Campaign contacts — pause/resume sequence
  campaignContactPause: (id) => `/campaigns/contacts/${id}/pause/`,
  campaignContactResume: (id) => `/campaigns/contacts/${id}/resume/`,
  campaignContactStop: (id) => `/campaigns/contacts/${id}/mark-stopped/`,
  campaignContactReactivate: (id) => `/campaigns/contacts/${id}/reactivate/`,

  // Campaign contacts — list by campaign
  contactsByCampaign: "/campaigns/contacts/",

  // Cross-module: Activities
  activityComplete: (id) => `/module-activities/${id}/complete/`,
  activityRecordNoAnswer: (id) => `/module-activities/${id}/record-no-answer/`,
  moduleActivities: "/module-activities/",

  // Campaign Contacts
  campaignContactResumeCallback: (id) =>
    `/campaigns/contacts/${id}/resume-callback/`,
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

// ==============================|| SWR HOOK - COMPLETED ACTIVITIES ||============================== //

/**
 * GET COMPLETED ACTIVITIES FOR A CAMPAIGN
 * Fetches all COMPLETED activities scoped to a campaign.
 *
 * @param {string|null} campaignId
 * @returns {{ activities, completedActivitiesLoading, mutateCompleted }}
 */
export function useGetCompletedActivities(campaignId, page = 1) {
  const { tenantId } = useAuth();

  const url =
    campaignId && isValidUUID(campaignId)
      ? `/module-activities/?campaign=${campaignId}&status=COMPLETED&ordering=-completed_at&page_size=25&page=${page}`
      : null;

  const { data, isLoading, mutate } = useSWR(
    url ? tenantKey(url, tenantId) : null,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      dedupingInterval: 30000,
    },
  );

  return useMemo(
    () => ({
      activities: data?.data?.results || data?.results || [],
      completedActivitiesTotalCount: data?.data?.count || data?.count || 0,
      completedActivitiesLoading: isLoading,
      mutateCompleted: mutate,
    }),
    [data, isLoading, mutate],
  );
}

// ==============================|| SWR HOOK - CAMPAIGN ACTIVITIES ||============================== //

/**
 * GET ALL ACTIVITIES FOR A CAMPAIGN (table view).
 * Uses cross-module activities endpoint with campaign filter.
 *
 * @param {string|null} campaignId
 * @returns {{ activities, activitiesLoading, activitiesError }}
 */
export function useGetCampaignActivities(campaignId) {
  const { tenantId } = useAuth();

  const url =
    campaignId && isValidUUID(campaignId)
      ? `${endpoints.moduleActivities}?campaign=${campaignId}&page_size=100`
      : null;

  const { data, isLoading, error } = useSWR(
    url ? tenantKey(url, tenantId) : null,
    { revalidateOnFocus: false, dedupingInterval: 30000 },
  );

  return useMemo(
    () => ({
      activities: data?.data?.results || data?.results || [],
      activitiesLoading: isLoading,
      activitiesError: error,
    }),
    [data, isLoading, error],
  );
}

// ==============================|| MUTATION - LOG RESPONSE ||============================== //

/**
 * LOG ASYNC RESPONSE
 * POST /campaigns/{id}/log-response/
 *
 * @param {string} campaignId
 * @param {{ activity_id, response, notes?, response_date? }} payload
 */
export async function logCampaignResponse(campaignId, payload) {
  if (!campaignId || !isValidUUID(campaignId)) {
    return { success: false, error: "Invalid campaign ID format", status: 400 };
  }

  const result = await api.post(
    endpoints.campaignLogResponse(campaignId),
    payload,
  );

  if (result.success || result.status === 200) {
    revalidateMultiple([
      endpoints.campaignPlaylist(campaignId),
      endpoints.campaignDashboard(campaignId),
      `${endpoints.accountsByCampaign}?campaign_id=${campaignId}&page=1&page_size=50`,
      `${endpoints.contactsByCampaign}?campaign=${campaignId}&page_size=200`,
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

// ==============================|| MUTATION - CANCEL PLANNED ACTIVITIES ||============================== //

/**
 * CANCEL PLANNED ACTIVITIES
 * DELETE /campaigns/{id}/cancel-planned/
 *
 * @param {string} campaignId
 * @param {{ scope: 'contact'|'account', account_id: string, contact_id?: string }} payload
 */
export async function cancelPlannedActivities(campaignId, payload) {
  if (!campaignId || !isValidUUID(campaignId)) {
    return { success: false, error: "Invalid campaign ID format", status: 400 };
  }

  const result = await api.delete(endpoints.campaignCancelPlanned(campaignId), {
    data: payload,
  });

  if (result.success || result.status === 200) {
    revalidateMultiple([
      endpoints.campaignPlaylist(campaignId),
      endpoints.campaignDashboard(campaignId),
      `${endpoints.accountsByCampaign}?campaign_id=${campaignId}&page=1&page_size=50`,
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

// ==============================|| MUTATION - RESUME CONTACT CALLBACK ||============================== //

/**
 * RESUME CONTACT CALLBACK
 * POST /campaigns/contacts/{contactId}/resume-callback/
 *
 * Transitions CampaignContact from CALLBACK_PENDING → IN_PROGRESS.
 * Used by the PAUSED section "Cancel Pause" button in the playlist.
 *
 * @param {string} campaignContactId - UUID of the CampaignContact record
 * @param {string} campaignId - For cache revalidation
 */
export async function resumeContactCallback(campaignContactId, campaignId) {
  if (!campaignContactId || !isValidUUID(campaignContactId)) {
    return { success: false, error: "Invalid contact ID format", status: 400 };
  }

  const result = await api.post(
    endpoints.campaignContactResumeCallback(campaignContactId),
  );

  if (result.success) {
    revalidateMultiple([
      endpoints.campaignPlaylist(campaignId),
      endpoints.campaignDashboard(campaignId),
      `${endpoints.accountsByCampaign}?campaign_id=${campaignId}&page=1&page_size=50`,
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

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

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
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
      mutateCampaigns: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
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
    revalidateOnFocus: true,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
    dedupingInterval: 5000,
    refreshInterval: 60000,
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

// ==============================|| READ HOOKS - TARGETED CAMPAIGN ||============================== //

/**
 * GET OR CREATE TARGETED CAMPAIGN — singleton per user.
 * GET /campaigns/targeted/?sequence_type=TARGETED
 *
 * Always returns an ACTIVE campaign. Creates it on first call.
 */
export function useGetTargetedCampaign(sequenceType = "TARGETED") {
  const { tenantId } = useAuth();

  const url = `${endpoints.campaignTargeted}?sequence_type=${sequenceType}`;
  const swrKey = tenantKey(url, tenantId);

  const { data, isLoading, error, isValidating, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
    () => ({
      targetedCampaign: data?.data || null,
      targetedLoading: isLoading,
      targetedError: error,
      targetedValidating: isValidating,
      mutateTargeted: mutate,
    }),
    [data, isLoading, error, isValidating, mutate],
  );
}

/**
 * GET CAMPAIGN CONTACTS — contacts enrolled in a campaign.
 * Used by TargetsTab to list all CampaignContact rows.
 *
 * @param {string} campaignId
 */
export function useGetCampaignContacts(campaignId) {
  const { tenantId } = useAuth();

  const swrKey = useMemo(() => {
    if (!campaignId || !isValidUUID(campaignId)) return null;
    const url = `${endpoints.contactsByCampaign}?campaign=${campaignId}&page_size=200`;
    return tenantKey(url, tenantId);
  }, [campaignId, tenantId]);

  const { data, isLoading, error, mutate } = useSWR(swrKey, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: true,
  });

  return useMemo(
    () => ({
      campaignContacts:
        data?.data?.results || data?.data || data?.results || [],
      campaignContactsLoading: isLoading,
      campaignContactsError: error,
      mutateCampaignContacts: mutate,
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
      endpoints.campaignPlaylist(campaignId),
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
      endpoints.campaignPlaylist(campaignId),
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * COMPLETE CAMPAIGN - ACTIVE/PAUSED → COMPLETED
 *
 * If open contacts exist (PLANNED activities remaining), the backend returns
 * requires_confirmation=true and open_contacts=[...] so the frontend can
 * offer a transfer to the TARGETED campaign before finalising.
 *
 * @param {string} campaignId
 * @returns {{ success, data: { campaign, requires_confirmation, open_contacts } }}
 */
export async function completeCampaign(campaignId, { force = false } = {}) {
  const result = await api.post(endpoints.campaignComplete(campaignId), {
    ...(force && { force: true }),
  });

  if (result.success) {
    // Unwrap double-enveloppe: apiRequest → {success, data: response.data}
    // backend → {success, data: {campaign, requires_confirmation, open_contacts}}
    const data = result.data?.data ?? result.data;
    const requiresConfirmation = data?.requires_confirmation === true;

    if (!requiresConfirmation) {
      revalidateMultiple([
        endpoints.campaigns,
        endpoints.campaignDetail(campaignId),
        endpoints.campaignDashboard(campaignId),
        endpoints.campaignPlaylist(campaignId),
      ]);
    }
    return {
      success: true,
      data: result.data,
      requiresConfirmation,
      openContacts: data?.open_contacts || [],
    };
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
      `/module-activities/?campaign=${campaignId}&status=COMPLETED&page_size=200`,
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * RECORD CALL NO ANSWER
 * POST /module-activities/{id}/record-no-answer/
 * Increments attempt counter. Activity stays PLANNED until threshold.
 */
export async function recordCallNoAnswer(activityId, outcomeNotes) {
  try {
    const res = await api.post(endpoints.activityRecordNoAnswer(activityId), {
      outcome_notes: outcomeNotes || undefined,
    });
    return res.data;
  } catch (err) {
    return {
      success: false,
      error: err?.response?.data,
      status: err?.response?.status,
    };
  }
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

/**
 * TOGGLE CONTACT on a CampaignAccount
 *
 * POST /campaigns/accounts/{campaignAccountId}/toggle-contact/
 * Body: { contact_id }
 *
 * Adds or removes a contact from target_contacts. When adding to an ACTIVE
 * campaign with activities already generated, activities are auto-created.
 * When removing, PLANNED activities for that contact are deleted.
 */
export async function toggleAccountContact(campaignAccountId, contactId) {
  if (!campaignAccountId || !contactId) {
    return {
      success: false,
      error: "campaignAccountId and contactId are required",
      status: 400,
    };
  }

  const result = await api.post(
    endpoints.accountToggleContact(campaignAccountId),
    { contact_id: contactId },
  );

  if (result.success) {
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status ?? 0 };
}

// ==============================|| MUTATION FUNCTIONS - TARGETED CAMPAIGN ||============================== //

/**
 * ENROLL TARGET — add a contact/account/department to the targeted campaign.
 * POST /campaigns/accounts/bulk-add/  (account enrollment)
 * then toggle-contact for specific contacts.
 *
 * @param {string} campaignId
 * @param {{ type: 'CONTACT'|'ACCOUNT'|'DEPARTMENT', account_id, contact_ids?, department_id? }} payload
 */
export async function enrollTarget(campaignId, payload) {
  if (!campaignId || !isValidUUID(campaignId)) {
    return { success: false, error: "Invalid campaign ID format", status: 400 };
  }

  const {
    account_id,
    contact_ids = [],
    department_id,
    type,
    origin_decision_cycle_id,
    notes,
  } = payload;

  if (!account_id) {
    return { success: false, error: "account_id is required", status: 400 };
  }

  const result = await api.post(endpoints.accountsEnrollTarget, {
    campaign_id: campaignId,
    account_id,
    type: type || "ACCOUNT",
    contact_ids,
    department_id: department_id || undefined,
    origin_decision_cycle_id: origin_decision_cycle_id || undefined,
    notes: notes || undefined,
  });

  if (!result.success) {
    return { success: false, error: result.error, status: result.status || 0 };
  }

  revalidateMultiple([
    endpoints.campaignTargeted,
    endpoints.campaignPlaylist(campaignId),
    endpoints.campaignDashboard(campaignId),
    endpoints.campaignDetail(campaignId),
    `${endpoints.contactsByCampaign}?campaign=${campaignId}&page_size=200`,
    `${endpoints.accountsByCampaign}?campaign_id=${campaignId}&page=1&page_size=50`,
  ]);

  return { success: true, data: result.data };
}

/**
 * REMOVE TARGETS — bulk remove CampaignContact rows.
 * Cancels PLANNED activities and removes from playlist.
 *
 * @param {string} campaignId - For cache revalidation
 * @param {string[]} campaignContactIds - UUIDs of CampaignContact records
 */
export async function removeTargets(campaignId, campaignContactIds) {
  if (!campaignContactIds?.length) {
    return { success: false, error: "No targets selected", status: 400 };
  }

  const results = await Promise.allSettled(
    campaignContactIds.map((id) => api.delete(`/campaigns/contacts/${id}/`)),
  );

  const failed = results.filter(
    (r) => r.status === "rejected" || !r.value?.success,
  );

  revalidateMultiple([
    endpoints.campaignPlaylist(campaignId),
    endpoints.campaignDashboard(campaignId),
    `${endpoints.contactsByCampaign}?campaign=${campaignId}&page_size=200`,
    `${endpoints.accountsByCampaign}?campaign_id=${campaignId}&page=1&page_size=50`,
  ]);

  if (failed.length > 0) {
    return {
      success: false,
      error: `${failed.length} target(s) could not be removed`,
      status: 207,
    };
  }

  return { success: true };
}

/**
 * PAUSE TARGET — PUT contact's PLANNED activities ON_HOLD.
 * Activities remain in playlist (Upcoming, end of list, warning style).
 *
 * @param {string} campaignContactId - UUID of CampaignContact
 * @param {string} campaignId - For cache revalidation
 */
export async function pauseTarget(campaignContactId, campaignId) {
  if (!campaignContactId || !isValidUUID(campaignContactId)) {
    return { success: false, error: "Invalid contact ID format", status: 400 };
  }

  const result = await api.post(
    endpoints.campaignContactPause(campaignContactId),
  );

  if (result.success) {
    revalidateMultiple([
      endpoints.campaignPlaylist(campaignId),
      `${endpoints.contactsByCampaign}?campaign=${campaignId}&page_size=200`,
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * RESUME TARGET — restore ON_HOLD activities to PLANNED with recalculated dates.
 *
 * @param {string} campaignContactId - UUID of CampaignContact
 * @param {string} campaignId - For cache revalidation
 */
export async function resumeTarget(campaignContactId, campaignId) {
  if (!campaignContactId || !isValidUUID(campaignContactId)) {
    return { success: false, error: "Invalid contact ID format", status: 400 };
  }

  const result = await api.post(
    endpoints.campaignContactResume(campaignContactId),
  );

  if (result.success) {
    revalidateMultiple([
      endpoints.campaignPlaylist(campaignId),
      `${endpoints.contactsByCampaign}?campaign=${campaignId}&page_size=200`,
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * STOP TARGET — transition contact to STOPPED.
 *
 * @param {string} campaignContactId - UUID of CampaignContact
 * @param {string} campaignId - For cache revalidation
 */
export async function stopTarget(campaignContactId, campaignId) {
  if (!campaignContactId || !isValidUUID(campaignContactId)) {
    return { success: false, error: "Invalid contact ID format", status: 400 };
  }

  const result = await api.post(
    endpoints.campaignContactStop(campaignContactId),
  );

  if (result.success) {
    revalidateMultiple([
      endpoints.campaignPlaylist(campaignId),
      `${endpoints.contactsByCampaign}?campaign=${campaignId}&page_size=200`,
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}

/**
 * REACTIVATE TARGET — reset a COMPLETED/STOPPED contact for a new sequence.
 * Only valid for TARGETED campaigns.
 *
 * @param {string} campaignContactId - UUID of CampaignContact
 * @param {string} campaignId - For cache revalidation
 */
export async function reactivateTarget(campaignContactId, campaignId) {
  if (!campaignContactId || !isValidUUID(campaignContactId)) {
    return { success: false, error: "Invalid contact ID format", status: 400 };
  }

  const result = await api.post(
    endpoints.campaignContactReactivate(campaignContactId),
  );

  if (result.success) {
    revalidateMultiple([
      endpoints.campaignPlaylist(campaignId),
      endpoints.campaignDashboard(campaignId),
      `${endpoints.contactsByCampaign}?campaign=${campaignId}&page_size=200`,
    ]);
    return { success: true, data: result.data };
  }

  return { success: false, error: result.error, status: result.status || 0 };
}
