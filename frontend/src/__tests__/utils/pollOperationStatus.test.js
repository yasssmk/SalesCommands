// frontend/src/__tests__/utils/pollOperationStatus.test.js

import { describe, it, expect, vi, beforeEach } from 'vitest';

// ==============================|| MOCKS ||============================== //

const mockGet = vi.fn();

vi.mock('utils/axiosClient', () => ({
  api: {
    get: (...args) => mockGet(...args),
  },
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import { pollOperationStatus } from 'utils/pollOperationStatus';

// ==============================|| TESTS ||============================== //

beforeEach(() => {
  vi.clearAllMocks();
});

describe('pollOperationStatus', () => {
  it('returns not_found immediately on 404 without retrying', async () => {
    mockGet.mockResolvedValue({
      success: false,
      status: 404,
      error: "No operation found with key 'abc123'. It may have expired or never existed.",
    });

    const result = await pollOperationStatus('abc123', {
      maxAttempts: 6,
      baseDelay: 0,
    });

    expect(result.status).toBe('not_found');
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it('returns not_found error message from backend', async () => {
    mockGet.mockResolvedValue({
      success: false,
      status: 404,
      error: "No operation found with key 'xyz'. It may have expired or never existed.",
    });

    const result = await pollOperationStatus('xyz', {
      maxAttempts: 3,
      baseDelay: 0,
    });

    expect(result.status).toBe('not_found');
    expect(result.error).toContain('No operation found');
  });

  it('retries on non-404 failures, does not retry on 404', async () => {
    mockGet
      .mockResolvedValueOnce({ success: false, status: 500, error: 'Server error' })
      .mockResolvedValueOnce({ success: false, status: 404, error: 'Not found' });

    const result = await pollOperationStatus('key123', {
      maxAttempts: 6,
      baseDelay: 0,
    });

    expect(mockGet).toHaveBeenCalledTimes(2);
    expect(result.status).toBe('not_found');
  });

  it('returns succeeded when operation completes', async () => {
    mockGet.mockResolvedValue({
      success: true,
      data: {
        status: 'succeeded',
        result: { http_status: 200, data: { success: true } },
      },
    });

    const result = await pollOperationStatus('key456', {
      maxAttempts: 3,
      baseDelay: 0,
    });

    expect(result.status).toBe('succeeded');
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it('returns still_running when max attempts exhausted', async () => {
    mockGet.mockResolvedValue({
      success: true,
      data: { status: 'running' },
    });

    const result = await pollOperationStatus('key789', {
      maxAttempts: 2,
      baseDelay: 0,
    });

    expect(result.status).toBe('still_running');
    expect(mockGet).toHaveBeenCalledTimes(2);
  });
});
