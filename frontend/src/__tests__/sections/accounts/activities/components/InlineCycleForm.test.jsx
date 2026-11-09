// frontend/src/__tests__/sections/accounts/activities/components/InlineCycleForm.test.jsx
//
// Lot 3 / 10 (TD-305) — InlineCycleForm follows the drawer's validation
// pattern: the name is an InlineEditableValue (read → click → edit, the
// required message under it, as the summary of the Edit*Content drawers) and
// the form is validated / discarded by THE shared ✓/✗ row
// (ConfirmCancelActions, as the TechStack start-year editor).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup, act } from "@testing-library/react";
import AphoriqTheme from "../../../../_utils/aphoriqTheme";
import InlineCycleForm from "sections/accounts/activities/components/InlineCycleForm";

const render = (ui) => rtlRender(<AphoriqTheme>{ui}</AphoriqTheme>);
afterEach(() => cleanup());

const typeName = (value) => {
  fireEvent.click(screen.getByTestId("inline-read-cycle_name"));
  fireEvent.change(screen.getByTestId("inline-input-cycle_name"), { target: { value } });
  fireEvent.keyDown(screen.getByTestId("inline-input-cycle_name"), { key: "Enter" });
};

describe("InlineCycleForm — the drawer's validation pattern (TD-305)", () => {
  it("✓ (Confirm new cycle) saves the name + the chosen step", async () => {
    const onSave = vi.fn();
    render(<InlineCycleForm onSave={onSave} />);
    typeName("  Deal Acme ");
    fireEvent.click(screen.getByTestId("stage-pill-TECHNICAL_FIT"));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Confirm new cycle" })); });
    expect(onSave).toHaveBeenCalledWith({ name: "Deal Acme", is_active: true, step_stage: "TECHNICAL_FIT" });
  });

  it("✓ without a name → the required message under the field, no save", async () => {
    const onSave = vi.fn();
    render(<InlineCycleForm onSave={onSave} />);
    await act(async () => { fireEvent.click(screen.getByTestId("inline-cycle-confirm")); });
    expect(screen.getByText("Cycle name is required")).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("✗ (Discard new cycle) calls onCancel when given", () => {
    const onCancel = vi.fn();
    render(<InlineCycleForm onSave={vi.fn()} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole("button", { name: "Discard new cycle" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("✗ without onCancel (mandatory cycle) discards the draft", () => {
    render(<InlineCycleForm onSave={vi.fn()} />);
    typeName("Deal Acme");
    expect(screen.getByText("Deal Acme")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("inline-cycle-cancel"));
    expect(screen.queryByText("Deal Acme")).toBeNull();
  });
});
