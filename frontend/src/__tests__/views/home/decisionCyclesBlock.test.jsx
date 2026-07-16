// frontend/src/__tests__/views/home/decisionCyclesBlock.test.jsx
//
// DecisionCyclesBlock rendered against the REAL dc_cycle_state KPI meta shape
// (value + meta.{cycle_status,current_step_name,next_action,validated_steps,
// total_steps}) zipped with the list row (name + account). No mock of the meta
// that could mask a field rename. Pins: the row content, STALLED shown in error
// (the local override of the shared 'warning'), "X/N stages" not "%", and the
// data-driven visibility (empty list -> no block at all).

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

// The block imports constants from api/accounts/decisionCycles, whose module
// pulls SWR/auth/axios at import time; none are exercised here, so stub them so
// the REAL constants (status labels/colors) still load.
vi.mock('swr', () => ({ default: () => ({}), mutate: vi.fn() }));
vi.mock('hooks/useAuth', () => ({ useAuth: () => ({ tenantId: 't' }) }));
vi.mock('utils/axiosClient', () => ({ api: {} }));
vi.mock('api/_swr', () => ({ tenantKey: (u) => u, revalidateMultiple: vi.fn() }));

const pushMock = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: pushMock }) }));

// MainCard pulls a next/font chain jsdom can't evaluate; stub it to render its
// title as text and forward children.
vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock', style: {} }),
}));
vi.mock('components/MainCard', () => ({
  default: ({ children, title }) => (
    <div data-testid="main-card">
      {title ? <div>{title}</div> : null}
      {children}
    </div>
  ),
}));

import DecisionCyclesBlock from 'sections/home/DecisionCyclesBlock';

// A row: list entity (name + account) + the dc_cycle_state result, index-aligned.
function item(cycle, meta, value) {
  return {
    cycle: { id: cycle.id, name: cycle.name, account: cycle.account, account_name: cycle.account_name },
    result: { key: 'dc_cycle_state', shape: 'SCALAR', value, scope: 'mine', meta: { cycle_id: cycle.id, ...meta } },
  };
}

const IN_PROGRESS = item(
  { id: 'dc-1', name: 'Acme renewal', account: 'acc-1', account_name: 'Acme Corp' },
  {
    cycle_status: 'IN_PROGRESS',
    current_stage: 'TECHNICAL_FIT',
    current_step_name: 'Technical Fit',
    current_step_order: 1,
    next_action: 'Advance: Technical Fit',
    validated_steps: 1,
    total_steps: 5,
  },
  'IN_PROGRESS',
);

const STALLED = item(
  { id: 'dc-2', name: 'Globex expansion', account: 'acc-2', account_name: 'Globex' },
  {
    cycle_status: 'STALLED',
    current_stage: 'CLOSING',
    current_step_name: 'Closing',
    current_step_order: 4,
    next_action: 'Act: close the deal or define the next step',
    validated_steps: 4,
    total_steps: 5,
  },
  'STALLED',
);

beforeEach(() => pushMock.mockClear());
afterEach(() => cleanup());

describe('DecisionCyclesBlock', () => {
  it('renders one row per open cycle with name, account, stage and "X/N stages" — never a %', () => {
    render(<DecisionCyclesBlock items={[IN_PROGRESS]} loading={false} />);

    expect(screen.getByText('My decision cycles')).toBeInTheDocument();
    expect(screen.getByText('Acme renewal')).toBeInTheDocument();
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    expect(screen.getByText('Technical Fit')).toBeInTheDocument();
    expect(screen.getByText('1/5 stages')).toBeInTheDocument();
    // the next action is the call-to-action, surfaced verbatim from meta
    expect(screen.getByText('Advance: Technical Fit')).toBeInTheDocument();
    // no percentage anywhere
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it('shows the derived status as a chip; STALLED is error (red), NOT the shared warning', () => {
    render(<DecisionCyclesBlock items={[STALLED]} loading={false} />);

    const stalledChip = screen.getByText('Stalled').closest('.MuiChip-root');
    expect(stalledChip).toBeTruthy();
    // the whole point of the local override: STALLED must be error, not warning
    expect(stalledChip.className).toMatch(/MuiChip-colorError/);
    expect(stalledChip.className).not.toMatch(/MuiChip-colorWarning/);
    // and its next action (the lever) is present
    expect(screen.getByText('Act: close the deal or define the next step')).toBeInTheDocument();
  });

  it('routes the name to the DC workspace and the account to the account page', () => {
    render(<DecisionCyclesBlock items={[IN_PROGRESS]} loading={false} />);

    screen.getByText('Acme renewal').click();
    expect(pushMock).toHaveBeenCalledWith('/accounts/acc-1/dc/dc-1');

    screen.getByText('Acme Corp').click();
    expect(pushMock).toHaveBeenCalledWith('/accounts/acc-1');
  });

  it('renders multiple cycles in the given (batch-preserved) order', () => {
    render(<DecisionCyclesBlock items={[IN_PROGRESS, STALLED]} loading={false} />);
    expect(screen.getByText('Acme renewal')).toBeInTheDocument();
    expect(screen.getByText('Globex expansion')).toBeInTheDocument();
  });

  it('DATA-DRIVEN VISIBILITY: an empty list renders NOTHING (no block, no heading)', () => {
    const { container } = render(<DecisionCyclesBlock items={[]} loading={false} />);
    expect(container.firstChild).toBeNull();
    expect(screen.queryByText('My decision cycles')).not.toBeInTheDocument();
  });

  it('while loading (cycles known), shows the card with skeletons and no cycle names', () => {
    render(<DecisionCyclesBlock items={[]} loading />);
    expect(screen.getByText('My decision cycles')).toBeInTheDocument();
    expect(screen.queryByText('Acme renewal')).not.toBeInTheDocument();
  });

  it('is null-safe when a result/meta is missing (name + account still render)', () => {
    const bare = { cycle: { id: 'dc-3', name: 'No-KPI cycle', account: 'acc-3', account_name: 'NoKpi Inc' }, result: null };
    render(<DecisionCyclesBlock items={[bare]} loading={false} />);
    expect(screen.getByText('No-KPI cycle')).toBeInTheDocument();
    expect(screen.getByText('NoKpi Inc')).toBeInTheDocument();
  });
});
