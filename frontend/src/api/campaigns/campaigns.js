// frontend/src/api/campaigns/campaigns.js
/**
 * API hooks and mutations for Campaigns module.
 *
 * Follows the same patterns as territories.js for consistency.
 * Phase A: Mock data + stub hooks. Real API calls will replace mocks later.
 */

import useSWR from 'swr';
import { useMemo } from 'react';
import { useAuth } from 'hooks/useAuth';
import { api } from 'utils/axiosClient';
import { tenantKey, revalidateMultiple } from 'api/_swr';
import { isValidUUID, sanitizeObject } from 'utils/validators';

// ==============================|| CONSTANTS ||============================== //

/**
 * Campaign families (high-level grouping)
 */
export const CAMPAIGN_FAMILIES = {
  PROSPECTION: 'PROSPECTION',
  CHASING: 'CHASING'
};

/**
 * Campaign family labels for UI display
 */
export const CAMPAIGN_FAMILY_LABELS = {
  PROSPECTION: 'Prospection',
  CHASING: 'Chasing'
};

/**
 * Campaign statuses (matching future backend CampaignStatus choices)
 */
export const CAMPAIGN_STATUSES = {
  DRAFT: 'DRAFT',
  ACTIVE: 'ACTIVE',
  PAUSED: 'PAUSED',
  COMPLETED: 'COMPLETED',
  CANCELLED: 'CANCELLED'
};

/**
 * Campaign status labels for UI display
 */
export const CAMPAIGN_STATUS_LABELS = {
  DRAFT: 'Draft',
  ACTIVE: 'Active',
  PAUSED: 'Paused',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled'
};

/**
 * Status colors for MUI Chip color prop
 */
export const CAMPAIGN_STATUS_COLORS = {
  DRAFT: 'default',
  ACTIVE: 'success',
  PAUSED: 'warning',
  COMPLETED: 'primary',
  CANCELLED: 'error'
};

/**
 * Sequence types for prospection campaigns
 */
export const SEQUENCE_TYPES = {
  CALL_EMAIL_CALL: 'CALL_EMAIL_CALL',
  EMAIL_CALL_EMAIL: 'EMAIL_CALL_EMAIL',
  CALL_ONLY: 'CALL_ONLY',
  EMAIL_ONLY: 'EMAIL_ONLY'
};

/**
 * Sequence type labels for UI display
 */
export const SEQUENCE_TYPE_LABELS = {
  CALL_EMAIL_CALL: 'Call → Email → Call',
  EMAIL_CALL_EMAIL: 'Email → Call → Email',
  CALL_ONLY: 'Call Only',
  EMAIL_ONLY: 'Email Only'
};

/**
 * Campaign member roles
 */
export const MEMBER_ROLES = {
  OWNER: 'OWNER',
  EXECUTOR: 'EXECUTOR',
  OBSERVER: 'OBSERVER'
};

/**
 * Member role labels for UI display
 */
export const MEMBER_ROLE_LABELS = {
  OWNER: 'Owner',
  EXECUTOR: 'Executor',
  OBSERVER: 'Observer'
};

/**
 * Objective types
 */
export const OBJECTIVE_TYPES = {
  LEADS: 'LEADS',
  MEETINGS: 'MEETINGS',
  OPPORTUNITIES: 'OPPORTUNITIES',
  PIPELINE_VALUE: 'PIPELINE_VALUE',
  REVENUE: 'REVENUE'
};

/**
 * Objective type labels for UI display
 */
export const OBJECTIVE_TYPE_LABELS = {
  LEADS: 'Leads Generated',
  MEETINGS: 'Meetings Booked',
  OPPORTUNITIES: 'Opportunities Created',
  PIPELINE_VALUE: 'Pipeline Value',
  REVENUE: 'Revenue'
};

// ==============================|| MOCK DATA ||============================== //

/**
 * Mock campaigns for frontend development.
 * Will be replaced by real API calls when backend is ready.
 */
export const MOCK_CAMPAIGNS = [
  {
    id: 'mock-camp-001',
    name: 'Q1 Outbound — Mid-Market DACH',
    description: 'Prospection campaign targeting mid-market accounts in DACH region.',
    family: 'PROSPECTION',
    sequence_type: 'CALL_EMAIL_CALL',
    status: 'ACTIVE',
    territory_id: 'mock-territory-001',
    territory_name: 'Mid-Market DACH',
    start_date: '2026-01-15',
    end_date: '2026-03-31',
    accounts_count: 48,
    activities_total: 144,
    activities_completed: 67,
    objective_type: 'MEETINGS',
    objective_target: 20,
    objective_current: 8,
    members: [
      { id: 'mock-member-001', user_name: 'Alice Martin', role: 'OWNER', is_primary_owner: true },
      { id: 'mock-member-002', user_name: 'Bob Dupont', role: 'EXECUTOR', is_primary_owner: false }
    ],
    created_by_name: 'Alice Martin',
    created_at: '2026-01-10T09:00:00Z',
    updated_at: '2026-02-18T14:30:00Z'
  },
  {
    id: 'mock-camp-002',
    name: 'Chasing — Open Opportunities',
    description: 'Follow-up campaign for all accounts with open decision cycles.',
    family: 'CHASING',
    sequence_type: null,
    status: 'ACTIVE',
    territory_id: null,
    territory_name: null,
    start_date: '2026-02-01',
    end_date: null,
    accounts_count: 23,
    activities_total: 46,
    activities_completed: 12,
    objective_type: 'OPPORTUNITIES',
    objective_target: 10,
    objective_current: 3,
    members: [
      { id: 'mock-member-003', user_name: 'Alice Martin', role: 'OWNER', is_primary_owner: true }
    ],
    created_by_name: 'Alice Martin',
    created_at: '2026-01-28T11:00:00Z',
    updated_at: '2026-02-17T16:45:00Z'
  },
  {
    id: 'mock-camp-003',
    name: 'Q1 Email Nurture — Enterprise FR',
    description: 'Email-only sequence for enterprise French accounts.',
    family: 'PROSPECTION',
    sequence_type: 'EMAIL_ONLY',
    status: 'DRAFT',
    territory_id: 'mock-territory-002',
    territory_name: 'Enterprise France',
    start_date: null,
    end_date: null,
    accounts_count: 0,
    activities_total: 0,
    activities_completed: 0,
    objective_type: 'LEADS',
    objective_target: 50,
    objective_current: 0,
    members: [
      { id: 'mock-member-004', user_name: 'Charlie Roux', role: 'OWNER', is_primary_owner: true }
    ],
    created_by_name: 'Charlie Roux',
    created_at: '2026-02-15T10:00:00Z',
    updated_at: '2026-02-15T10:00:00Z'
  },
  {
    id: 'mock-camp-004',
    name: 'H2 2025 — SMB Benelux',
    description: 'Completed prospection campaign for SMB segment in Benelux.',
    family: 'PROSPECTION',
    sequence_type: 'CALL_EMAIL_CALL',
    status: 'COMPLETED',
    territory_id: 'mock-territory-003',
    territory_name: 'SMB Benelux',
    start_date: '2025-07-01',
    end_date: '2025-12-31',
    accounts_count: 65,
    activities_total: 195,
    activities_completed: 195,
    objective_type: 'MEETINGS',
    objective_target: 30,
    objective_current: 34,
    members: [
      { id: 'mock-member-005', user_name: 'Bob Dupont', role: 'OWNER', is_primary_owner: true },
      { id: 'mock-member-006', user_name: 'Alice Martin', role: 'EXECUTOR', is_primary_owner: false }
    ],
    created_by_name: 'Bob Dupont',
    created_at: '2025-06-20T08:00:00Z',
    updated_at: '2025-12-31T18:00:00Z'
  },
  {
    id: 'mock-camp-005',
    name: 'Cancelled — UK Expansion',
    description: 'Campaign cancelled due to market conditions.',
    family: 'PROSPECTION',
    sequence_type: 'CALL_ONLY',
    status: 'CANCELLED',
    territory_id: 'mock-territory-004',
    territory_name: 'UK Enterprise',
    start_date: '2025-10-01',
    end_date: null,
    accounts_count: 30,
    activities_total: 30,
    activities_completed: 5,
    objective_type: 'PIPELINE_VALUE',
    objective_target: 500000,
    objective_current: 25000,
    members: [
      { id: 'mock-member-007', user_name: 'Charlie Roux', role: 'OWNER', is_primary_owner: true }
    ],
    created_by_name: 'Charlie Roux',
    created_at: '2025-09-15T09:00:00Z',
    updated_at: '2025-11-01T12:00:00Z'
  }
];

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  campaigns: '/campaigns/',
  campaignDetail: (id) => `/campaigns/${id}/`,
  campaignWorkspace: (id) => `/campaigns/${id}/workspace/`,
  campaignStart: (id) => `/campaigns/${id}/start/`,
  campaignPause: (id) => `/campaigns/${id}/pause/`,
  campaignResume: (id) => `/campaigns/${id}/resume/`,
  campaignComplete: (id) => `/campaigns/${id}/complete/`,
  campaignCancel: (id) => `/campaigns/${id}/cancel/`,
  campaignMembers: (id) => `/campaigns/${id}/members/`,
  campaignObjectives: (id) => `/campaigns/${id}/objectives/`,
  campaignDashboard: (id) => `/campaigns/${id}/dashboard/`,
  choices: '/campaigns/choices/',
  bulkDelete: '/campaigns/bulk-delete/'
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

  // Owner scope filter (mine/team/all)
  if (filters.owner_scope) {
    queryParams.append('owner_scope', filters.owner_scope);
  }

  // Campaign-specific filters
  if (filters.status) {
    queryParams.append('status', filters.status);
  }

  if (filters.family) {
    queryParams.append('family', filters.family);
  }

  if (filters.territory_id) {
    queryParams.append('territory_id', filters.territory_id);
  }

  const queryString = queryParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

// ==============================|| MOCK HELPERS ||============================== //

/**
 * Filter and paginate mock data (temporary until backend is connected)
 * @param {Object} options - {page, pageSize, search, filters}
 * @returns {Object} {results, count}
 */
const getMockCampaigns = (options = {}) => {
  const { page = 1, pageSize = 50, search = '', filters = {} } = options;

  let filtered = [...MOCK_CAMPAIGNS];

  // Search filter
  if (search) {
    const term = search.toLowerCase();
    filtered = filtered.filter(
      (c) => c.name.toLowerCase().includes(term) || c.description.toLowerCase().includes(term)
    );
  }

  // Status filter
  if (filters.status) {
    filtered = filtered.filter((c) => c.status === filters.status);
  }

  // Family filter
  if (filters.family) {
    filtered = filtered.filter((c) => c.family === filters.family);
  }

  const count = filtered.length;
  const start = (page - 1) * pageSize;
  const results = filtered.slice(start, start + pageSize);

  return { results, count };
};

// ==============================|| READ HOOKS ||============================== //

/**
 * GET CAMPAIGNS - Paginated list with filters
 * Uses mock data until backend is connected.
 *
 * @param {Object} options - {page, pageSize, search, ordering, filters}
 * @returns {Object} {campaigns, campaignsCount, campaignsLoading, campaignsError, campaignsValidating, campaignsEmpty}
 */
export function useGetCampaigns(options = {}) {
  // TODO: Replace mock with real SWR fetch when backend is ready
  // const { tenantId } = useAuth();
  // const urlWithParams = useMemo(() => buildUrlWithParams(endpoints.campaigns, options), [options]);
  // const swrKey = tenantKey(urlWithParams, tenantId);
  // const { data, isLoading, error, isValidating } = useSWR(swrKey, { ... });

  const { page = 1, pageSize = 50, search = '', filters = {} } = options;

  const memoizedValue = useMemo(() => {
    const { results, count } = getMockCampaigns({ page, pageSize, search, filters });
    return {
      campaigns: results,
      campaignsCount: count,
      campaignsLoading: false,
      campaignsError: null,
      campaignsValidating: false,
      campaignsEmpty: results.length === 0
    };
  }, [page, pageSize, search, filters]);

  return memoizedValue;
}

/**
 * GET CAMPAIGN - Single campaign details
 * Uses mock data until backend is connected.
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Object} {campaign, campaignLoading, campaignError, campaignValidating}
 */
export function useGetCampaign(campaignId) {
  // TODO: Replace mock with real SWR fetch when backend is ready
  // const { tenantId } = useAuth();
  // const swrKey = useMemo(() => {
  //   if (!campaignId || !isValidUUID(campaignId)) return null;
  //   return tenantKey(endpoints.campaignDetail(campaignId), tenantId);
  // }, [campaignId, tenantId]);

  const memoizedValue = useMemo(() => {
    const campaign = MOCK_CAMPAIGNS.find((c) => c.id === campaignId) || null;
    return {
      campaign,
      campaignLoading: false,
      campaignError: campaign ? null : 'Campaign not found',
      campaignValidating: false
    };
  }, [campaignId]);

  return memoizedValue;
}

/**
 * GET CAMPAIGN WORKSPACE - Campaign details + stats for workspace page
 * Uses mock data until backend is connected.
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Object} {campaign, stats, loading, error, validating, mutate}
 */
export function useGetCampaignWorkspace(campaignId) {
  // TODO: Replace mock with real SWR fetch when backend is ready

  const memoizedValue = useMemo(() => {
    const campaign = MOCK_CAMPAIGNS.find((c) => c.id === campaignId) || null;
    return {
      campaign,
      stats: campaign
        ? {
            accounts_count: campaign.accounts_count,
            activities_total: campaign.activities_total,
            activities_completed: campaign.activities_completed,
            completion_rate: campaign.activities_total > 0
              ? Math.round((campaign.activities_completed / campaign.activities_total) * 100)
              : 0
          }
        : { accounts_count: 0, activities_total: 0, activities_completed: 0, completion_rate: 0 },
      loading: false,
      error: campaign ? null : 'Campaign not found',
      validating: false,
      mutate: () => console.log('TODO: mutate campaign workspace')
    };
  }, [campaignId]);

  return memoizedValue;
}

// ==============================|| MUTATION FUNCTIONS ||============================== //

/**
 * CREATE CAMPAIGN
 *
 * @param {Object} payload - Campaign data
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function createCampaign(payload) {
  console.log('TODO: createCampaign', payload);
  // const sanitized = sanitizeObject(payload, ['name', 'description']);
  // const result = await api.post(endpoints.campaigns, sanitized);
  // if (result.success) {
  //   revalidateMultiple([endpoints.campaigns]);
  //   return { success: true, data: result.data };
  // }
  // return { success: false, error: result.error, status: result.status || 0 };
  return { success: true, data: { id: 'mock-new', ...payload } };
}

/**
 * UPDATE CAMPAIGN
 *
 * @param {string} campaignId - UUID of the campaign
 * @param {Object} payload - Campaign data to update
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function updateCampaign(campaignId, payload) {
  console.log('TODO: updateCampaign', campaignId, payload);
  return { success: true, data: { id: campaignId, ...payload } };
}

/**
 * DELETE CAMPAIGN
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Promise<Object>} {success: boolean, error?: string}
 */
export async function deleteCampaign(campaignId) {
  console.log('TODO: deleteCampaign', campaignId);
  return { success: true };
}

/**
 * START CAMPAIGN - Transition from DRAFT to ACTIVE
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function startCampaign(campaignId) {
  console.log('TODO: startCampaign', campaignId);
  return { success: true, data: { id: campaignId, status: 'ACTIVE' } };
}

/**
 * PAUSE CAMPAIGN
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function pauseCampaign(campaignId) {
  console.log('TODO: pauseCampaign', campaignId);
  return { success: true, data: { id: campaignId, status: 'PAUSED' } };
}

/**
 * RESUME CAMPAIGN - Transition from PAUSED to ACTIVE
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function resumeCampaign(campaignId) {
  console.log('TODO: resumeCampaign', campaignId);
  return { success: true, data: { id: campaignId, status: 'ACTIVE' } };
}

/**
 * COMPLETE CAMPAIGN
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function completeCampaign(campaignId) {
  console.log('TODO: completeCampaign', campaignId);
  return { success: true, data: { id: campaignId, status: 'COMPLETED' } };
}

/**
 * CANCEL CAMPAIGN
 *
 * @param {string} campaignId - UUID of the campaign
 * @returns {Promise<Object>} {success: boolean, data?: Object, error?: string}
 */
export async function cancelCampaign(campaignId) {
  console.log('TODO: cancelCampaign', campaignId);
  return { success: true, data: { id: campaignId, status: 'CANCELLED' } };
}

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Get progress percentage for a campaign
 * @param {Object} campaign - Campaign object
 * @returns {number} Progress 0-100
 */
export const getCampaignProgress = (campaign) => {
  if (!campaign || !campaign.activities_total) return 0;
  return Math.round((campaign.activities_completed / campaign.activities_total) * 100);
};

/**
 * Get objective progress percentage for a campaign
 * @param {Object} campaign - Campaign object
 * @returns {number} Progress 0-100
 */
export const getObjectiveProgress = (campaign) => {
  if (!campaign || !campaign.objective_target) return 0;
  return Math.min(100, Math.round((campaign.objective_current / campaign.objective_target) * 100));
};