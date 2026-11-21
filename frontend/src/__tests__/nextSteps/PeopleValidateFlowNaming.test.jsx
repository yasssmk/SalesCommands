// frontend/src/__tests__/nextSteps/PeopleValidateFlowNaming.test.jsx
//
// Sprint « Deal health v2 », sub-step 5d — validating a NAMED People signal
// by linking it to a stakeholder WITHOUT a name of its own (no full_name, no
// contact): a checkbox, CHECKED by default, offers to give that stakeholder
// the signal's name (PO: « information completes itself when it does not
// contradict »). Confirm sends the flag; the server keeps the guard.
// Everywhere else — a named stakeholder, a stakeholder linked to a contact,
// a signal without a name — no checkbox, no flag (the payload is unchanged).
//
// The REAL PeopleValidateFlow, rendered in the workspace coque harness (the
// harness of PeopleValidatePage.test.jsx); only the API layer is mocked.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within, waitFor } from "@testing-library/react";
import WorkspaceCoque from "../_utils/workspaceCoque";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("hooks/useAuth", () => ({ useAuth: () => ({ tenantId: "t-1" }) }));
vi.mock("api/businessData/contacts", () => ({
  useGetContactChoices: () => ({ standardDepartments: [] }),
}));
vi.mock("utils/displayError", () => ({ displayErrorSnackbar: vi.fn() }));
let mockResolution = null;
vi.mock("api/signals/signals", () => ({
  usePeopleResolutionCandidates: vi.fn(() => mockResolution),
  resolvePeopleSignal: vi.fn(async () => ({ success: true, data: {} })),
}));

import PeopleValidateFlow, {
  PEOPLE_NAME_STAKEHOLDER_LABEL,
} from "sections/activities/workspace/PeopleValidateFlow";
import { resolvePeopleSignal } from "api/signals/signals";

const FINANCE = { id: "st-fin", full_name: "", contact: null,
  department: { id: 3, name: "Finance & Accounting" }, current_role_display: null, proposed: false };
const ELENA = { id: "st-elena", full_name: "Elena Rossi", contact: null, department: null,
  current_role_display: null, proposed: false };
const ANA = { id: "st-ana", full_name: "", contact: { id: "c-ana", first_name: "Ana", last_name: "Lopez" },
  department: null, current_role_display: null, proposed: false };

const PERSON = { id: "ps-1", full_name: "Colonel Mustard", target_department: null };

afterEach(() => { cleanup(); vi.clearAllMocks(); });

async function linkTo(signal, candidateLabel) {
  mockResolution = { hasCycle: true, stakeholders: [FINANCE, ELENA, ANA], contacts: [],
                     candidatesLoading: false };
  render(
    <WorkspaceCoque>
      <PeopleValidateFlow signal={signal} onBack={vi.fn()} onResolved={vi.fn()} />
    </WorkspaceCoque>,
  );
  const flow = await screen.findByTestId("people-validate-flow");
  fireEvent.click(within(flow).getByLabelText("Link to an existing stakeholder or contact"));
  fireEvent.click(within(flow).getByRole("button", { name: "Next" }));
  const list = await within(flow).findByTestId("people-candidates");
  fireEvent.click(within(list).getByLabelText(`Select ${candidateLabel}`));
  return flow;
}

const confirm = (flow) => fireEvent.click(within(flow).getByRole("button", { name: "Confirm" }));

describe("People validation — give a nameless stakeholder the signal's name", () => {
  it("offers it, checked by default, and sends the flag on Confirm", async () => {
    const flow = await linkTo(PERSON, "Finance & Accounting");

    const box = within(flow).getByLabelText(PEOPLE_NAME_STAKEHOLDER_LABEL("Colonel Mustard"));
    expect(box).toBeChecked();
    confirm(flow);
    await waitFor(() => expect(resolvePeopleSignal).toHaveBeenCalledWith(
      "ps-1", { stakeholder_id: "st-fin", name_stakeholder: true },
    ));
  });

  it("unchecked: the stakeholder is linked without the flag", async () => {
    const flow = await linkTo(PERSON, "Finance & Accounting");
    fireEvent.click(within(flow).getByLabelText(PEOPLE_NAME_STAKEHOLDER_LABEL("Colonel Mustard")));
    confirm(flow);
    await waitFor(() => expect(resolvePeopleSignal).toHaveBeenCalledWith(
      "ps-1", { stakeholder_id: "st-fin" },
    ));
  });

  it.each([
    ["a stakeholder already named", PERSON, "Elena Rossi", "st-elena"],
    ["a stakeholder linked to a contact", PERSON, "Ana Lopez", "st-ana"],
    ["a signal without a name", { ...PERSON, full_name: "" }, "Finance & Accounting", "st-fin"],
  ])("never offered for %s", async (_case, signal, label, id) => {
    const flow = await linkTo(signal, label);
    expect(within(flow).queryByRole("checkbox")).toBeNull();
    confirm(flow);
    await waitFor(() => expect(resolvePeopleSignal).toHaveBeenCalledWith("ps-1", { stakeholder_id: id }));
  });
});
