// frontend/src/__tests__/contexts/breadcrumb.test.jsx
//
// UX Activity L0 — contextual breadcrumb mechanism (socle).
//
// Proves the missing mechanism the audit flagged:
//   - a page pushes its trail via setCrumbs([...]) → the layout bar renders the
//     segments (href segment = clickable link; last segment = current page, no
//     link);
//   - setCrumbs([]) → the bar stays PRESENT (constant-height anchor) but renders
//     no segments;
//   - the pushing consumer and the bar share ONE provider (no two-instances
//     trap): the push reaches the same provider the bar reads.

import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import AphoriqTheme from "../_utils/aphoriqTheme";

// BreadcrumbBar reads next/navigation useRouter for clickable segments.
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { BreadcrumbProvider, useBreadcrumb } from "contexts/BreadcrumbContext";
import BreadcrumbBar from "components/BreadcrumbBar";

// A child (inside the provider) standing in for a page that declares its trail.
function Pusher() {
  const { setCrumbs } = useBreadcrumb();
  return (
    <div>
      <button
        onClick={() =>
          setCrumbs([
            { label: "ATHENA", href: "/accounts/1" },
            { label: "New test" },
          ])
        }
      >
        push
      </button>
      <button onClick={() => setCrumbs([])}>clear</button>
    </div>
  );
}

function renderBar() {
  return render(
    <AphoriqTheme>
      <BreadcrumbProvider>
        <BreadcrumbBar />
        <Pusher />
      </BreadcrumbProvider>
    </AphoriqTheme>,
  );
}

afterEach(() => cleanup());

describe("Breadcrumb mechanism (L0)", () => {
  it("bar is always present (constant-height anchor), empty by default", () => {
    renderBar();
    expect(screen.getByTestId("breadcrumb-bar")).toBeInTheDocument();
    expect(screen.queryByText("ATHENA")).not.toBeInTheDocument();
  });

  it("a page pushing a trail via setCrumbs renders the segments in the bar", () => {
    renderBar();
    fireEvent.click(screen.getByRole("button", { name: "push" }));

    expect(screen.getByText("ATHENA")).toBeInTheDocument();
    expect(screen.getByText("New test")).toBeInTheDocument();
    // href segment is a clickable link; the last (no href) is the current page.
    expect(screen.getByText("ATHENA").closest("a")).not.toBeNull();
    expect(screen.getByText("New test").closest("a")).toBeNull();
  });

  it("setCrumbs([]) keeps the bar present but clears the segments (height reserved)", () => {
    renderBar();
    fireEvent.click(screen.getByRole("button", { name: "push" }));
    expect(screen.getByText("ATHENA")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "clear" }));
    expect(screen.queryByText("ATHENA")).not.toBeInTheDocument();
    // bar still present → constant-height anchor kept even when empty
    expect(screen.getByTestId("breadcrumb-bar")).toBeInTheDocument();
  });
});
