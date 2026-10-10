// frontend/src/__tests__/sections/activities/workspace/EditObjectionContent.test.jsx
//
// Objection S2 — the Objection (blockers) EDIT drawer, a clone of
// EditConstraintContent on the standard chassis. Fields: summary (Yup identical
// to Constraint) + contact (AsyncContactSelect, account-scoped, clearable) +
// source_quote. Save PATCHes updateSignal("blockers", id, payload) with contact
// = the UUID (never the object / the event) or null.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

// ---- mocks (before importing the component) ----
vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));
const closeDrawer = vi.fn();
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ closeDrawer, openDrawer: vi.fn() }),
}));
// The picker emits onChange(event, contact) — the AsyncContactSelect signature.
const PICKED = {
  id: "c-picked",
  first_name: "Paul",
  last_name: "Picked",
  job_title: "CTO",
  email: "paul@example.com",
};
vi.mock("components/AsyncSelection/AsyncContactSelect", () => ({
  default: (props) => (
    <div data-testid="objection-contact-select" data-filters={JSON.stringify(props.filters ?? null)}>
      <span data-testid="objection-contact-value">
        {props.value ? `${props.value.first_name} ${props.value.last_name}` : "none"}
      </span>
      <button type="button" onClick={(e) => props.onChange(e, PICKED)}>
        pick
      </button>
      <button type="button" onClick={(e) => props.onChange(e, null)}>
        clear
      </button>
    </div>
  ),
}));

import EditObjectionContent from "sections/activities/workspace/EditObjectionContent";
import { updateSignal } from "api/signals/signals";

const OBJECTION = {
  id: "objection-1",
  status: "PENDING",
  summary: "Budget frozen until Q2 for every new tool",
  contact: { id: "c-orig", first_name: "Sophie", last_name: "Martin", job_title: "CFO" },
  source_quote: "Our budget is completely frozen",
};

const renderEdit = (objection = OBJECTION, props = {}) =>
  render(
    <AphoriqTheme>
      <EditObjectionContent objection={objection} accountId="acc-1" {...props} />
    </AphoriqTheme>,
  );

const save = async () => {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
  });
};

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("EditObjectionContent (Objection S2)", () => {
  it("renders the fields pre-filled (summary, current contact, quote) + no own 'Edit objection' title", () => {
    renderEdit();
    ["summary", "source_quote"].forEach((name) =>
      expect(screen.getByTestId(`inline-read-${name}`)).toBeInTheDocument(),
    );
    expect(screen.getByText(OBJECTION.summary)).toBeInTheDocument();
    expect(screen.getByTestId("objection-contact-value")).toHaveTextContent("Sophie Martin");
    expect(screen.getByText(OBJECTION.source_quote)).toBeInTheDocument();
    expect(screen.queryByText("Edit objection")).not.toBeInTheDocument();
  });

  it("E2: picking a contact → PATCH updateSignal('blockers', id, {contact: <uuid>})", async () => {
    renderEdit();
    fireEvent.click(screen.getByRole("button", { name: "pick" }));
    await save();
    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [type, id, patch] = updateSignal.mock.calls[0];
    expect(type).toBe("blockers");
    expect(id).toBe("objection-1");
    expect(patch.contact).toBe("c-picked");
  });

  it("E3: the picker is scoped to the activity's account — filters={{ account_id }}", () => {
    renderEdit();
    expect(JSON.parse(screen.getByTestId("objection-contact-select").dataset.filters)).toEqual({
      account_id: "acc-1",
    });
  });

  it("E4: clearing the contact → payload contact null", async () => {
    renderEdit();
    fireEvent.click(screen.getByRole("button", { name: "clear" }));
    await save();
    expect(updateSignal).toHaveBeenCalledTimes(1);
    expect(updateSignal.mock.calls[0][2]).toHaveProperty("contact", null);
  });

  it("E5: summary + source_quote edits are in the payload {summary, contact, source_quote} only", async () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-summary"));
    fireEvent.change(screen.getByTestId("inline-input-summary"), {
      target: { value: "No budget before the next fiscal year" },
    });
    fireEvent.doubleClick(screen.getByTestId("inline-read-source_quote"));
    fireEvent.change(screen.getByTestId("inline-input-source_quote"), {
      target: { value: "Nothing gets signed before April." },
    });
    await save();
    expect(updateSignal.mock.calls[0][2]).toEqual({
      summary: "No budget before the next fiscal year",
      contact: "c-orig",
      source_quote: "Nothing gets signed before April.",
    });
  });

  it("E5: summary < 10 characters → Save disabled, no PATCH", async () => {
    renderEdit();
    fireEvent.doubleClick(screen.getByTestId("inline-read-summary"));
    fireEvent.change(screen.getByTestId("inline-input-summary"), { target: { value: "Too short" } });
    // Validation is async (Yup) — let it settle.
    await act(async () => {});
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
    await save();
    expect(updateSignal).not.toHaveBeenCalled();
  });

  it("Save returns to the detail — onSaved gets the rebuilt signal with a COMPACT contact", async () => {
    const onSaved = vi.fn();
    renderEdit(OBJECTION, { onSaved });
    fireEvent.click(screen.getByRole("button", { name: "pick" }));
    await save();
    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(onSaved.mock.calls[0][0]).toMatchObject({ id: "objection-1", summary: OBJECTION.summary });
    expect(onSaved.mock.calls[0][0].contact).toEqual({
      id: "c-picked",
      first_name: "Paul",
      last_name: "Picked",
      job_title: "CTO",
    });
    expect(closeDrawer).not.toHaveBeenCalled();
  });
});
