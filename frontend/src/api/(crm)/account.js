import useSWR, { mutate } from 'swr';
import { useMemo } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000/app/accounts';

const initialState = {
  modal: false
};

export const endpoints = {
  key: 'app/accounts',
  list: '/accounts/',
  detail: '/accounts/:id',
  create: '/accounts/',
  update: '/accounts/:id',
  delete: '/accounts/:id'
};

export function useGetAccounts(filters = {}) {
  const params = new URLSearchParams(filters);
  const { data, isLoading, error, isValidating } = useSWR(
    `${API_URL}${endpoints.list}/?${params}`,
    async (url) => {
      const response = await axios.get(url);
      console.log('XXX@ :' + response)
      return response.data;
    },
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      accounts: data?.accounts,
      accountsLoading: isLoading,
      accountsError: error,
      accountsValidating: isValidating,
      accountsEmpty: !isLoading && !data?.accounts?.length
    }),
    [data, error, isLoading, isValidating]
  );

  return memoizedValue;
}

export function useGetAccount(id) {
  const { data, isLoading, error } = useSWR(
    id ? `${API_URL}${endpoints.detail.replace(':id', id)}` : null,
    async (url) => {
      const response = await axios.get(url);
      return response.data;
    },
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const memoizedValue = useMemo(
    () => ({
      account: data,
      accountLoading: isLoading,
      accountError: error
    }),
    [data, error, isLoading]
  );

  return memoizedValue;
}

export async function createAccount(newAccount) {
  // Update local state optimistically
  mutate(
    `${API_URL}${endpoints.list}`,
    async (currentData) => {
      const optimisticAccount = { ...newAccount, id: Date.now() }; // Temporary ID
      return {
        ...currentData,
        accounts: [...(currentData?.accounts || []), optimisticAccount]
      };
    },
    false
  );

  // Make API call
  try {
    const response = await axios.post(`${API_URL}${endpoints.create}`, newAccount);
    // Revalidate the accounts list after successful creation
    mutate(`${API_URL}${endpoints.list}`);
    return response.data;
  } catch (error) {
    // Revalidate in case of error to restore correct state
    mutate(`${API_URL}${endpoints.list}`);
    throw error;
  }
}

export async function updateAccount(id, updatedAccount) {
  // Update local state optimistically
  mutate(
    `${API_URL}${endpoints.list}`,
    (currentData) => {
      const updatedAccounts = currentData.accounts.map((account) =>
        account.id === id ? { ...account, ...updatedAccount } : account
      );
      return { ...currentData, accounts: updatedAccounts };
    },
    false
  );

  // Make API call
  try {
    const response = await axios.put(`${API_URL}${endpoints.update.replace(':id', id)}`, updatedAccount);
    // Revalidate both the list and the individual account
    mutate(`${API_URL}${endpoints.list}`);
    mutate(`${API_URL}${endpoints.detail.replace(':id', id)}`);
    return response.data;
  } catch (error) {
    // Revalidate in case of error
    mutate(`${API_URL}${endpoints.list}`);
    mutate(`${API_URL}${endpoints.detail.replace(':id', id)}`);
    throw error;
  }
}

export async function deleteAccount(id) {
  // Update local state optimistically
  mutate(
    `${API_URL}${endpoints.list}`,
    (currentData) => {
      const filteredAccounts = currentData.accounts.filter((account) => account.id !== id);
      return { ...currentData, accounts: filteredAccounts };
    },
    false
  );

  // Make API call
  try {
    const response = await axios.delete(`${API_URL}${endpoints.delete.replace(':id', id)}`);
    // Revalidate the accounts list after successful deletion
    mutate(`${API_URL}${endpoints.list}`);
    return response.data;
  } catch (error) {
    // Revalidate in case of error
    mutate(`${API_URL}${endpoints.list}`);
    throw error;
  }
}

// Modal state management
export function useAccountModal() {
  const { data, isLoading } = useSWR(endpoints.key + '/modal', () => initialState, {
    revalidateIfStale: false,
    revalidateOnFocus: false,
    revalidateOnReconnect: false
  });

  const memoizedValue = useMemo(
    () => ({
      modalState: data,
      modalLoading: isLoading
    }),
    [data, isLoading]
  );

  return memoizedValue;
}

export function handleAccountModal(modal) {
  mutate(
    endpoints.key + '/modal',
    (currentState) => ({ ...currentState, modal }),
    false
  );
}