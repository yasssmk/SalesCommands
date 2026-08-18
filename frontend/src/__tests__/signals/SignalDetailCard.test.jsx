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
    contacts: [{ id: "c1", first_name: "Marie", last_name: "Curie" }],
  },
};

describe("SignalDetailCard", () => {
  // ==============================|| RENDERING ||============================== //

  it("renders signal type and status chips", () => {
    render(<SignalDetailCard signal={MOCK_PAIN} signalType="pain" />);

    expect(screen.getByText("Pain")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("renders theme chip when what_display and dimension_display present", () => {
    render(<SignalDetailCard signal={MOCK_PAIN} signalType="pain" />);

    expect(screen.getByText("Data × Time")).toBeInTheDocument();
  });

  it("does not render theme chip when missing theme fields", () => {
    const signal = { ...MOCK_PAIN, what_display: null, dimension_display: null };
    render(<SignalDetailCard signal={signal} signalType="pain" />);

    expect(screen.queryByText(/×/)).not.toBeInTheDocument();
  });

  it("renders summary", () => {
    render(<SignalDetailCard signal={MOCK_PAIN} signalType="pain" />);

    expect(screen.getByText("Lost 5h/week on consolidation")).toBeInTheDocument();
  });

  it("renders extraction date", () => {
    render(<SignalDetailCard signal={MOCK_PAIN} signalType="pain" />);

    expect(screen.getByText(/Extracted:/)).toBeInTheDocument();
  });

  it("renders with reduced opacity for REJECTED signal", () => {
    const signal = { ...MOCK_PAIN, status: "REJECTED" };
    const { container } = render(
      <SignalDetailCard signal={signal} signalType="pain" />,
    );

    expect(container.firstChild).toHaveStyle({ opacity: 0.5 });
  });

  // ==============================|| SOURCE QUOTE (Fix 2) ||============================== //

  it("renders source_quote for pain signal", () => {
    render(<SignalDetailCard signal={MOCK_PAIN} signalType="pain" />);

    expect(
      screen.getByText(/We spend too much time consolidating data/),
    ).toBeInTheDocument();
  });

  it("renders source_quote for objective signal", () => {
    const signal = {
      ...MOCK_PAIN,
      id: "o1",
      _signalType: "objective",
      source_quote: "Our goal is to reduce churn by 15%",
    };
    render(<SignalDetailCard signal={signal} signalType="objective" />);

    expect(screen.getByText(/Our goal is to reduce churn by 15%/)).toBeInTheDocument();
  });

  it("renders source_quote for impact signal", () => {
    const signal = {
      ...MOCK_PAIN,
      id: "i1",
      _signalType: "impact",
      source_quote: "Productivity dropped 20% last quarter",
    };
    render(<SignalDetailCard signal={signal} signalType="impact" />);

    expect(screen.getByText(/Productivity dropped 20% last quarter/)).toBeInTheDocument();
  });

  it("renders source_quote for tech-stack signal", () => {
    const signal = {
      id: "ts1",
      status: "PENDING",
      _signalType: "tech-stack",
      tech_name: "Salesforce",
      source_quote: "We use Salesforce for everything",
      source_context: { contacts: [] },
    };
    render(<SignalDetailCard signal={signal} signalType="tech-stack" />);

    expect(screen.getByText(/We use Salesforce for everything/)).toBeInTheDocument();
  });

  it("renders source_quote for blocker signal", () => {
    const signal = {
      id: "b1",
      status: "PENDING",
      summary: "Budget frozen",
      _signalType: "blockers",
      source_quote: "No budget until Q2",
      contact: { id: "c1", first_name: "Jean", last_name: "Martin" },
    };
    render(<SignalDetailCard signal={signal} signalType="blockers" />);

    expect(screen.getByText(/No budget until Q2/)).toBeInTheDocument();
  });

  it("does not render quote block when source_quote is empty", () => {
    const signal = { ...MOCK_PAIN, source_quote: null };
    const { container } = render(
      <SignalDetailCard signal={signal} signalType="pain" />,
    );

    expect(container.querySelector('[style*="italic"]')).not.toBeInTheDocument();
  });

  // ==============================|| TECH STACK NAME (Fix 3a) ||============================== //

  it("renders tech_name for tech-stack", () => {
    const signal = {
      id: "ts1",
      status: "PENDING",
      tech_name: "Salesforce",
      source_context: { contacts: [] },
    };
    render(<SignalDetailCard signal={signal} signalType="tech-stack" />);

    expect(screen.getByText("Salesforce")).toBeInTheDocument();
    expect(screen.queryByText("Not in catalog")).not.toBeInTheDocument();
  });

  it("never shows a 'Not in catalog' chip (S10 — no catalogue to be absent from)", () => {
    // The chip flagged a tool the LLM could not match to the tenant
    // catalogue. With identity carried on the signal itself, every tech
    // signal names its tool and nothing is "pending a match".
    const signal = {
      id: "ts2",
      status: "PENDING",
      tech_name: "Notion",
      metadata: { pending_tech_name: "Notion" },
      source_context: { contacts: [] },
    };
    render(<SignalDetailCard signal={signal} signalType="tech-stack" />);

    expect(screen.getByText("Notion")).toBeInTheDocument();
    expect(screen.queryByText("Not in catalog")).not.toBeInTheDocument();
  });

  it("renders 'Unknown tool' when the signal has no name", () => {
    const signal = {
      id: "ts3",
      status: "PENDING",
      tech_name: "",
      metadata: null,
      source_context: { contacts: [] },
    };
    render(<SignalDetailCard signal={signal} signalType="tech-stack" />);

    expect(screen.getByText("Unknown tool")).toBeInTheDocument();
  });

  // ==============================|| CONTACT RULE (Fix 3b) ||============================== //

  it("renders source_context.contacts[0] as contact", () => {
    render(<SignalDetailCard signal={MOCK_PAIN} signalType="pain" />);

    expect(screen.getByText("Marie Curie")).toBeInTheDocument();
  });

  it("renders signal.contact for blocker (priority over source_context)", () => {
    const blocker = {
      id: "b1",
      status: "PENDING",
      summary: "Budget frozen",
      contact: { id: "c1", first_name: "Jean", last_name: "Martin" },
      source_context: {
        contacts: [{ id: "c2", first_name: "Marie", last_name: "Curie" }],
      },
      _signalType: "blockers",
    };
    render(<SignalDetailCard signal={blocker} signalType="blockers" />);

    expect(screen.getByText("Jean Martin")).toBeInTheDocument();
    expect(screen.queryByText("Marie Curie")).not.toBeInTheDocument();
  });

  it("falls back to source_context.contacts[0] when blocker has no signal.contact", () => {
    const blocker = {
      id: "b2",
      status: "PENDING",
      summary: "Budget frozen",
      contact: null,
      source_context: {
        contacts: [{ id: "c2", first_name: "Marie", last_name: "Curie" }],
      },
      _signalType: "blockers",
    };
    render(<SignalDetailCard signal={blocker} signalType="blockers" />);

    expect(screen.getByText("Marie Curie")).toBeInTheDocument();
  });

  it("renders nothing (no crash) when no contact available", () => {
    const signal = {
      ...MOCK_PAIN,
      contact: null,
      source_context: { contacts: [] },
    };
    const { container } = render(
      <SignalDetailCard signal={signal} signalType="pain" />,
    );

    expect(screen.queryByText("No contact attributed")).not.toBeInTheDocument();
    expect(container.firstChild).toBeInTheDocument();
  });

  it("renders tech-stack with source contact from activity", () => {
    const ts = {
      id: "ts4",
      status: "PENDING",
      tech_name: "HubSpot",
      source_context: {
        contacts: [{ id: "c3", first_name: "Alice", last_name: "Dupont" }],
      },
    };
    render(<SignalDetailCard signal={ts} signalType="tech-stack" />);

    expect(screen.getByText("Alice Dupont")).toBeInTheDocument();
  });

  // ==============================|| ACTIONS ||============================== //

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
      <SignalDetailCard signal={MOCK_PAIN} signalType="pain" onEdit={onEdit} />,
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

  // ==============================|| INCOMPLETE ALERTS ||============================== //

  it("shows incomplete alert when PENDING and missing fields", () => {
    const incomplete = { ...MOCK_PAIN, what: null, dimension: null };
    render(<SignalDetailCard signal={incomplete} signalType="pain" />);

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
    render(<SignalDetailCard signal={MOCK_PAIN} signalType="pain" />);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
