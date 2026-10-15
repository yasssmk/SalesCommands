// frontend/src/__tests__/sections/activities/workspace/EditObjectionContent.contact.test.jsx
//
// Step 3b — Objection §2 contact on the click-to-edit pattern, through the REAL
// AsyncContactSelect (only its data hook is mocked): read = contact name → one
// click → focused search + open list → a choice returns to read; one Escape
// restores.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act, waitFor } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

// ---- mocks (before importing the component) ----
vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
}));
const ORIG = { id: "c-orig", first_name: "Sophie", last_name: "Martin", job_title: "CFO" };
const PICKED = { id: "c-picked", first_name: "Paul", last_name: "Picked", job_title: "CTO" };
vi.mock("api/businessData/contacts", () => ({
  useGetContacts: vi.fn(() => ({ contacts: [ORIG, PICKED], contactsLoading: false })),
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ closeDrawer: vi.fn(), openDrawer: vi.fn() }),
}));

import EditObjectionContent from "sections/activities/workspace/EditObjectionContent";
import { updateSignal } from "api/signals/signals";

const OBJECTION = {
  id: "objection-1",
  status: "PENDING",
  summary: "Budget frozen until Q2 for every new tool",
  contact: ORIG,
  source_quote: "Our budget is completely frozen",
};

const renderEdit = () =>
  render(
    <AphoriqTheme>
      <EditObjectionContent objection={OBJECTION} accountId="acc-1" />
    </AphoriqTheme>,
  );

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("EditObjectionContent — contact on the click-to-edit pattern (real AsyncContactSelect)", () => {
  it("no search field at render; the read row shows the contact name", () => {
    renderEdit();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByTestId("inline-read-contact")).toHaveTextContent("Sophie Martin");
  });

  it("one click → the search input is focused and the list is open", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-contact"));
    await waitFor(() => expect(screen.getByRole("combobox")).toHaveFocus());
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });

  it("a choice returns to READ with the new name; Save sends contact = its id", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-contact"));
    fireEvent.click(await screen.findByRole("option", { name: /Paul Picked/ }));
    await waitFor(() => expect(screen.queryByRole("combobox")).not.toBeInTheDocument());
    expect(screen.getByTestId("inline-read-contact")).toHaveTextContent("Paul Picked");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal.mock.calls[0][2].contact).toBe("c-picked");
  });

  it("ONE Escape with the list open → READ with the original contact", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-contact"));
    await screen.findByRole("listbox");
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("combobox")).not.toBeInTheDocument());
    expect(screen.getByTestId("inline-read-contact")).toHaveTextContent("Sophie Martin");
  });
});
