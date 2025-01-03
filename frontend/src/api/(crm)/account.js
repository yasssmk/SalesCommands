import useSWR, { mutate } from 'swr';
import { useMemo } from 'react';
import axios from 'axios';
import { sanitizeInput, sanitizeApiCall } from 'utils/InputSanitizer';


const API_URL = process.env.NEXT_BE_API_URL;

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

export const useGetAccounts = sanitizeApiCall(async (filters = {}) => {
  const sanitizedFilters = sanitizeInput(filters);
  const params = new URLSearchParams(sanitizedFilters);
  try {
    const response = await axios.get(`${API_URL}/accounts/?${params}`);
    return response.data;

  } catch (error) {
    throw error;
  }
});


export const createAccount = sanitizeApiCall(async (newAccount) => {
  const response = await axios.post(`${API_URL}/accounts/`, newAccount);
  return response.status === 201 ? response.data : response.error;
});

export const deleteAccount = sanitizeApiCall(async (id) => {
  const sanitizedId = sanitizeInput(id);
  const response = await axios.delete(`${API_URL}/accounts/${sanitizedId}/`);
  return response.status === 202 ? response.message : response.error;
});

export const updateAccount = sanitizeApiCall(async (id, updatedAccount) => {
  const sanitizedId = sanitizeInput(id);
  const response = await axios.put(`${API_URL}/accounts/${sanitizedId}/`, updatedAccount);
  return response.status === 200 ? response.data : response.error;
});

export const getAccountTypes = sanitizeApiCall(async () => {
  const response = await axios.get(`${API_URL}${endpoints.accountType}`);
  return response.data;
});

export function useAccountModal() {
  const { data, isLoading } = useSWR(endpoints.key + '/modal', () => initialState, {
    revalidateIfStale: false,
    revalidateOnFocus: false,
    revalidateOnReconnect: false
  });

  return useMemo(
    () => ({
      modalState: data,
      modalLoading: isLoading
    }),
    [data, isLoading]
  );
}

export function handleAccountModal(modal) {
  mutate(
    endpoints.key + '/modal',
    (currentState) => ({ ...currentState, modal }),
    false
  );
}