// frontend/src/__tests__/components/workspaceDrawer.unsavedGuard.test.jsx
//
// Sprint « Source / Notes » 2.2 — the « unsaved changes » guard of the single
// workspace coque (WorkspaceDrawerContext). A drawer content that is MODIFIED
// (DrawerContentLayout `dirty`) is never lost silently: replacing it
// (openDrawer), closing it (closeDrawer, the coque's ×) or opening the left
// menu asks the shared ConfirmDialog first — « Keep editing » keeps the
// content as typed, « Discard » applies the action. A pristine content, the
// content's own Cancel and a save in progress are never intercepted.
// beforeunload is prevented while any source is modified.
// Real provider, real coque (WorkspaceDrawer), real DrawerContentLayout.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act, waitFor } from "@testing-library/react";
import { useState } from "react";

vi.mock("@mui/material/useMediaQuery", () => ({ default: vi.fn(() => false) }));
vi.mock("@mui/x-date-pickers/DatePicker", () => ({ DatePicker: () => <input /> }));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));

const { completeActivity } = vi.hoisted(() => ({
  completeActivity: vi.fn(() => Promise.resolve({ success: true, data: {} })),
}));
vi.mock("api/accounts/activities", async (orig) => ({
  ...(await orig()),
  completeActivity: (...a) => completeActivity(...a),
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

import WorkspaceCoque from "../_utils/workspaceCoque";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { useMenuState } from "hooks/useMenuState";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import OutcomeDrawerContent from "sections/activities/workspace/OutcomeDrawerContent";
import ResolutionFlow from "components/flows/ResolutionFlow";

// A resolution flow (the next step / People chassis) whose caller holds a
// choice: `bar.dirty` (2.2) reaches the guard through the chassis.
function FlowContent({ dirty }) {
  const bar = { onSave: () => {}, onCancel: () => {}, saveLabel: "Next", dirty };
  return (
    <ResolutionFlow steps={[{ key: "a", label: "Resolution" }]} activeStep={0} bar={bar} testId="flow">
      <span>choose…</span>
    </ResolutionFlow>
  );
}

// An edit content on the real layout: modified once something is typed.
function FormContent() {
  const { closeDrawer } = useWorkspaceDrawer();
  const [value, setValue] = useState("");
  return (
    <DrawerContentLayout onSave={() => {}} onCancel={closeDrawer} dirty={value !== ""}>
      <input aria-label="draft" value={value} onChange={(e) => setValue(e.target.value)} />
    </DrawerContentLayout>
  );
}

// Save either MOVES ON (opens another content itself — a flow's forward step,
// a successful save) or FAILS (stays, shows an error: a re-render).
function SavingContent({ succeeds }) {
  const { openDrawer } = useWorkspaceDrawer();
  const [value, setValue] = useState("");
  const [error, setError] = useState(null);
  const save = () =>
    succeeds ? openDrawer(<div data-testid="next">next content</div>) : setError("refused");
  return (
    <DrawerContentLayout onSave={save} onCancel={() => {}} dirty={value !== ""}>
      <input aria-label="draft" value={value} onChange={(e) => setValue(e.target.value)} />
      {error && <span>{error}</span>}
    </DrawerContentLayout>
  );
}

function Trigger() {
  const { openDrawer, closeDrawer } = useWorkspaceDrawer();
  const { menuMaster, handlerDrawerOpen } = useMenuState();
  return (
    <div>
      <span data-testid="menu-state">{menuMaster?.isDashboardDrawerOpened ? "open" : "closed"}</span>
      <button onClick={() => openDrawer(<FormContent />, { title: "Edit" })}>open-form</button>
      <button onClick={() => openDrawer(<div data-testid="other">other content</div>)}>open-other</button>
      <button
        onClick={() => openDrawer(<OutcomeDrawerContent activity={{ id: "act-1", activity_type: "CALL" }} />)}
      >
        open-outcome
      </button>
      <button onClick={() => openDrawer(<SavingContent succeeds />)}>open-saving-ok</button>
      <button onClick={() => openDrawer(<SavingContent succeeds={false} />)}>open-saving-ko</button>
      <button onClick={() => openDrawer(<FlowContent dirty />)}>open-flow-dirty</button>
      <button onClick={() => openDrawer(<FlowContent dirty={false} />)}>open-flow-clean</button>
      <button onClick={() => closeDrawer()}>close</button>
      <button onClick={() => handlerDrawerOpen(true)}>open-menu</button>
    </div>
  );
}

const renderWorkspace = () => render(<Trigger />, { wrapper: WorkspaceCoque });
const type = (text) => fireEvent.change(screen.getByLabelText("draft"), { target: { value: text } });
const dialog = () => screen.queryByTestId("confirm-dialog");

beforeEach(() => {
  try { localStorage.clear(); } catch { /* ignore */ }
  completeActivity.mockClear();
});
afterEach(() => cleanup());

describe("unsaved changes guard — drawer content", () => {
  it("replacing a MODIFIED content asks first; « Keep editing » keeps what was typed", async () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-form"));
    type("half-written");
    fireEvent.click(screen.getByText("open-other"));

    expect(dialog()).toHaveTextContent("Discard your changes?");
    expect(screen.queryByTestId("other")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));

    await waitFor(() => expect(dialog()).toBeNull());
    expect(screen.getByLabelText("draft")).toHaveValue("half-written");
    expect(screen.queryByTestId("other")).toBeNull();
  });

  it("« Discard » applies the replacement", async () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-form"));
    type("half-written");
    fireEvent.click(screen.getByText("open-other"));
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));

    expect(await screen.findByTestId("other")).toBeInTheDocument();
    expect(screen.queryByLabelText("draft")).toBeNull();
  });

  it("closing a MODIFIED content (closeDrawer, the coque's ×) asks first", async () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-form"));
    type("x");
    fireEvent.click(screen.getByText("close"));
    expect(dialog()).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    await waitFor(() => expect(dialog()).toBeNull());

    fireEvent.click(screen.getByRole("button", { name: "Close drawer" }));
    expect(dialog()).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    await waitFor(() => expect(screen.queryByLabelText("draft")).toBeNull());
  });

  it("opening the menu over a MODIFIED content asks first; « Keep editing » re-folds the menu", async () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-form"));
    type("x");
    fireEvent.click(screen.getByText("open-menu"));

    expect(dialog()).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    await waitFor(() => expect(screen.getByTestId("menu-state")).toHaveTextContent("closed"));
    expect(screen.getByLabelText("draft")).toHaveValue("x");

    fireEvent.click(screen.getByText("open-menu"));
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    await waitFor(() => expect(screen.queryByLabelText("draft")).toBeNull());
    expect(screen.getByTestId("menu-state")).toHaveTextContent("open");
  });

  it("a PRISTINE content is replaced and closed without asking", () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-form"));
    fireEvent.click(screen.getByText("open-other"));
    expect(dialog()).toBeNull();
    expect(screen.getByTestId("other")).toBeInTheDocument();
  });

  it("the content's own Cancel is a deliberate discard: no confirmation", async () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-form"));
    type("x");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(dialog()).toBeNull();
    await waitFor(() => expect(screen.queryByLabelText("draft")).toBeNull());
  });
});

describe("unsaved changes guard — the content's own Save", () => {
  it("a Save that moves on (opens the next content itself) is not intercepted", async () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-saving-ok"));
    type("x");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(dialog()).toBeNull();
    expect(await screen.findByTestId("next")).toBeInTheDocument();
  });

  it("a FAILED Save keeps the guard: the content is still protected", async () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-saving-ko"));
    type("x");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("refused")).toBeInTheDocument();
    fireEvent.click(screen.getByText("open-other"));
    expect(dialog()).toBeInTheDocument();
  });
});

describe("unsaved changes guard — the resolution flows (bar.dirty)", () => {
  it("a flow holding a choice asks before being replaced", () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-flow-dirty"));
    fireEvent.click(screen.getByText("open-other"));
    expect(dialog()).toBeInTheDocument();
  });

  it("a flow with no choice is replaced without asking", () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-flow-clean"));
    fireEvent.click(screen.getByText("open-other"));
    expect(dialog()).toBeNull();
    expect(screen.getByTestId("other")).toBeInTheDocument();
  });
});

describe("unsaved changes guard — a real drawer (OutcomeDrawerContent)", () => {
  it("a picked outcome is a modification: replacing the drawer asks first", () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-outcome"));
    fireEvent.click(screen.getByTestId("outcome-pill-SUCCESSFUL"));
    fireEvent.click(screen.getByText("open-other"));
    expect(dialog()).toBeInTheDocument();
  });

  it("a successful save closes the drawer without asking", async () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-outcome"));
    fireEvent.click(screen.getByTestId("outcome-pill-SUCCESSFUL"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /^complete$/i }));
    });
    await waitFor(() => expect(completeActivity).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.queryByTestId("outcome-pill-SUCCESSFUL")).toBeNull());
    expect(dialog()).toBeNull();
  });
});

describe("unsaved changes guard — beforeunload", () => {
  const fireBeforeUnload = () => {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event;
  };

  it("is prevented while a source is modified", () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-form"));
    type("x");
    expect(fireBeforeUnload().defaultPrevented).toBe(true);
  });

  it("is left alone when nothing is modified", () => {
    renderWorkspace();
    fireEvent.click(screen.getByText("open-form"));
    expect(fireBeforeUnload().defaultPrevented).toBe(false);
  });
});
