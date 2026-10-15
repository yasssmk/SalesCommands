// frontend/src/__tests__/sections/activities/workspace/EditPeopleContent.contact.test.jsx
//
// Step 3b — People §1 contact on the click-to-edit pattern, through the REAL
// AsyncContactSelect (only its data hook is mocked): read = contact name → one
// click → focused search + open list → a choice returns to read; one Escape
// restores; unlinking keeps the cited name.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act, waitFor } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

// ---- mocks (before importing the component) ----
vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
  useGetSignalChoices: vi.fn(() => ({
    choices: {
      people_roles: [{ value: "ECONOMIC_BUYER", label: "Economic Buyer" }],
      people_influences: [{ value: "HIGH", label: "High" }],
    },
    choicesLoading: false,
  })),
}));
const ORIG = { id: "c-orig", first_name: "Sophie", last_name: "Martin", job_title: "CFO" };
const PICKED = { id: "c-picked", first_name: "Paul", last_name: "Picked", job_title: "CTO" };
vi.mock("api/businessData/contacts", () => ({
  useGetContactChoices: vi.fn(() => ({ standardDepartments: [{ value: 1, label: "Finance" }] })),
  useGetContacts: vi.fn(() => ({ contacts: [ORIG, PICKED], contactsLoading: false })),
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ closeDrawer: vi.fn(), openDrawer: vi.fn() }),
}));

import EditPeopleContent from "sections/activities/workspace/EditPeopleContent";
import { updateSignal } from "api/signals/signals";

const PEOPLE = {
  id: "people-1",
  status: "PENDING",
  role: "ECONOMIC_BUYER",
  role_display: "Economic Buyer",
  influence: "HIGH",
  influence_display: "High",
  full_name: "Sophie Martin",
  target_contact: ORIG,
  target_department: { id: "1", name: "Finance" },
  notes: "Signs off every budget line.",
  source_quote: "Sophie will have the final word.",
};

const renderEdit = () =>
  render(
    <AphoriqTheme>
      <EditPeopleContent people={PEOPLE} accountId="acc-1" />
    </AphoriqTheme>,
  );

const save = async () => {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
  });
};

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("EditPeopleContent — contact on the click-to-edit pattern (real AsyncContactSelect)", () => {
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

  it("a choice returns to READ with the new name; Save sends target_contact = its id", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-contact"));
    fireEvent.click(await screen.findByRole("option", { name: /Paul Picked/ }));
    await waitFor(() => expect(screen.queryByRole("combobox")).not.toBeInTheDocument());
    expect(screen.getByTestId("inline-read-contact")).toHaveTextContent("Paul Picked");
    await save();
    expect(updateSignal.mock.calls[0][2].target_contact).toBe("c-picked");
  });

  it("ONE Escape with the list open → READ with the original contact", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-contact"));
    await screen.findByRole("listbox");
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("combobox")).not.toBeInTheDocument());
    expect(screen.getByTestId("inline-read-contact")).toHaveTextContent("Sophie Martin");
  });

  it("click outside (focus leaves) → READ, contact unchanged", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-contact"));
    await screen.findByRole("listbox");
    fireEvent.blur(screen.getByRole("combobox"));
    await waitFor(() => expect(screen.queryByRole("combobox")).not.toBeInTheDocument());
    expect(screen.getByTestId("inline-read-contact")).toHaveTextContent("Sophie Martin");
  });

  it("unlinking (Clear) keeps the cited name → payload target_contact null, no identity warning", async () => {
    renderEdit();
    fireEvent.click(screen.getByTestId("inline-read-contact"));
    fireEvent.click(await screen.findByRole("button", { name: "Clear" }));
    await waitFor(() => expect(screen.queryByRole("combobox")).not.toBeInTheDocument());
    expect(screen.getByTestId("inline-read-contact")).not.toHaveTextContent("Sophie Martin");
    expect(screen.queryByTestId("people-identity-warning")).not.toBeInTheDocument();
    await save();
    const patch = updateSignal.mock.calls[0][2];
    expect(patch.target_contact).toBeNull();
    expect(patch.full_name).toBe("Sophie Martin");
  });
});
