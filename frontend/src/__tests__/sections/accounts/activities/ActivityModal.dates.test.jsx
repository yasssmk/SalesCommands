// frontend/src/__tests__/sections/accounts/activities/ActivityModal.dates.test.jsx
//
// Sprint « Cycle de vie des contacts », 8g-1b — the server now refuses an
// activity with BOTH a scheduled date and a due date (8g-1, TD-230,
// backend/app_modules/activities/services/date_rules.py). The old
// ActivityModal (still used by 5 screens) shows both pickers and only
// required « at least one »: its Yup rule now says the server's rule —
// exactly one date, the server's message (DATES_EXCLUSIVE). The REAL modal;
// the pickers / API mocked (the harness of ActivityModal.submitPayload.test).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "", style: { fontFamily: "Public Sans" }, variable: "" }),
}));
// Each date picker: a « pick » button (sets a date) + the field's helper text.
vi.mock("@mui/x-date-pickers/DatePicker", async () => {
  const { default: dayjs } = await import("dayjs");
  return {
    DatePicker: (props) => (
      <div data-testid="date-field">
        <button type="button" data-testid="pick-date" onClick={() => props.onChange(dayjs("2026-12-01"))}>
          pick
        </button>
        <span data-testid="date-helper">{props.slotProps?.textField?.helperText || ""}</span>
      </div>
    ),
  };
});
vi.mock("@mui/x-date-pickers/TimePicker", () => ({ TimePicker: () => null }));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));
vi.mock("api/accounts/activities", () => ({
  createActivity: vi.fn(async () => ({ success: true, data: {} })),
  createActivityWithEntities: vi.fn(async () => ({ success: true, data: {} })),
  updateActivity: vi.fn(),
  useGetActivityChoices: () => ({ choicesLoading: false }),
  ACTIVITY_TYPES: { CALL: "CALL", EMAIL: "EMAIL", MEETING: "MEETING", TASK: "TASK" },
  ACTIVITY_TYPE_LABELS: { CALL: "Call", EMAIL: "Email", MEETING: "Meeting", TASK: "Task" },
  ACTIVITY_STATUSES: { PLANNED: "PLANNED", COMPLETED: "COMPLETED" },
  ACTIVITY_STATUS_LABELS: { PLANNED: "Planned", COMPLETED: "Completed" },
}));
vi.mock("api/businessData/contacts", () => ({
  useGetContacts: () => ({ contacts: [], contactsLoading: false }),
}));
vi.mock("api/accounts/decisionCycles", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetDecisionCyclesByAccount: () => ({ cycles: [], cyclesLoading: false }),
  useGetDecisionStepsByCycle: () => ({ steps: [], stepsLoading: false }),
}));
vi.mock("utils/displayError", () => ({ displayErrorSnackbar: vi.fn(), displaySuccessSnackbar: vi.fn() }));

import ActivityModal from "sections/accounts/activities/ActivityModal";
import { createActivity } from "api/accounts/activities";

const DATES_EXCLUSIVE = "An activity has a scheduled date or a due date, not both.";

const renderModal = () =>
  render(<ActivityModal open onClose={() => {}} accountId="acc1" activity={null} defaultActivityType="TASK" />);
const fillTitle = () =>
  fireEvent.change(document.getElementById("title"), { target: { value: "Send the recap" } });
const pickScheduled = () => fireEvent.click(screen.getAllByTestId("pick-date")[0]);
const pickDue = () => fireEvent.click(screen.getAllByTestId("pick-date")[1]);
const submit = () => fireEvent.click(screen.getByRole("button", { name: "Create", hidden: true }));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("ActivityModal — exactly one date, as the server (8g-1b)", () => {
  it("both dates: blocked on the front, the server's message", async () => {
    renderModal();
    fillTitle();
    pickScheduled();
    pickDue();
    submit();
    await waitFor(() =>
      expect(screen.getAllByTestId("date-helper").map((e) => e.textContent)).toContain(DATES_EXCLUSIVE));
    expect(createActivity).not.toHaveBeenCalled();
  });

  it.each([["the scheduled date", pickScheduled], ["the due date", pickDue]])("%s alone: created", async (_l, pick) => {
    renderModal();
    fillTitle();
    pick();
    submit();
    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
  });

  it("no date: still blocked (unchanged)", async () => {
    renderModal();
    fillTitle();
    submit();
    await waitFor(() =>
      expect(screen.getAllByTestId("date-helper").map((e) => e.textContent))
        .toContain("Scheduled date or due date is required"));
    expect(createActivity).not.toHaveBeenCalled();
  });
});
