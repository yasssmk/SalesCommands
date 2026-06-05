// frontend/src/__tests__/signals/SignalsViewToggle.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import SignalsViewToggle, {
  getPersistedView,
} from "sections/activities/signals/SignalsViewToggle";

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
});

afterEach(() => {
  cleanup();
});

describe("SignalsViewToggle", () => {
  it("renders Grouped and Flat buttons", () => {
    render(
      <SignalsViewToggle view="grouped" onChange={vi.fn()} activityId="a1" />,
    );

    expect(screen.getByRole("button", { name: /grouped/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /flat/i })).toBeInTheDocument();
  });

  it("calls onChange with new view on toggle click", () => {
    const onChange = vi.fn();
    render(
      <SignalsViewToggle view="grouped" onChange={onChange} activityId="a1" />,
    );

    fireEvent.click(screen.getByRole("button", { name: /flat/i }));
    expect(onChange).toHaveBeenCalledWith("flat");
  });

  it("persists view to sessionStorage", () => {
    const onChange = vi.fn();
    render(
      <SignalsViewToggle view="grouped" onChange={onChange} activityId="a1" />,
    );

    fireEvent.click(screen.getByRole("button", { name: /flat/i }));
    expect(sessionStorage.getItem("signals_view_a1")).toBe("flat");
  });

  it("does not call onChange when clicking already-selected view", () => {
    const onChange = vi.fn();
    render(
      <SignalsViewToggle view="grouped" onChange={onChange} activityId="a1" />,
    );

    fireEvent.click(screen.getByRole("button", { name: /grouped/i }));
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("getPersistedView", () => {
  it("returns 'grouped' by default", () => {
    expect(getPersistedView("a1")).toBe("grouped");
  });

  it("returns stored value", () => {
    sessionStorage.setItem("signals_view_a1", "flat");
    expect(getPersistedView("a1")).toBe("flat");
  });

  it("returns 'grouped' for invalid stored value", () => {
    sessionStorage.setItem("signals_view_a1", "invalid");
    expect(getPersistedView("a1")).toBe("grouped");
  });

  it("returns 'grouped' when activityId is null", () => {
    expect(getPersistedView(null)).toBe("grouped");
  });
});
