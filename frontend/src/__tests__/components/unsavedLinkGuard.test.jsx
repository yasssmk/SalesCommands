// frontend/src/__tests__/components/unsavedLinkGuard.test.jsx
//
// Sprint « Source / Notes » 2.3 — while a source is MODIFIED (a drawer
// content OR a page field), a click on an INTERNAL link (breadcrumb, menu,
// page link) is intercepted in the capture phase: the shared ConfirmDialog
// asks (same labels as 2.2); « Keep editing » → no navigation, « Discard » →
// router.push to the link. Not intercepted: nothing modified, an external
// link, a new tab (ctrl / cmd / middle click, target=_blank), a link without a
// route change. The browser Back button is NOT covered (documented).
// Real provider, real coque, real UnsavedLinkGuard; each link carries its own
// React onClick standing for Next's <Link> handler — it records whether the
// click reached the app (i.e. was NOT intercepted).

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import { useState } from "react";

vi.mock("@mui/material/useMediaQuery", () => ({ default: vi.fn(() => false) }));
const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/activities/act-1",
}));

import WorkspaceCoque from "../_utils/workspaceCoque";
import UnsavedLinkGuard from "components/drawer/UnsavedLinkGuard";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import useUnsavedChanges from "hooks/useUnsavedChanges";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import { UNSAVED_SCOPE } from "utils/unsavedChanges";

const reached = vi.fn();
// Stands for Next's <Link>: its own handler prevents the native navigation
// and records that the click reached the app.
const AppLink = ({ href, children, ...rest }) => (
  <a
    href={href}
    onClick={(e) => {
      e.preventDefault();
      reached(href);
    }}
    {...rest}
  >
    {children}
  </a>
);

// A page field (the Source band's notes, 2.4) holding unsaved text.
function PageField() {
  const [value, setValue] = useState("");
  useUnsavedChanges(value !== "", { scope: UNSAVED_SCOPE.PAGE });
  return <input aria-label="page-draft" value={value} onChange={(e) => setValue(e.target.value)} />;
}

function DrawerForm() {
  const [value, setValue] = useState("");
  return (
    <DrawerContentLayout onSave={() => {}} onCancel={() => {}} dirty={value !== ""}>
      <input aria-label="drawer-draft" value={value} onChange={(e) => setValue(e.target.value)} />
    </DrawerContentLayout>
  );
}

function Page() {
  const { openDrawer } = useWorkspaceDrawer();
  return (
    <div>
      <UnsavedLinkGuard />
      <PageField />
      <button onClick={() => openDrawer(<DrawerForm />)}>open-form</button>
      <AppLink href="/accounts/acc-1?tab=signals">Account</AppLink>
      <AppLink href="https://example.com/doc">External</AppLink>
      <AppLink href="/accounts/acc-2" target="_blank">New tab</AppLink>
      <AppLink href="/activities/act-1#notes">Same route</AppLink>
    </div>
  );
}

const renderPage = () => render(<Page />, { wrapper: WorkspaceCoque });
const dialog = () => screen.queryByTestId("confirm-dialog");
const typePage = () => fireEvent.change(screen.getByLabelText("page-draft"), { target: { value: "notes…" } });

beforeEach(() => {
  push.mockClear();
  reached.mockClear();
  window.history.replaceState({}, "", "/activities/act-1");
});
afterEach(() => cleanup());

describe("internal links while a source is modified", () => {
  it("a page field modified: the link asks; « Keep editing » does not navigate", async () => {
    renderPage();
    typePage();
    fireEvent.click(screen.getByText("Account"));

    expect(dialog()).toHaveTextContent("Discard your changes?");
    expect(reached).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    await waitFor(() => expect(dialog()).toBeNull());
    expect(push).not.toHaveBeenCalled();
    expect(screen.getByLabelText("page-draft")).toHaveValue("notes…");
  });

  it("« Discard » navigates with router.push to the link (path + query)", async () => {
    renderPage();
    typePage();
    fireEvent.click(screen.getByText("Account"));
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/accounts/acc-1?tab=signals"));
    expect(reached).not.toHaveBeenCalled();
  });

  it("a drawer content modified: the link asks too", () => {
    renderPage();
    fireEvent.click(screen.getByText("open-form"));
    fireEvent.change(screen.getByLabelText("drawer-draft"), { target: { value: "x" } });
    fireEvent.click(screen.getByText("Account"));
    expect(dialog()).toBeInTheDocument();
    expect(reached).not.toHaveBeenCalled();
  });
});

describe("links NOT intercepted", () => {
  it("nothing modified: the link navigates directly", () => {
    renderPage();
    fireEvent.click(screen.getByText("Account"));
    expect(dialog()).toBeNull();
    expect(reached).toHaveBeenCalledWith("/accounts/acc-1?tab=signals");
  });

  it.each([
    ["ctrl-click", { ctrlKey: true }],
    ["cmd-click", { metaKey: true }],
    ["shift-click", { shiftKey: true }],
    ["middle click", { button: 1 }],
  ])("a %s (new tab / window) is left alone", (_label, init) => {
    renderPage();
    typePage();
    fireEvent.click(screen.getByText("Account"), init);
    expect(dialog()).toBeNull();
    expect(reached).toHaveBeenCalled();
  });

  it("an external link is left alone", () => {
    renderPage();
    typePage();
    fireEvent.click(screen.getByText("External"));
    expect(dialog()).toBeNull();
    expect(reached).toHaveBeenCalledWith("https://example.com/doc");
  });

  it("a target=_blank link is left alone", () => {
    renderPage();
    typePage();
    fireEvent.click(screen.getByText("New tab"));
    expect(dialog()).toBeNull();
    expect(reached).toHaveBeenCalled();
  });

  it("a link without a route change (same path, a hash) is left alone", () => {
    renderPage();
    typePage();
    fireEvent.click(screen.getByText("Same route"));
    expect(dialog()).toBeNull();
    expect(reached).toHaveBeenCalled();
  });
});
