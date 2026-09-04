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

describe("UserDrawerContent — identity (name + role · team) + email-only coords", () => {
  it("shows the real name (full_name), role · team under it, and Email as the only coordinate", () => {
    mockUser();
    renderFiche();

    // name = full_name (NOT the email)
    const name = screen.getByTestId("user-name");
    expect(name).toHaveTextContent("Admin Tenant A");
    expect(name).not.toHaveTextContent("admin@test.com");

    // role · team live in the identity subtitle
    const subtitle = screen.getByTestId("user-subtitle");
    expect(subtitle).toHaveTextContent("Manager");
    expect(subtitle).toHaveTextContent("Sales EMEA");

    // coordinates = Email only
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /admin@test\.com/ })).toBeInTheDocument();
    // Role / Team are NOT coordinate rows anymore
    expect(screen.queryByText("Role")).not.toBeInTheDocument();
    expect(screen.queryByText("Team")).not.toBeInTheDocument();
  });

  it("uses `name` / `role` (auth-context user shape) when full_name/role_name are absent", () => {
    // The owner is often the logged-in user, so useGetUser returns the auth
    // context user, whose name is under `name` (get_full_name) and role under
    // `role` — not full_name / role_name. The fiche must read these too.
    mockUser({ id: "u1", name: "Admin Tenant A", email: "admin@test.com", role: "Manager" });
    renderFiche();
    const name = screen.getByTestId("user-name");
    expect(name).toHaveTextContent("Admin Tenant A");
    expect(name).not.toHaveTextContent("Unnamed member");
    expect(screen.getByTestId("user-subtitle")).toHaveTextContent("Manager");
  });

  it("never uses the email as the name (empty full_name → neutral placeholder)", () => {
    mockUser({ ...USER, full_name: "", first_name: "", last_name: "", email: "ghost@test.com" });
    renderFiche();
    const name = screen.getByTestId("user-name");
    expect(name).not.toHaveTextContent("ghost@test.com");
    // email still shows as the coordinate value
    expect(screen.getByRole("link", { name: /ghost@test\.com/ })).toBeInTheDocument();
  });

  it("shows 'No role' / 'No team' placeholders in the subtitle when empty", () => {
    mockUser({ ...USER, role_name: null, team_name: "" });
    renderFiche();
    const subtitle = screen.getByTestId("user-subtitle");
    expect(subtitle).toHaveTextContent(/No role/i);
    expect(subtitle).toHaveTextContent(/No team/i);
  });

  it("shows 'No email' in coords when the email is empty", () => {
    mockUser({ ...USER, email: "" });
    renderFiche();
    expect(screen.getByText("Email")).toBeInTheDocument();
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
