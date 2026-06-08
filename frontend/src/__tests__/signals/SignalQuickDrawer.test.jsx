// frontend/src/__tests__/signals/SignalQuickDrawer.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import SignalQuickDrawer from "sections/activities/signals/SignalQuickDrawer";

afterEach(() => {
  cleanup();
});

const MOCK_SIGNAL = {
  id: "s1",
  status: "PENDING",
  summary: "Lost 5h/week on consolidation",
  what: "DATA",
  dimension: "TIME",
  source_quote: "We lose about 5 hours per week just consolidating reports",
  what_display: "Data",
  dimension_display: "Time",
  created_at: "2026-05-12T14:32:00Z",
  source: "LLM_EXTRACTED",
  contact: null,
  source_context: {
    contacts: [{ id: "c1", first_name: "Pierre", last_name: "Dupont" }],
  },
};

describe("SignalQuickDrawer", () => {
  it("renders signal details when open", () => {
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_SIGNAL}
        signalType="pain"
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Pain")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText(/Lost 5h\/week/)).toBeInTheDocument();
    expect(screen.getByText(/We lose about 5 hours/)).toBeInTheDocument();
    expect(screen.getByText("Data × Time")).toBeInTheDocument();
    expect(screen.getByText("Pierre Dupont")).toBeInTheDocument();
  });

  it("shows Validate, Reject, Edit buttons for PENDING signal", () => {
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_SIGNAL}
        signalType="pain"
        onClose={vi.fn()}
        onValidate={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /validate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
  });

  it("hides Validate/Reject for VALIDATED signal", () => {
    const validated = { ...MOCK_SIGNAL, status: "VALIDATED" };
    render(
      <SignalQuickDrawer
        open={true}
        signal={validated}
        signalType="pain"
        onClose={vi.fn()}
        onEdit={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
  });

  it("hides all action buttons when locked", () => {
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_SIGNAL}
        signalType="pain"
        onClose={vi.fn()}
        isLocked
      />,
    );

    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
  });

  it("calls onValidate on Validate click", () => {
    const onValidate = vi.fn();
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_SIGNAL}
        signalType="pain"
        onClose={vi.fn()}
        onValidate={onValidate}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /validate/i }));
    expect(onValidate).toHaveBeenCalledWith(MOCK_SIGNAL, "pain");
  });

  it("calls onReject on Reject click", () => {
    const onReject = vi.fn();
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_SIGNAL}
        signalType="pain"
        onClose={vi.fn()}
        onReject={onReject}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(onReject).toHaveBeenCalledWith(MOCK_SIGNAL, "pain");
  });

  it("calls onEdit on Edit click", () => {
    const onEdit = vi.fn();
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_SIGNAL}
        signalType="pain"
        onClose={vi.fn()}
        onEdit={onEdit}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    expect(onEdit).toHaveBeenCalledWith(MOCK_SIGNAL, "pain");
  });

  it("calls onClose on close button click", () => {
    const onClose = vi.fn();
    render(
      <SignalQuickDrawer
        open={true}
        signal={MOCK_SIGNAL}
        signalType="pain"
        onClose={onClose}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /close drawer/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it("hides contact line when no contact available", () => {
    const noContact = {
      ...MOCK_SIGNAL,
      contact: null,
      source_context: { contacts: [] },
    };
    render(
      <SignalQuickDrawer
        open={true}
        signal={noContact}
        signalType="pain"
        onClose={vi.fn()}
      />,
    );

    expect(screen.queryByText("No contact attributed")).not.toBeInTheDocument();
    expect(screen.queryByText("Pierre Dupont")).not.toBeInTheDocument();
  });

  it("renders blocker contact directly from signal.contact", () => {
    const blocker = {
      id: "b1",
      status: "PENDING",
      summary: "Budget frozen",
      contact: { id: "c2", first_name: "Sophie", last_name: "Martin" },
    };
    render(
      <SignalQuickDrawer
        open={true}
        signal={blocker}
        signalType="blockers"
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Sophie Martin")).toBeInTheDocument();
  });

  it("returns null when signal is null", () => {
    const { container } = render(
      <SignalQuickDrawer
        open={true}
        signal={null}
        signalType="pain"
        onClose={vi.fn()}
      />,
    );

    expect(container.firstChild).toBeNull();
  });
});
