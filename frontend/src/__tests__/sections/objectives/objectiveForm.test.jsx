// frontend/src/__tests__/sections/objectives/objectiveForm.test.jsx
//
// The objective form: a valid submit sends the exact payload WITHOUT a campaign
// (objectives from this page are global); Yup rejects end < start and a start
// date in the past (create). The third-party MUI date picker is stubbed to a
// plain input for testability; our own components stay real.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import dayjs from 'dayjs';

// Stub the third-party date picker to a plain input (not one of OUR components);
// surface the helperText so Yup errors are assertable.
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
vi.mock('utils/displayError', () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));
vi.mock('utils/formErrorHandler', () => ({ handleFormikError: vi.fn() }));

import ObjectiveForm from 'sections/objectives/ObjectiveForm';

const FUTURE_START = dayjs().add(10, 'day').format('YYYY-MM-DD');
const FUTURE_END = dayjs().add(40, 'day').format('YYYY-MM-DD');
const PAST_START = dayjs().subtract(10, 'day').format('YYYY-MM-DD');

afterEach(() => {
  cleanup();
  createObjective.mockClear();
});

async function pickMetric(label) {
  fireEvent.mouseDown(screen.getAllByRole('combobox')[0]); // only Select is Metric now
  const option = await screen.findByRole('option', { name: label });
  fireEvent.click(option);
}

describe('ObjectiveForm', () => {
  it('has NO campaign field and submits a payload without source_campaign', async () => {
    const user = userEvent.setup();
    render(<ObjectiveForm closeModal={vi.fn()} />);

    // the campaign select is gone
    expect(screen.queryByLabelText('Campaign')).toBeNull();

    await pickMetric('Revenue won');
    await user.type(screen.getByLabelText('Target value'), '100');
    fireEvent.change(screen.getByLabelText('Start date'), { target: { value: FUTURE_START } });
    fireEvent.change(screen.getByLabelText('End date'), { target: { value: FUTURE_END } });

    await user.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(createObjective).toHaveBeenCalledTimes(1));
    const payload = createObjective.mock.calls[0][0];
    expect(payload).toEqual({
      metric: 'REVENUE_WON',
      target_value: 100,
      period_start: FUTURE_START,
      period_end: FUTURE_END,
    });
    expect('source_campaign' in payload).toBe(false);
  });

  it('rejects end < start (Yup) and does not call the API', async () => {
    const user = userEvent.setup();
    render(<ObjectiveForm closeModal={vi.fn()} />);

    await pickMetric('Meetings');
    await user.type(screen.getByLabelText('Target value'), '5');
    fireEvent.change(screen.getByLabelText('Start date'), { target: { value: FUTURE_END } });
    fireEvent.change(screen.getByLabelText('End date'), { target: { value: FUTURE_START } });

    await user.click(screen.getByRole('button', { name: 'Create' }));

    expect(await screen.findByText(/End date must be on or after start date/i)).toBeTruthy();
    expect(createObjective).not.toHaveBeenCalled();
  });

  it('rejects a start date in the past on create (Yup) and does not call the API', async () => {
    const user = userEvent.setup();
    render(<ObjectiveForm closeModal={vi.fn()} />);

    await pickMetric('Meetings');
    await user.type(screen.getByLabelText('Target value'), '5');
    fireEvent.change(screen.getByLabelText('Start date'), { target: { value: PAST_START } });
    fireEvent.change(screen.getByLabelText('End date'), { target: { value: FUTURE_END } });

    await user.click(screen.getByRole('button', { name: 'Create' }));

    expect(await screen.findByText(/Start date cannot be in the past/i)).toBeTruthy();
    expect(createObjective).not.toHaveBeenCalled();
  });

  it('does NOT block editing an objective whose start is already in the past', async () => {
    const user = userEvent.setup();
    const objective = {
      id: '11111111-1111-1111-1111-111111111111',
      metric: 'MEETINGS',
      target_value: '5',
      period_start: PAST_START, // already running
      period_end: FUTURE_END,
    };
    render(<ObjectiveForm objective={objective} closeModal={vi.fn()} />);
    // change only the target and save — the past start must not block the edit.
    await user.clear(screen.getByLabelText('Target value'));
    await user.type(screen.getByLabelText('Target value'), '9');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    // no "past" error surfaces
    expect(screen.queryByText(/Start date cannot be in the past/i)).toBeNull();
  });
});
