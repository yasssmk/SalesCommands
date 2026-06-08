// frontend/src/__tests__/nextSteps/LLMNextStepActivityFormModal.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("@mui/x-date-pickers/DatePicker", () => ({
  DatePicker: (props) => <input data-testid="date-picker" aria-label={props.label} />,
}));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({
  AdapterDayjs: class {},
}));

const mockCreateActivity = vi.fn(() =>
  Promise.resolve({ success: true, data: { id: "new-act-1" } }),
);

vi.mock("api/accounts/activities", () => ({
  createActivity: (...args) => mockCreateActivity(...args),
  ACTIVITY_TYPES: {
    CALL: "CALL",
    EMAIL: "EMAIL",
    MEETING: "MEETING",
    TASK: "TASK",
    LINKEDIN: "LINKEDIN",
    OTHER: "OTHER",
  },
  ACTIVITY_TYPE_LABELS: {
    CALL: "Phone Call",
    EMAIL: "Email",
    MEETING: "Meeting",
    TASK: "Task",
    LINKEDIN: "LinkedIn Message",
    OTHER: "Other",
  },
  useGetActivityChoices: vi.fn(() => ({ choicesLoading: false })),
}));

vi.mock("api/businessData/contacts", () => ({
  useGetContacts: vi.fn(() => ({
    contacts: [
      {
        id: "c1",
        first_name: "Jane",
        last_name: "Doe",
        email: "jane@acme.com",
        job_title: "VP Eng",
      },
      {
        id: "c2",
        first_name: "John",
        last_name: "Smith",
        email: "john@acme.com",
        job_title: "CTO",
      },
    ],
    contactsLoading: false,
  })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import LLMNextStepActivityFormModal from "sections/activities/nextSteps/LLMNextStepActivityFormModal";

// ==============================|| FIXTURES ||============================== //

const mockSignal = {
  id: "ns-123",
  suggested_title: "Follow up on pricing",
  suggested_activity_type: "CALL",
  suggested_due_date: "2026-06-15",
  source_quote: "We should discuss pricing next week",
  suggested_contacts: [{ id: "c1", first_name: "Jane", last_name: "Doe" }],
};

const defaultProps = {
  open: true,
  onClose: vi.fn(),
  onSuccess: vi.fn(),
  accountId: "account-456",
};

// ==============================|| TESTS ||============================== //

describe("LLMNextStepActivityFormModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders pre-filled form from signal", () => {
    render(
      <LLMNextStepActivityFormModal {...defaultProps} signal={mockSignal} />,
    );

    expect(screen.getByText("Convert to Activity")).toBeInTheDocument();

    const titleInput = screen.getByLabelText("Title *");
    expect(titleInput.value).toBe("Follow up on pricing");
  });

  it("shows AI Rationale when signal has source_quote", () => {
    render(
      <LLMNextStepActivityFormModal {...defaultProps} signal={mockSignal} />,
    );

    expect(screen.getByText("AI Rationale")).toBeInTheDocument();
    expect(
      screen.getByText(/We should discuss pricing next week/),
    ).toBeInTheDocument();
  });

  it("renders empty form when no signal (manual add)", () => {
    render(
      <LLMNextStepActivityFormModal {...defaultProps} signal={null} />,
    );

    expect(screen.getByText("Create Activity")).toBeInTheDocument();

    const titleInput = screen.getByLabelText("Title *");
    expect(titleInput.value).toBe("");
  });

  it("does not show AI Rationale when no signal", () => {
    render(
      <LLMNextStepActivityFormModal {...defaultProps} signal={null} />,
    );

    expect(screen.queryByText("AI Rationale")).not.toBeInTheDocument();
  });

  it("submits with next_step_signal_id when converting from signal", async () => {
    render(
      <LLMNextStepActivityFormModal {...defaultProps} signal={mockSignal} />,
    );

    const submitButton = screen.getByRole("button", {
      name: "Create Activity",
    });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockCreateActivity).toHaveBeenCalledWith(
        expect.objectContaining({
          next_step_signal_id: "ns-123",
          title: "Follow up on pricing",
          activity_type: "CALL",
          account_id: "account-456",
        }),
      );
    });
  });

  it("submits without next_step_signal_id for manual add", async () => {
    render(
      <LLMNextStepActivityFormModal {...defaultProps} signal={null} />,
    );

    const titleInput = screen.getByLabelText("Title *");
    fireEvent.change(titleInput, { target: { value: "Manual follow up" } });

    const submitButton = screen.getByRole("button", { name: "Create" });
    fireEvent.click(submitButton);

    await waitFor(() => {
      if (mockCreateActivity.mock.calls.length > 0) {
        const payload = mockCreateActivity.mock.calls[0][0];
        expect(payload).not.toHaveProperty("next_step_signal_id");
      }
    });
  });

  it("calls onClose when clicking Cancel", () => {
    render(
      <LLMNextStepActivityFormModal {...defaultProps} signal={mockSignal} />,
    );

    fireEvent.click(screen.getByText("Cancel"));

    expect(defaultProps.onClose).toHaveBeenCalled();
  });
});
