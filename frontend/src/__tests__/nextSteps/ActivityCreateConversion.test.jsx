// frontend/src/__tests__/nextSteps/ActivityCreateConversion.test.jsx
//
// Sprint Next steps 5.13 — "Start Decision Cycle" moves from the ActivityModal
// to the creation drawer (EditActivityContent, create mode).
//   13.1 — the drawer accepts `sourceActivityId` and sends it as
//          source_activity_id on BOTH creation paths (createActivity, and
//          createActivityWithEntities when something is created inline) —
//          what the ActivityModal sent (ActivityModal.jsx: source_activity_id),
//          the link the backend reads to call the new cycle "born" from the
//          campaign activity (and to stamp its source_campaign).
// The drawer and the coque are REAL; the API calls and data hooks are mocked.

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, within, waitFor } from "@testing-library/react";
import WorkspaceCoque from "../_utils/workspaceCoque";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "act-1" }),
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/activities/act-1",
}));
vi.mock("@mui/x-date-pickers/DatePicker", () => ({ DatePicker: () => <input /> }));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));
vi.mock("@mui/x-date-pickers/TimePicker", () => ({ TimePicker: () => <input /> }));
vi.mock("api/accounts/activities", async (importOriginal) => ({
  ...(await importOriginal()),
  createActivity: vi.fn(async () => ({ success: true, data: { id: "act-new" } })),
  createActivityWithEntities: vi.fn(async () => ({ success: true, data: { id: "act-new" } })),
}));
vi.mock("api/accounts/decisionCycles", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetDecisionCyclesByAccount: vi.fn(() => ({ cycles: [], cyclesLoading: false })),
  useGetDecisionStepsByCycle: vi.fn(() => ({ steps: [], stepsLoading: false })),
}));
vi.mock("api/signals/signals", async (importOriginal) => ({
  ...(await importOriginal()),
  useNextStepCitedContacts: vi.fn(() => ({ citedContacts: mockCited, citedLoading: false })),
}));
vi.mock("hooks/useAuth", () => ({
  useAuth: () => ({ user: { id: "u-1", first_name: "Ann", last_name: "Owner", email: "ann@acme.test" }, tenantId: "t-1" }),
  default: () => ({ user: { id: "u-1", first_name: "Ann", last_name: "Owner", email: "ann@acme.test" }, tenantId: "t-1" }),
}));
// The inline contact sub-form → a one-click save (as in the band tests).
vi.mock("sections/accounts/activities/components", async (importOriginal) => ({
  ...(await importOriginal()),
  InlineContactForm: ({ onSave }) => (
    <button type="button" onClick={() => onSave({ first_name: "Isabelle", last_name: "Roux" })}>
      save inline contact
    </button>
  ),
}));
vi.mock("utils/displayError", () => ({ displaySuccessSnackbar: vi.fn(), displayErrorSnackbar: vi.fn() }));

import { createActivity, createActivityWithEntities } from "api/accounts/activities";
import EditActivityContent from "sections/activities/workspace/EditActivityContent";

let mockCited = [];
const THOMAS = { id: "c-1", first_name: "Thomas", last_name: "Lefèvre", job_title: "CTO" };

// A next step pre-fills a valid form (title, date, the cited contact).
const NEXT_STEP = {
  id: "ns-1", status: "PENDING", suggested_title: "Discovery meeting",
  suggested_activity_type: "MEETING", suggested_due_date: "2026-11-12",
};

const renderDrawer = (props = {}) =>
  render(
    <WorkspaceCoque>
      <EditActivityContent mode="create" accountId="acc-1" nextStep={NEXT_STEP} {...props} />
    </WorkspaceCoque>,
  );
const saveButton = () => screen.getByRole("button", { name: "Save" });

beforeEach(() => { mockCited = [{ name: "Thomas Lefèvre", contact: THOMAS }]; });
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("13.1 — the creation drawer sends source_activity_id", () => {
  it("createActivity: the payload carries source_activity_id", async () => {
    renderDrawer({ sourceActivityId: "act-camp" });
    fireEvent.click(saveButton());
    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
    expect(createActivity.mock.calls[0][0].source_activity_id).toBe("act-camp");
  });

  it("createActivityWithEntities (a contact created inline): the activity carries source_activity_id", async () => {
    renderDrawer({ sourceActivityId: "act-camp" });
    fireEvent.click(within(screen.getByTestId("activity-create")).getByTestId("add-inline-contact"));
    fireEvent.click(screen.getByRole("button", { name: "save inline contact" }));
    fireEvent.click(saveButton());
    await waitFor(() => expect(createActivityWithEntities).toHaveBeenCalledTimes(1));
    expect(createActivityWithEntities.mock.calls[0][0].activity.source_activity_id).toBe("act-camp");
  });

  it("without sourceActivityId: no source_activity_id key (the payload as before)", async () => {
    renderDrawer();
    fireEvent.click(saveButton());
    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
    expect(createActivity.mock.calls[0][0]).not.toHaveProperty("source_activity_id");
  });
});
