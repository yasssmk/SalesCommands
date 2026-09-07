// frontend/src/__tests__/components/signals/ObjectiveScopePill.test.jsx
//
// SIG-5b — the shared Objective "scope pill" (2 states: Company / Department).
// Draft-only: it derives the active state from `value.scope_level` and raises a
// scope patch via onChange; it never saves. PERSONAL is legacy: an objective
// already stored PERSONAL is shown read-only, never offered.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import AphoriqTheme from "../../_utils/aphoriqTheme";
import ObjectiveScopePill from "components/signals/ObjectiveScopePill";

const DEPTS = [
  { value: "d1", label: "Finance" },
  { value: "d2", label: "Marketing" },
];

const renderPill = (props) =>
  render(
    <AphoriqTheme>
      <ObjectiveScopePill departmentOptions={DEPTS} {...props} />
    </AphoriqTheme>,
  );

afterEach(() => cleanup());

describe("ObjectiveScopePill (SIG-5b)", () => {
  it("renders exactly two offered pills: Company and Department", () => {
    renderPill({ value: { scope_level: "BUSINESS" }, onChange: vi.fn() });
    expect(screen.getByTestId("scope-pill-BUSINESS")).toBeInTheDocument();
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toBeInTheDocument();
    expect(screen.getByText("Company")).toBeInTheDocument();
    expect(screen.getByText("Department")).toBeInTheDocument();
  });

  it("derives the active pill from scope_level = BUSINESS", () => {
    renderPill({ value: { scope_level: "BUSINESS" }, onChange: vi.fn() });
    expect(screen.getByTestId("scope-pill-BUSINESS")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveAttribute("aria-pressed", "false");
  });

  it("derives the active pill from scope_level = DEPARTMENT", () => {
    renderPill({
      value: { scope_level: "DEPARTMENT", target_department: "d1" },
      onChange: vi.fn(),
    });
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("scope-pill-BUSINESS")).toHaveAttribute("aria-pressed", "false");
  });

  it("empty scope_level defaults to Company (BUSINESS) active", () => {
    renderPill({ value: {}, onChange: vi.fn() });
    expect(screen.getByTestId("scope-pill-BUSINESS")).toHaveAttribute("aria-pressed", "true");
  });

  it("clicking Company raises the BUSINESS patch (clears the forbidden FKs)", () => {
    const onChange = vi.fn();
    renderPill({ value: { scope_level: "DEPARTMENT", target_department: "d1" }, onChange });
    fireEvent.click(screen.getByTestId("scope-pill-BUSINESS"));
    expect(onChange).toHaveBeenCalledWith({
      scope_level: "BUSINESS",
      target_department: null,
      target_contact: null,
    });
  });

  it("clicking Department raises the DEPARTMENT patch (clears target_contact)", () => {
    const onChange = vi.fn();
    renderPill({ value: { scope_level: "BUSINESS" }, onChange });
    fireEvent.click(screen.getByTestId("scope-pill-DEPARTMENT"));
    expect(onChange).toHaveBeenCalledWith({
      scope_level: "DEPARTMENT",
      target_contact: null,
    });
  });

  it("shows the department select ONLY when Department is active", () => {
    const { rerender } = renderPill({ value: { scope_level: "BUSINESS" }, onChange: vi.fn() });
    expect(screen.queryByTestId("scope-department-select")).not.toBeInTheDocument();

    rerender(
      <AphoriqTheme>
        <ObjectiveScopePill
          departmentOptions={DEPTS}
          value={{ scope_level: "DEPARTMENT", target_department: "d1" }}
          onChange={vi.fn()}
        />
      </AphoriqTheme>,
    );
    expect(screen.getByTestId("scope-department-select")).toBeInTheDocument();
  });

  it("choosing a department raises a target_department patch", () => {
    const onChange = vi.fn();
    renderPill({
      value: { scope_level: "DEPARTMENT", target_department: "d1" },
      onChange,
    });
    fireEvent.change(screen.getByTestId("scope-department-select"), {
      target: { value: "d2" },
    });
    expect(onChange).toHaveBeenCalledWith({ target_department: "d2" });
  });

  it("a legacy PERSONAL objective is shown read-only, not offered, without crashing", () => {
    renderPill({
      value: { scope_level: "PERSONAL", target_contact: { id: "c1" } },
      onChange: vi.fn(),
    });
    // Neither offered pill is active…
    expect(screen.getByTestId("scope-pill-BUSINESS")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("scope-pill-DEPARTMENT")).toHaveAttribute("aria-pressed", "false");
    // …and the legacy Personal state is surfaced (read-only).
    expect(screen.getByTestId("scope-pill-PERSONAL")).toBeInTheDocument();
    expect(screen.getByText("Personal")).toBeInTheDocument();
  });
});
