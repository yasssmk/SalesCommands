// frontend/src/__tests__/signals/SignalEditDialog.techstack.test.jsx
//
// Regression guard for the object-vs-UUID edit bug: the TechStack edit
// form must emit tech_catalog_entry as a UUID and OMIT it entirely when
// unchanged. Exercises the real edit path (form -> handleSave ->
// updateSignal), where the compact catalog object used to leak through
// and 400 at the backend FK.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";

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

// Interactive stub: exposes the current value id and a button that fires
// onChange with a fresh catalog entry (so we can exercise the attach path).
vi.mock("components/AsyncSelection/AsyncTechCatalogSelect", () => ({
  default: ({ value, onChange, disabled }) => (
    <div data-testid="catalog-select">
      <span data-testid="catalog-value">{value ? value.id : "none"}</span>
      <button
        type="button"
        disabled={disabled}
        onClick={() =>
          onChange(null, {
            id: "cat-NEW",
            company_name: "New",
            product_name: "Tool",
          })
        }
      >
        pick-new
      </button>
    </div>
  ),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import SignalEditDialog from "sections/activities/signals/SignalEditDialog";
import { updateSignal } from "api/signals/signals";

// ==============================|| FIXTURES ||============================== //

const VALIDATED_TECHSTACK = {
  id: "ts1",
  status: "VALIDATED",
  tech_catalog_entry: {
    id: "cat-1",
    company_name: "Salesforce",
    product_name: "Sales Cloud",
  },
  usage_scope: null,
  usage_department: null,
  usage_start_year: null,
  renewal_date: null,
  cost_description: "",
  is_discontinued: false,
  discontinued_date: null,
  source_quote: "we use salesforce",
  notes: "old note",
};

const PENDING_UNMATCHED = {
  id: "ts2",
  status: "PENDING",
  tech_catalog_entry: null,
  metadata: { pending_tech_name: "Notion" },
  usage_scope: null,
  usage_department: null,
  usage_start_year: null,
  renewal_date: null,
  cost_description: "",
  is_discontinued: false,
  discontinued_date: null,
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

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

// ==============================|| TESTS ||============================== //

describe("SignalEditDialog — tech-stack catalog anchor payload", () => {
  it("omits tech_catalog_entry on a notes-only edit of a validated signal", async () => {
    renderDialog(VALIDATED_TECHSTACK);

    fireEvent.change(screen.getByDisplayValue("old note"), {
      target: { value: "new note" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(updateSignal).toHaveBeenCalled());

    const [type, id, payload] = updateSignal.mock.calls[0];
    expect(type).toBe("tech-stack");
    expect(id).toBe("ts1");
    // The immutable anchor is not re-sent (no object, no UUID).
    expect(payload).not.toHaveProperty("tech_catalog_entry");
    expect(payload.notes).toBe("new note");
  });

  it("emits tech_catalog_entry as a UUID when attaching on a PENDING signal", async () => {
    renderDialog(PENDING_UNMATCHED);

    // Attach a catalog entry via the (enabled) select stub.
    fireEvent.click(screen.getByRole("button", { name: "pick-new" }));
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(updateSignal).toHaveBeenCalled());

    const [, , payload] = updateSignal.mock.calls[0];
    // UUID string, not the compact object.
    expect(payload.tech_catalog_entry).toBe("cat-NEW");
  });
});
