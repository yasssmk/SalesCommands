// frontend/src/api/admin/users.js

import useSWR, { mutate } from 'swr';
import { useMemo } from 'react';

// utils
import axiosClient, { api } from 'utils/axiosClient';

// ==============================|| ENDPOINTS ||============================== //

const endpoints = {
  users: '/client/users/',
  organizations: '/client/organizations/',
  teams: '/client/teams/',
  roles: '/client/roles/',
  clientAccountStats: (clientId) => `/client/client-accounts/${clientId}/stats/`
};

// ==============================|| SWR FETCHER ||============================== //

const fetcher = async (url) => {
  const result = await api.get(url);
  if (result.success) {
    return result.data;
  }
  throw new Error(result.error || 'Failed to fetch data');
};

// 🔁 Revalidate ALL user lists (any key that starts with /client/users/)
export const revalidateUsersLists = () =>
  mutate((key) => typeof key === 'string' && key.startsWith(endpoints.users));

// 🔁 Revalidate seats for a specific client (when you know the id)
export const refreshClientSeats = (clientId) => {
  if (!clientId) return;
  return mutate(endpoints.clientAccountStats(clientId));
};

// 🔁 Revalidate ANY seats stats key (pattern-based, works even if clientId is unknown here)
const revalidateAnyClientSeats = () =>
  mutate(
    (key) =>
      typeof key === 'string' &&
      key.includes('/client/client-accounts/') &&
      key.endsWith('/stats/')
  );

// ==============================|| HOOKS ||============================== //

/**
 * ✅ GET USERS LIST
 * Uses Django pagination format with results array
 */
export function useGetUsers() {
  const listUrl = endpoints.users;
  const { data, isLoading, error, isValidating } = useSWR(
    listUrl,
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      users: data?.results || [],
      usersCount: data?.count || 0,
      usersLoading: isLoading,
      usersError: error,
      usersValidating: isValidating,
      usersEmpty: !isLoading && (!data?.results?.length)
    }),
    [data, error, isLoading, isValidating]
  );

  return memoizedValue;
}

/**
 * ✅ GET SINGLE USER
 */
export function useGetUser(userId) {
  const { data, isLoading, error, isValidating } = useSWR(
    userId ? `${endpoints.users}${userId}/` : null,
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      user: data,
      userLoading: isLoading,
      userError: error,
      userValidating: isValidating
    }),
    [data, error, isLoading, isValidating]
  );

  return memoizedValue;
}

/**
 * ✅ GET ORGANIZATIONS
 */
export function useGetOrganizations() {
  const { data, isLoading, error } = useSWR(
    endpoints.organizations,
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      organizations: data?.results || [],
      organizationsLoading: isLoading,
      organizationsError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

/**
 * ✅ GET TEAMS (with filters + enabled)
 * @param {Object} filters - ex: { organization: 'uuid' }
 * @param {boolean} enabled - if false, skip fetch
 */
export function useGetTeams(filters = {}, enabled = true) {
  const qs = new URLSearchParams(filters || {}).toString();
  const key = enabled ? `${endpoints.teams}${qs ? `?${qs}` : ''}` : null;

  const { data, isLoading, error } = useSWR(
    key,
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      teams: data?.results || [],
      teamsLoading: isLoading,
      teamsError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

/**
 * ✅ GET USER ROLES
 */
export function useGetUserRoles() {
  const { data, isLoading, error } = useSWR(
    endpoints.roles,
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      roles: data?.results || [],
      rolesLoading: isLoading,
      rolesError: error
    }),
    [data, isLoading, error]
  );

  return memoizedValue;
}

/**
 * ✅ GET CLIENT SEATS STATS
 * seats = client.max_users
 * seats_used = # active users
 * seats_left = seats - seats_used
 */
export function useGetClientSeats(clientId) {
  const key = clientId ? endpoints.clientAccountStats(clientId) : null;

  const { data, isLoading, error, isValidating } = useSWR(
    key,
    fetcher,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  // our api wrapper returns the inner "data", so seats should be directly under data.seats
  const root = data?.seats ? data : data?.data ? data.data : {};
  const s = root?.seats || {};

  const seats = Number(s.seats ?? 0);
  const seatsUsed = Number(s.seats_used ?? 0);
  const seatsLeft = Number(s.seats_left ?? Math.max(0, seats - seatsUsed));

  return {
    seats,
    seatsUsed,
    seatsLeft,
    seatsLoading: isLoading,
    seatsError: error,
    seatsValidating: isValidating,
    raw: data
  };
}

// ==============================|| CRUD FUNCTIONS ||============================== //

/**
 * ✅ CREATE USER
 */
export const insertUser = async (userData) => {
  const result = await api.post(endpoints.users, userData);

  if (result.success) {
    // Optimistic update for users list
    mutate(
      endpoints.users,
      (currentData) => {
        if (!currentData) return { results: [result.data], count: 1 };
        return {
          ...currentData,
          results: [...(currentData.results || []), result.data],
          count: (currentData.count || 0) + 1
        };
      },
      false
    );

    // Revalidate users + seats
    mutate(endpoints.users);
    revalidateAnyClientSeats();

    return { success: true, user: result.data };
  } else {
    return { success: false, error: result.error };
  }
};

/**
 * ✅ UPDATE USER (PATCH)
 */
export const updateUser = async (userId, userData) => {
  const result = await api.patch(`${endpoints.users}${userId}/`, userData);

  if (result.success) {
    // Optimistic update for users list
    mutate(
      endpoints.users,
      (currentData) => {
        if (!currentData) return currentData;
        const updatedResults = (currentData.results || []).map((u) =>
          u.id === userId ? result.data : u
        );
        return { ...currentData, results: updatedResults };
      },
      false
    );

    // Update single user cache if present
    mutate(`${endpoints.users}${userId}/`, result.data, false);

    // Revalidate users + seats
    mutate(endpoints.users);
    revalidateAnyClientSeats();

    return { success: true, user: result.data };
  } else {
    return { success: false, error: result.error };
  }
};

/**
 * ✅ DELETE USER
 */
export const deleteUser = async (userId) => {
  const result = await api.delete(`${endpoints.users}${userId}/`);

  if (result.success) {
    // Optimistic update for users list
    mutate(
      endpoints.users,
      (currentData) => {
        if (!currentData) return currentData;
        const filteredResults = (currentData.results || []).filter((u) => u.id !== userId);
        return {
          ...currentData,
          results: filteredResults,
          count: Math.max(0, (currentData.count || 1) - 1)
        };
      },
      false
    );

    // Drop single user cache
    mutate(`${endpoints.users}${userId}/`, undefined, false);

    // Revalidate users + seats
    mutate(endpoints.users);
    revalidateAnyClientSeats();

    return { success: true, status: result.status ?? 204 };
  } else {
    return { success: false, error: result.error, status: result.status };
  }
};

// ==============================|| ADDITIONAL OPERATIONS ||============================== //

/**
 * ✅ REFRESH USERS LIST
 */
export const refreshUsers = () => mutate(endpoints.users);

/**
 * ✅ FILTER USERS
 */
export const filterUsers = (filters) => {
  const queryParams = new URLSearchParams(filters).toString();
  const url = `${endpoints.users}?${queryParams}`;
  return mutate(url);
};
