// frontend/src/__tests__/sections/activities/workspace/UserDrawerContent.test.jsx
//
// CT-USER — the read-only fiche for an internal team member (activity owner /
// invited user). Symmetric to the Contact fiche but for the User model: name +
// platform Role + Team + Email (coordinates), all in the shared two-column
// CoordinateRow with "No …" placeholders when empty. PURE READ — no edit pencil
// (user edit is admin-only elsewhere), no "N activities", no DC role, no "See
// signals" (an internal is not a deal decider).

import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ closeDrawer: vi.fn() }),
}));

const useGetUser = vi.fn();
vi.mock("api/admin/users", () => ({
  useGetUser: (...a) => useGetUser(...a),
}));

import ThemeCustomization from "themes/index";
import UserDrawerContent from "sections/activities/workspace/UserDrawerContent";

const USER = {
  id: "u1",
  first_name: "Admin",
  last_name: "Tenant A",
  full_name: "Admin Tenant A",
  email: "admin@test.com",
  role_name: "Manager",
  team_name: "Sales EMEA",
};

function mockUser(user = USER, extra = {}) {
  useGetUser.mockReturnValue({
    user,
    userLoading: false,
    userError: null,
    userValidating: false,
    ...extra,
  });
}

function renderFiche(props = {}) {
  return render(
    <ThemeCustomization>
      <UserDrawerContent userId="u1" {...props} />
    </ThemeCustomization>,
  );
}

beforeEach(() => useGetUser.mockReset());

describe("UserDrawerContent — identity + role + team + email", () => {
  it("renders name, and Role / Team / Email labels with their values", () => {
    mockUser();
    renderFiche();

    expect(screen.getByText("Admin Tenant A")).toBeInTheDocument();

    expect(screen.getByText("Role")).toBeInTheDocument();
    expect(screen.getByText("Manager")).toBeInTheDocument();

    expect(screen.getByText("Team")).toBeInTheDocument();
    expect(screen.getByText("Sales EMEA")).toBeInTheDocument();

    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /admin@test\.com/ })).toBeInTheDocument();
  });

  it("keeps all rows with 'No …' placeholders when values are empty", () => {
    mockUser({ ...USER, role_name: null, team_name: "", email: "" });
    renderFiche();

    expect(screen.getByText("Role")).toBeInTheDocument();
    expect(screen.getByText("Team")).toBeInTheDocument();
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByText("No role")).toBeInTheDocument();
    expect(screen.getByText("No team")).toBeInTheDocument();
    expect(screen.getByText("No email")).toBeInTheDocument();
  });
});

describe("UserDrawerContent — pure read (no actions, no deal blocks)", () => {
  it("shows NO edit pencil, NO activities, NO DC role, NO 'See signals', NO Save/Cancel bar", () => {
    mockUser();
    renderFiche();

    expect(screen.queryByTestId("contact-edit")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId("contact-activities")).not.toBeInTheDocument();
    expect(screen.queryByTestId("contact-role")).not.toBeInTheDocument();
    expect(screen.queryByTestId("contact-signals-link")).not.toBeInTheDocument();
    expect(screen.queryByText(/See signals/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId("drawer-actions")).not.toBeInTheDocument();
  });
});

describe("UserDrawerContent — loading / error", () => {
  it("shows a discreet loader while the user loads (no crash)", () => {
    useGetUser.mockReturnValue({ user: null, userLoading: true, userError: null });
    renderFiche();
    expect(screen.getByTestId("user-loading")).toBeInTheDocument();
  });

  it("shows a discreet error message when the user cannot be loaded", () => {
    useGetUser.mockReturnValue({ user: null, userLoading: false, userError: new Error("x") });
    renderFiche();
    expect(screen.getByText(/could not be loaded/i)).toBeInTheDocument();
  });
});
