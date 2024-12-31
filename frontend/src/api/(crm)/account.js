import useSWR, { mutate } from 'swr';
import { useMemo } from 'react';
import axios from 'axios';
import { BE_API_URL } from '../config';

const API_URL = BE_API_URL;

const initialState = {
  modal: false
};

export const endpoints = {
  list: '/accounts/',
  detail: '/accounts/:id/',
  create: '/accounts/',
  update: '/accounts/:id/',
  delete: '/accounts/:id/',
  accountType: '/accounts/account-types/'
};

export async function  useGetAccounts(filters = {}) {
     const params = new URLSearchParams(filters);
     const response = await axios.get(`${API_URL}/accounts/?${params}`);
     console.log('Fetched Accounts:', response.data);
     return response.data;
}

export async function createAccount(newAccount) {
  const response = await axios.post(`${API_URL}/accounts/`, newAccount);
  if (response.status === 201) {
    return response.data;
  } else {
    return response.error
  }
}

export async function deleteAccount(id) {
  const response = await axios.delete(`${API_URL}/accounts/${id}/`);
  if (response.status === 202) {
    return response.message;
  } else {
    return response.error
  }
}

export async function updateAccount(id, updatedAccount) {
  const response = await axios.put(`${API_URL}/accounts/${id}/`, updatedAccount);
  if (response.status === 200) {
    return response.data;
  } else {
    return response.error
  }
}

export async function getAccountTypes() {
  const response = await axios.get(`${API_URL}${endpoints.accountType}`);
  return response.data;
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