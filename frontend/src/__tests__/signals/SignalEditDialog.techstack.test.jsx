// frontend/src/__tests__/signals/SignalEditDialog.techstack.test.jsx
//
// The TechStack edit form emits the signal's own tech identity (S10):
// tech_name plus the three qualification booleans, and never a catalogue
// reference.
//
// This file previously guarded an object-vs-UUID bug: the form had to
// emit `tech_catalog_entry` as a UUID and omit it entirely when
// unchanged, because the compact catalogue object leaked through and
// 400'd at the backend FK. The catalogue is gone, so that class of bug
// is gone with it — what needs guarding now is that the free-text name
// and the booleans reach the API, and that no catalogue key survives
// anywhere in the payload.
//
// Exercises the real edit path (form -> handleSave -> updateSignal).

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true, data: {} })),
  reopenSignal: vi.fn(() => Promise.resolve({ success: true, data: {} })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

vi.mock("api/businessData/contacts", () => ({
  useGetContactChoices: () => ({ standardDepartments: [] }),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import SignalEditDialog from "sections/activities/signals/SignalEditDialog";
import { updateSignal } from "api/signals/signals";

// ==============================|| FIXTURES ||============================== //

const VALIDATED_TECHSTACK = {
  id: "ts1",
  status: "VALIDATED",
  tech_name: "Salesforce",
  is_competitor: false,
  is_integration: false,
  is_to_replace: false,
  usage_scope: null,
  usage_departments: [],
  usage_start_year: null,
  renewal_date: null,
  cost_description: "",
  is_discontinued: false,
  discontinued_date: null,
  source_quote: "we use salesforce",
  notes: "old note",
};

const PENDING_TECHSTACK = {
  ...VALIDATED_TECHSTACK,
  id: "ts2",
  status: "PENDING",
  tech_name: "Notion",
  source_quote: "we use notion",
  notes: "",
};

function renderDialog(signal) {
  return render(
    <SignalEditDialog
      open
      onClose={vi.fn()}
      onSuccess={vi.fn()}
      signal={signal}
      signalType="tech-stack"
      accountId="acc-1"
      choices={{}}
      choicesLoading={false}
    />,
  );
}

function save() {
  fireEvent.click(screen.getByRole("button", { name: /save changes/i }));
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

// ==============================|| TESTS ||============================== //

describe("SignalEditDialog — tech-stack identity payload", () => {
  it("emits tech_name on a notes-only edit of a validated signal", async () => {
    renderDialog(VALIDATED_TECHSTACK);

    fireEvent.change(screen.getByDisplayValue("old note"), {
      target: { value: "new note" },
    });
    save();

    await waitFor(() => expect(updateSignal).toHaveBeenCalled());

    const [type, id, payload] = updateSignal.mock.calls[0];
    expect(type).toBe("tech-stack");
    expect(id).toBe("ts1");
    expect(payload.tech_name).toBe("Salesforce");
    expect(payload.notes).toBe("new note");
  });

  it("never sends a catalogue key", async () => {
    renderDialog(VALIDATED_TECHSTACK);

    // The dialog guards no-op saves, so touch a field first.
    fireEvent.change(screen.getByDisplayValue("old note"), {
      target: { value: "touched" },
    });
    save();

    await waitFor(() => expect(updateSignal).toHaveBeenCalled());

    const [, , payload] = updateSignal.mock.calls[0];
    expect(payload).not.toHaveProperty("tech_catalog_entry");
    expect(payload).not.toHaveProperty("tech_catalog_entry_id");
  });

  it("lets a validated signal's tool name be corrected", async () => {
    // No catalogue lock any more: fixing a transcription is a normal edit.
    renderDialog(VALIDATED_TECHSTACK);

    fireEvent.change(screen.getByDisplayValue("Salesforce"), {
      target: { value: "Salesforce CRM" },
    });
    save();

    await waitFor(() => expect(updateSignal).toHaveBeenCalled());

    const [, , payload] = updateSignal.mock.calls[0];
    expect(payload.tech_name).toBe("Salesforce CRM");
  });

  it("emits only is_to_replace (competitor and integration toggles are gone)", async () => {
    renderDialog(PENDING_TECHSTACK);

    // The manual "Competitor" and "Integration" toggles were both retired —
    // competitors are their own signal type, and an integration requirement is
    // now a TECHNICAL ConstraintSignal. Only "to replace" survives.
    expect(screen.queryByLabelText("Tool is a competitor")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Tool is an integration")).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Tool is to be replaced"));
    save();

    await waitFor(() => expect(updateSignal).toHaveBeenCalled());

    const [, , payload] = updateSignal.mock.calls[0];
    expect(payload).not.toHaveProperty("is_competitor");
    expect(payload).not.toHaveProperty("is_integration");
    expect(payload.is_to_replace).toBe(true);
  });

  it("blocks a save that blanks the tool name", async () => {
    renderDialog(VALIDATED_TECHSTACK);

    fireEvent.change(screen.getByDisplayValue("Salesforce"), {
      target: { value: "   " },
    });
    save();

    await waitFor(() =>
      expect(screen.getByText(/name the tool/i)).toBeInTheDocument(),
    );
    expect(updateSignal).not.toHaveBeenCalled();
  });
});
