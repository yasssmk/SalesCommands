// frontend/src/__tests__/sections/objectives/objectiveForm.test.jsx
//
// The objective form: a valid submit sends the exact payload (metric, target,
// dates, optional campaign), and Yup rejects end < start (no API call). The
// third-party MUI date picker is stubbed to a plain input for testability; our
// own components stay real. Data helpers are mocked.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Stub the third-party date picker to a plain date input (not one of OUR shared
// components). onChange receives the raw string, which the form formats.
vi.mock('@mui/x-date-pickers/DatePicker', () => ({
  DatePicker: ({ label, onChange, slotProps }) => (
    <span>
      <input aria-label={label} onChange={(e) => onChange(e.target.value)} />
      {slotProps?.textField?.helperText ? <span>{slotProps.textField.helperText}</span> : null}
    </span>
  ),
}));
vi.mock('@mui/x-date-pickers/LocalizationProvider', () => ({
  LocalizationProvider: ({ children }) => children,
}));
vi.mock('@mui/x-date-pickers/AdapterDayjs', () => ({ AdapterDayjs: {} }));

const createObjective = vi.fn(() => Promise.resolve({ success: true, data: {} }));
vi.mock('api/objectives/objectives', () => ({
  createObjective: (...a) => createObjective(...a),
  updateObjective: vi.fn(() => Promise.resolve({ success: true })),
}));
vi.mock('api/campaigns/campaigns', () => ({
  useGetCampaigns: () => ({ campaigns: [{ id: 'c1', name: 'Q1 Outbound' }] }),
}));
vi.mock('utils/displayError', () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));
vi.mock('utils/formErrorHandler', () => ({ handleFormikError: vi.fn() }));

import ObjectiveForm from 'sections/objectives/ObjectiveForm';

afterEach(() => {
  cleanup();
  createObjective.mockClear();
});

async function pickMetric(label) {
  // Two Selects render as comboboxes (metric, then campaign); metric is first.
  const combos = screen.getAllByRole('combobox');
  fireEvent.mouseDown(combos[0]);
  const option = await screen.findByRole('option', { name: label });
  fireEvent.click(option);
}

describe('ObjectiveForm', () => {
  it('submits the exact payload (metric, target, dates, global campaign)', async () => {
    const user = userEvent.setup();
    render(<ObjectiveForm closeModal={vi.fn()} />);

    await pickMetric('Revenue won');
    await user.type(screen.getByLabelText('Target value'), '100');
    fireEvent.change(screen.getByLabelText('Start date'), { target: { value: '2026-01-01' } });
    fireEvent.change(screen.getByLabelText('End date'), { target: { value: '2026-12-31' } });

    await user.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(createObjective).toHaveBeenCalledTimes(1));
    expect(createObjective).toHaveBeenCalledWith({
      metric: 'REVENUE_WON',
      target_value: 100,
      period_start: '2026-01-01',
      period_end: '2026-12-31',
      source_campaign: null, // empty select -> global objective
    });
  });

  it('rejects end < start (Yup) and does not call the API', async () => {
    const user = userEvent.setup();
    render(<ObjectiveForm closeModal={vi.fn()} />);

    await pickMetric('Meetings');
    await user.type(screen.getByLabelText('Target value'), '5');
    fireEvent.change(screen.getByLabelText('Start date'), { target: { value: '2026-06-01' } });
    fireEvent.change(screen.getByLabelText('End date'), { target: { value: '2026-01-01' } });

    await user.click(screen.getByRole('button', { name: 'Create' }));

    expect(await screen.findByText(/End date must be on or after start date/i)).toBeTruthy();
    expect(createObjective).not.toHaveBeenCalled();
  });
});
