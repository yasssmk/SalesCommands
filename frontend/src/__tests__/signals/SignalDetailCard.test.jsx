// frontend/src/__tests__/signals/SignalDetailCard.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import SignalDetailCard from "components/cards/signals/SignalDetailCard";

afterEach(() => {
  cleanup();
});

const MOCK_PAIN = {
  id: "p1",
  status: "PENDING",
  summary: "Lost 5h/week on consolidation",
  what: "DATA",
  what_display: "Data",
  dimension: "TIME",
  dimension_display: "Time",
  source_quote: "We spend too much time consolidating data",
  created_at: "2025-06-01T10:00:00Z",
  source_context: {
    contact: { id: "c1", first_name: "Marie", last_name: "Curie" },
  },
};

describe("SignalDetailCard", () => {
  it("renders signal type and status chips", () => {
    render(
      <SignalDetailCard signal={MOCK_PAIN} signalType="pain" />,
    );

    expect(screen.getByText("Pain")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("renders theme chip when what_display and dimension_display present", () => {
    render(
      <SignalDetailCard signal={MOCK_PAIN} signalType="pain" />,
    );

    expect(screen.getByText("Data × Time")).toBeInTheDocument();
  });

  it("does not render theme chip when missing theme fields", () => {
    const signal = { ...MOCK_PAIN, what_display: null, dimension_display: null };
    render(
      <SignalDetailCard signal={signal} signalType="pain" />,
    );

    expect(screen.queryByText(/×/)).not.toBeInTheDocument();
  });

  it("renders summary", () => {
    render(
      <SignalDetailCard signal={MOCK_PAIN} signalType="pain" />,
    );

    expect(screen.getByText("Lost 5h/week on consolidation")).toBeInTheDocument();
  });

  it("renders source quote", () => {
    render(
      <SignalDetailCard signal={MOCK_PAIN} signalType="pain" />,
    );

    expect(
      screen.getByText(/We spend too much time consolidating data/),
    ).toBeInTheDocument();
  });

  it("renders contact name", () => {
    render(
      <SignalDetailCard signal={MOCK_PAIN} signalType="pain" />,
    );

    expect(screen.getByText("Marie Curie")).toBeInTheDocument();
  });

  it("renders 'No contact attributed' when no contact", () => {
    const signal = { ...MOCK_PAIN, source_context: {} };
    render(
      <SignalDetailCard signal={signal} signalType="pain" />,
    );

    expect(screen.getByText("No contact attributed")).toBeInTheDocument();
  });

  it("renders extraction date", () => {
    render(
      <SignalDetailCard signal={MOCK_PAIN} signalType="pain" />,
    );

    expect(screen.getByText(/Extracted:/)).toBeInTheDocument();
  });

  it("renders edit, reject, validate buttons for PENDING signal", () => {
    render(
      <SignalDetailCard
        signal={MOCK_PAIN}
        signalType="pain"
        onEdit={vi.fn()}
        onReject={vi.fn()}
        onValidate={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /validate/i })).toBeInTheDocument();
  });

  it("hides reject and validate buttons for VALIDATED signal", () => {
    const signal = { ...MOCK_PAIN, status: "VALIDATED" };
    render(
      <SignalDetailCard signal={signal} signalType="pain" onEdit={vi.fn()} />,
    );

    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /reject/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /validate/i }),
    ).not.toBeInTheDocument();
  });

  it("hides all action buttons when locked", () => {
    render(
      <SignalDetailCard signal={MOCK_PAIN} signalType="pain" isLocked />,
    );

    expect(
      screen.queryByRole("button", { name: /edit/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /validate/i }),
    ).not.toBeInTheDocument();
  });

  it("calls onEdit with signal and type", () => {
    const onEdit = vi.fn();
    render(
      <SignalDetailCard
        signal={MOCK_PAIN}
        signalType="pain"
        onEdit={onEdit}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    expect(onEdit).toHaveBeenCalledWith(MOCK_PAIN, "pain");
  });

  it("calls onValidate with signal and type", () => {
    const onValidate = vi.fn();
    render(
      <SignalDetailCard
        signal={MOCK_PAIN}
        signalType="pain"
        onValidate={onValidate}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /validate/i }));
    expect(onValidate).toHaveBeenCalledWith(MOCK_PAIN, "pain");
  });

  it("calls onReject with signal and type", () => {
    const onReject = vi.fn();
    render(
      <SignalDetailCard
        signal={MOCK_PAIN}
        signalType="pain"
        onReject={onReject}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(onReject).toHaveBeenCalledWith(MOCK_PAIN, "pain");
  });

  it("renders with reduced opacity for REJECTED signal", () => {
    const signal = { ...MOCK_PAIN, status: "REJECTED" };
    const { container } = render(
      <SignalDetailCard signal={signal} signalType="pain" />,
    );

    expect(container.firstChild).toHaveStyle({ opacity: 0.5 });
  });

  it("shows incomplete alert when PENDING and missing fields", () => {
    const incomplete = { ...MOCK_PAIN, what: null, dimension: null };
    render(
      <SignalDetailCard signal={incomplete} signalType="pain" />,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/What/)).toBeInTheDocument();
  });

  it("disables validate button when fields are missing", () => {
    const incomplete = { ...MOCK_PAIN, summary: "" };
    render(
      <SignalDetailCard
        signal={incomplete}
        signalType="pain"
        onValidate={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /validate/i })).toBeDisabled();
  });

  it("does not show incomplete alert for complete signal", () => {
    render(
      <SignalDetailCard signal={MOCK_PAIN} signalType="pain" />,
    );

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders tech-stack product name as summary", () => {
    const tsSignal = {
      id: "ts1",
      status: "PENDING",
      _signalType: "tech-stack",
      tech_catalog_entry: { product_name: "Salesforce", company_name: "SFDC" },
    };
    render(
      <SignalDetailCard signal={tsSignal} signalType="tech-stack" />,
    );

    expect(screen.getByText("Salesforce")).toBeInTheDocument();
  });

  it("renders blocker contact from signal.contact", () => {
    const blocker = {
      id: "b1",
      status: "PENDING",
      summary: "Budget frozen",
      contact: { id: "c1", first_name: "Jean", last_name: "Martin" },
      _signalType: "blockers",
    };
    render(
      <SignalDetailCard signal={blocker} signalType="blockers" />,
    );

    expect(screen.getByText("Jean Martin")).toBeInTheDocument();
  });
});
