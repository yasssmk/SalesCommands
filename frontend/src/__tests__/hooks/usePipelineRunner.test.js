// frontend/src/__tests__/hooks/usePipelineRunner.test.js

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, cleanup } from '@testing-library/react';

// ==============================|| MOCKS ||============================== //

const mockRunExtraction = vi.fn();
vi.mock('api/aiPipelines/activityExtraction', () => ({
  runActivityExtraction: (...args) => mockRunExtraction(...args),
  EXTRACTION_STATUS: {
    SUCCESS: 'SUCCESS',
    PARTIAL: 'PARTIAL',
    FAILED: 'FAILED',
  },
  EXTRACTION_OUTCOME_CODES: {
    ALREADY_EXTRACTED: 'ALREADY_EXTRACTED',
    IDEMPOTENCY_CONFLICT: 'IDEMPOTENCY_CONFLICT',
    TIMEOUT_PENDING: 'TIMEOUT_PENDING',
    POLL_FAILED: 'POLL_FAILED',
  },
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import usePipelineRunner, { PIPELINE_STATE } from 'hooks/usePipelineRunner';

// ==============================|| TESTS ||============================== //

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe('usePipelineRunner', () => {
  it('starts in idle state', () => {
    const { result } = renderHook(() => usePipelineRunner());

    expect(result.current.state).toBe(PIPELINE_STATE.IDLE);
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('transitions to running then success on successful extraction', async () => {
    const onSuccess = vi.fn();
    const data = {
      status: 'SUCCESS',
      qualification_run: { created_signals_count: 5 },
      next_steps_run: { created_signals_count: 3 },
    };
    mockRunExtraction.mockResolvedValue({ success: true, data });

    const { result } = renderHook(() => usePipelineRunner({ onSuccess }));

    await act(async () => {
      result.current.run('act-1', 'some transcript text');
    });

    expect(result.current.state).toBe(PIPELINE_STATE.SUCCESS);
    expect(result.current.result).toEqual(data);
    expect(result.current.error).toBeNull();
    expect(onSuccess).toHaveBeenCalledWith(data);
    expect(mockRunExtraction).toHaveBeenCalledWith('act-1', 'some transcript text', null, null);
  });

  it('forwards pipeline flags to extraction function', async () => {
    mockRunExtraction.mockResolvedValue({
      success: true,
      data: { status: 'SUCCESS' },
    });

    const { result } = renderHook(() => usePipelineRunner());

    await act(async () => {
      result.current.run('act-1', 'transcript', { run_qualification: true, run_next_steps: false });
    });

    expect(mockRunExtraction).toHaveBeenCalledWith(
      'act-1', 'transcript', null,
      { run_qualification: true, run_next_steps: false },
    );
  });

  it('transitions to partial on PARTIAL status', async () => {
    const data = {
      status: 'PARTIAL',
      qualification_run: { created_signals_count: 3 },
      next_steps_run: { created_signals_count: 0 },
    };
    mockRunExtraction.mockResolvedValue({ success: true, data });

    const { result } = renderHook(() => usePipelineRunner());

    await act(async () => {
      result.current.run('act-1', 'transcript');
    });

    expect(result.current.state).toBe(PIPELINE_STATE.PARTIAL);
    expect(result.current.result).toEqual(data);
  });

  it('transitions to error on failed extraction', async () => {
    const onError = vi.fn();
    mockRunExtraction.mockResolvedValue({
      success: false,
      error: 'LLM provider error',
    });

    const { result } = renderHook(() => usePipelineRunner({ onError }));

    await act(async () => {
      result.current.run('act-1', 'transcript');
    });

    expect(result.current.state).toBe(PIPELINE_STATE.ERROR);
    expect(result.current.error).toBe('LLM provider error');
    expect(onError).toHaveBeenCalled();
  });

  it('transitions to error on TIMEOUT_PENDING', async () => {
    mockRunExtraction.mockResolvedValue({
      success: false,
      code: 'TIMEOUT_PENDING',
      isPending: true,
    });

    const { result } = renderHook(() => usePipelineRunner());

    await act(async () => {
      result.current.run('act-1', 'transcript');
    });

    expect(result.current.state).toBe(PIPELINE_STATE.ERROR);
    expect(result.current.error).toContain('taking longer than expected');
  });

  it('handles ALREADY_EXTRACTED as success', async () => {
    const onSuccess = vi.fn();
    const data = {
      qualification_run: { created_signals_count: 2 },
      next_steps_run: { created_signals_count: 1 },
    };
    mockRunExtraction.mockResolvedValue({
      success: false,
      code: 'ALREADY_EXTRACTED',
      data,
    });

    const { result } = renderHook(() => usePipelineRunner({ onSuccess }));

    await act(async () => {
      result.current.run('act-1', 'transcript');
    });

    expect(result.current.state).toBe(PIPELINE_STATE.SUCCESS);
    expect(result.current.result).toEqual(data);
    expect(onSuccess).toHaveBeenCalledWith(data);
  });

  it('handles thrown exception', async () => {
    mockRunExtraction.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => usePipelineRunner());

    await act(async () => {
      result.current.run('act-1', 'transcript');
    });

    expect(result.current.state).toBe(PIPELINE_STATE.ERROR);
    expect(result.current.error).toBe('Network error');
  });

  it('reset() returns to idle', async () => {
    mockRunExtraction.mockResolvedValue({
      success: true,
      data: { status: 'SUCCESS' },
    });

    const { result } = renderHook(() => usePipelineRunner());

    await act(async () => {
      result.current.run('act-1', 'transcript');
    });

    expect(result.current.state).toBe(PIPELINE_STATE.SUCCESS);

    act(() => {
      result.current.reset();
    });

    expect(result.current.state).toBe(PIPELINE_STATE.IDLE);
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('does nothing when activityId is falsy', async () => {
    const { result } = renderHook(() => usePipelineRunner());

    await act(async () => {
      result.current.run(null, 'transcript');
    });

    expect(result.current.state).toBe(PIPELINE_STATE.IDLE);
    expect(mockRunExtraction).not.toHaveBeenCalled();
  });
});
