// frontend/src/__tests__/api/aiPipelines/activityExtraction.test.js

import { describe, it, expect, vi, beforeEach } from 'vitest';

// ==============================|| MOCKS ||============================== //

vi.mock('utils/axiosClient', () => ({
  api: {
    post: vi.fn(),
  },
}));

vi.mock('api/_swr', () => ({
  revalidateMultiple: vi.fn(),
}));

vi.mock('utils/pollOperationStatus', () => ({
  pollOperationStatus: vi.fn(),
}));

vi.mock('utils/validators', () => ({
  isValidUUID: vi.fn((v) => /^[0-9a-f-]{36}$/.test(v)),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import { api } from 'utils/axiosClient';
import { revalidateMultiple } from 'api/_swr';
import { pollOperationStatus } from 'utils/pollOperationStatus';
import {
  runActivityExtraction,
  EXTRACTION_OUTCOME_CODES,
} from 'api/aiPipelines/activityExtraction';

// ==============================|| TEST DATA ||============================== //

const ACTIVITY_ID = '11111111-1111-1111-1111-111111111111';
const TRANSCRIPT = 'A'.repeat(100);

const MOCK_SUCCESS_RESPONSE = {
  success: true,
  data: {
    data: {
      status: 'SUCCESS',
      qualification_run: {
        run_id: 'run-1',
        status: 'SUCCESS',
        created_signals_count: 5,
      },
      next_steps_run: {
        run_id: 'run-2',
        status: 'SUCCESS',
        created_signals_count: 3,
      },
      qualification_signals: {
        pain: [{ id: 's1' }],
        objective: [],
        impact: [],
        'tech-stack': [],
        blocker: [],
      },
      next_step_signals: [{ id: 'ns1' }],
    },
  },
};

// ==============================|| TESTS ||============================== //

beforeEach(() => {
  vi.clearAllMocks();
});

describe('runActivityExtraction', () => {
  // ------------------------------------------------------------------
  // 1. Client-side validation — invalid activity ID
  // ------------------------------------------------------------------
  it('returns 400 error for invalid activity ID', async () => {
    const result = await runActivityExtraction('not-a-uuid', TRANSCRIPT);
    expect(result.success).toBe(false);
    expect(result.status).toBe(400);
    expect(api.post).not.toHaveBeenCalled();
  });

  // ------------------------------------------------------------------
  // 2. Client-side validation — empty transcript
  // ------------------------------------------------------------------
  it('returns 400 error for empty transcript', async () => {
    const result = await runActivityExtraction(ACTIVITY_ID, '   ');
    expect(result.success).toBe(false);
    expect(result.status).toBe(400);
    expect(api.post).not.toHaveBeenCalled();
  });

  // ------------------------------------------------------------------
  // 3. Sync success (HTTP 200)
  // ------------------------------------------------------------------
  it('returns success on sync HTTP 200', async () => {
    api.post.mockResolvedValue(MOCK_SUCCESS_RESPONSE);

    const result = await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(api.post).toHaveBeenCalledWith(
      '/module-ai-pipelines/activity-extraction/run/',
      { activity_id: ACTIVITY_ID, transcript: TRANSCRIPT },
      expect.objectContaining({ profile: 'bulk' }),
    );
    expect(revalidateMultiple).toHaveBeenCalled();
  });

  // ------------------------------------------------------------------
  // 4. Deterministic idempotency key in request headers
  // ------------------------------------------------------------------
  it('sends deterministic Idempotency-Key header', async () => {
    api.post.mockResolvedValue(MOCK_SUCCESS_RESPONSE);

    await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    const config = api.post.mock.calls[0][2];
    expect(config.headers).toBeDefined();
    expect(config.headers['Idempotency-Key']).toMatch(/^[0-9a-f]{64}$/);
  });

  // ------------------------------------------------------------------
  // 5. Same inputs produce same idempotency key
  // ------------------------------------------------------------------
  it('produces identical keys for identical inputs', async () => {
    api.post.mockResolvedValue(MOCK_SUCCESS_RESPONSE);

    await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);
    await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    const key1 = api.post.mock.calls[0][2].headers['Idempotency-Key'];
    const key2 = api.post.mock.calls[1][2].headers['Idempotency-Key'];
    expect(key1).toBe(key2);
  });

  // ------------------------------------------------------------------
  // 6. Different transcript produces different idempotency key
  // ------------------------------------------------------------------
  it('produces different keys for different transcripts', async () => {
    api.post.mockResolvedValue(MOCK_SUCCESS_RESPONSE);

    await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);
    await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT + ' extra');

    const key1 = api.post.mock.calls[0][2].headers['Idempotency-Key'];
    const key2 = api.post.mock.calls[1][2].headers['Idempotency-Key'];
    expect(key1).not.toBe(key2);
  });

  // ------------------------------------------------------------------
  // 7. HTTP 202 — polls then returns success
  // ------------------------------------------------------------------
  it('polls on 202 and maps succeeded result', async () => {
    api.post.mockResolvedValue({
      success: true,
      data: {
        __is202: true,
        __idempotency_key: 'fallback-key',
      },
    });

    pollOperationStatus.mockResolvedValue({
      status: 'succeeded',
      result: {
        http_status: 200,
        data: {
          success: true,
          data: MOCK_SUCCESS_RESPONSE.data.data,
        },
      },
    });

    const result = await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(result.success).toBe(true);
    expect(pollOperationStatus).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        maxAttempts: 12,
        baseDelay: 2000,
        maxDelay: 15000,
      }),
    );
  });

  // ------------------------------------------------------------------
  // 8. Client timeout — polls then returns
  // ------------------------------------------------------------------
  it('polls on client timeout and maps result', async () => {
    api.post.mockResolvedValue({
      success: false,
      isTimeout: true,
      idempotencyKey: 'timeout-key',
    });

    pollOperationStatus.mockResolvedValue({
      status: 'succeeded',
      result: {
        http_status: 200,
        data: {
          success: true,
          data: MOCK_SUCCESS_RESPONSE.data.data,
        },
      },
    });

    const result = await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);
    expect(result.success).toBe(true);
    expect(pollOperationStatus).toHaveBeenCalled();
  });

  // ------------------------------------------------------------------
  // 9. HTTP 409 — ALREADY_EXTRACTED
  // ------------------------------------------------------------------
  it('returns ALREADY_EXTRACTED on 409 with that code', async () => {
    api.post.mockResolvedValue({
      success: false,
      status: 409,
      data: {
        code: 'ALREADY_EXTRACTED',
        error: 'Already processed',
        data: { qualification_run: {} },
      },
    });

    const result = await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(result.success).toBe(false);
    expect(result.code).toBe(EXTRACTION_OUTCOME_CODES.ALREADY_EXTRACTED);
    expect(result.data).toBeDefined();
    expect(result.status).toBe(409);
  });

  // ------------------------------------------------------------------
  // 10. HTTP 409 — IDEMPOTENCY_CONFLICT
  // ------------------------------------------------------------------
  it('returns IDEMPOTENCY_CONFLICT on 409 without code', async () => {
    api.post.mockResolvedValue({
      success: false,
      status: 409,
      data: {},
    });

    const result = await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(result.success).toBe(false);
    expect(result.code).toBe(EXTRACTION_OUTCOME_CODES.IDEMPOTENCY_CONFLICT);
  });

  // ------------------------------------------------------------------
  // 11. Polling still_running — TIMEOUT_PENDING
  // ------------------------------------------------------------------
  it('returns TIMEOUT_PENDING when polling exhausts retries', async () => {
    api.post.mockResolvedValue({
      success: true,
      data: { __is202: true, __idempotency_key: 'key' },
    });

    pollOperationStatus.mockResolvedValue({
      status: 'still_running',
      message: 'Still processing',
    });

    const result = await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(result.success).toBe(false);
    expect(result.code).toBe(EXTRACTION_OUTCOME_CODES.TIMEOUT_PENDING);
    expect(result.isPending).toBe(true);
  });

  // ------------------------------------------------------------------
  // 12. Polling failed
  // ------------------------------------------------------------------
  it('returns POLL_FAILED when polling returns null', async () => {
    api.post.mockResolvedValue({
      success: true,
      data: { __is202: true, __idempotency_key: 'key' },
    });

    pollOperationStatus.mockResolvedValue(null);

    const result = await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(result.success).toBe(false);
    expect(result.code).toBe(EXTRACTION_OUTCOME_CODES.POLL_FAILED);
  });

  // ------------------------------------------------------------------
  // 13. Generic error (400/500)
  // ------------------------------------------------------------------
  it('returns generic error for non-409 failures', async () => {
    api.post.mockResolvedValue({
      success: false,
      error: 'Server error',
      status: 500,
    });

    const result = await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(result.success).toBe(false);
    expect(result.error).toBe('Server error');
    expect(result.status).toBe(500);
  });

  // ------------------------------------------------------------------
  // 14. Progress callback passed to polling
  // ------------------------------------------------------------------
  it('passes onProgress to pollOperationStatus', async () => {
    api.post.mockResolvedValue({
      success: true,
      data: { __is202: true, __idempotency_key: 'key' },
    });

    pollOperationStatus.mockResolvedValue({
      status: 'succeeded',
      result: {
        http_status: 200,
        data: { success: true, data: {} },
      },
    });

    const onProgress = vi.fn();
    await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT, onProgress);

    expect(pollOperationStatus).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ onProgress }),
    );
  });

  // ------------------------------------------------------------------
  // 15. Trims whitespace from transcript before sending
  // ------------------------------------------------------------------
  it('trims transcript whitespace before POST', async () => {
    api.post.mockResolvedValue(MOCK_SUCCESS_RESPONSE);

    await runActivityExtraction(ACTIVITY_ID, `  ${TRANSCRIPT}  `);

    const sentPayload = api.post.mock.calls[0][1];
    expect(sentPayload.transcript).toBe(TRANSCRIPT);
  });

  // ------------------------------------------------------------------
  // F8-3: Network retry — success on first try (no retry)
  // ------------------------------------------------------------------
  it('does not retry when first POST succeeds', async () => {
    api.post.mockResolvedValue(MOCK_SUCCESS_RESPONSE);

    await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(api.post).toHaveBeenCalledTimes(1);
  });

  // ------------------------------------------------------------------
  // F8-3: Network retry — retries on network error then succeeds
  // ------------------------------------------------------------------
  it('retries on network error and succeeds on second attempt', async () => {
    api.post
      .mockResolvedValueOnce({ success: false })
      .mockResolvedValueOnce(MOCK_SUCCESS_RESPONSE);

    const result = await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(api.post).toHaveBeenCalledTimes(2);
    expect(result.success).toBe(true);
  });

  // ------------------------------------------------------------------
  // F8-3: Network retry — retries on 503 then succeeds
  // ------------------------------------------------------------------
  it('retries on 503 and succeeds on retry', async () => {
    api.post
      .mockResolvedValueOnce({ success: false, status: 503, error: 'Service Unavailable' })
      .mockResolvedValueOnce(MOCK_SUCCESS_RESPONSE);

    const result = await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(api.post).toHaveBeenCalledTimes(2);
    expect(result.success).toBe(true);
  });

  // ------------------------------------------------------------------
  // F8-3: Network retry — does NOT retry on 400/409/500
  // ------------------------------------------------------------------
  it('does not retry on 400 client error', async () => {
    api.post.mockResolvedValue({
      success: false,
      status: 400,
      error: 'Validation error',
    });

    const result = await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(api.post).toHaveBeenCalledTimes(1);
    expect(result.success).toBe(false);
    expect(result.status).toBe(400);
  });

  it('does not retry on 409 conflict', async () => {
    api.post.mockResolvedValue({
      success: false,
      status: 409,
      data: { code: 'ALREADY_EXTRACTED' },
    });

    await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(api.post).toHaveBeenCalledTimes(1);
  });

  it('does not retry on 500 server error', async () => {
    api.post.mockResolvedValue({
      success: false,
      status: 500,
      error: 'Internal Server Error',
    });

    await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(api.post).toHaveBeenCalledTimes(1);
  });

  // ------------------------------------------------------------------
  // F8-3: Network retry — exhausts retries and returns last result
  // ------------------------------------------------------------------
  it('exhausts all retries on persistent network error', async () => {
    api.post.mockResolvedValue({ success: false });

    const result = await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(api.post).toHaveBeenCalledTimes(3);
    expect(result.success).toBe(false);
  });

  // ------------------------------------------------------------------
  // F8-3: Network retry — does NOT retry on timeout (handled by polling)
  // ------------------------------------------------------------------
  it('does not retry on client timeout (isTimeout)', async () => {
    api.post.mockResolvedValue({
      success: false,
      isTimeout: true,
      idempotencyKey: 'key',
    });

    pollOperationStatus.mockResolvedValue({
      status: 'succeeded',
      result: { http_status: 200, data: { success: true, data: {} } },
    });

    await runActivityExtraction(ACTIVITY_ID, TRANSCRIPT);

    expect(api.post).toHaveBeenCalledTimes(1);
  });
});
