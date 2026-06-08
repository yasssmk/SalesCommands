// frontend/src/__tests__/signals/SignalCompactLine.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import SignalCompactLine from "sections/activities/signals/SignalCompactLine";

afterEach(() => {
  cleanup();
});

const MOCK_SIGNAL = {
  id: "s1",
  status: "PENDING",
  summary: "Lost 5h/week on consolidation tasks",
};

describe("SignalCompactLine", () => {
  it("renders signal type chip and summary", () => {
    render(
      <SignalCompactLine
        signal={MOCK_SIGNAL}
        signalType="pain"
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Pain")).toBeInTheDocument();
    expect(screen.getByText(/Lost 5h\/week/)).toBeInTheDocument();
  });

  it("renders status chip", () => {
    render(
      <SignalCompactLine
        signal={MOCK_SIGNAL}
        signalType="pain"
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("shows validate/reject buttons for PENDING signals", () => {
    render(
      <SignalCompactLine
        signal={MOCK_SIGNAL}
        signalType="pain"
        onSelect={vi.fn()}
        onValidate={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /validate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
  });

  it("hides validate/reject buttons for VALIDATED signals", () => {
    const validated = { ...MOCK_SIGNAL, status: "VALIDATED" };
    render(
      <SignalCompactLine
        signal={validated}
        signalType="pain"
        onSelect={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
  });

  it("hides validate/reject buttons when locked", () => {
    render(
      <SignalCompactLine
        signal={MOCK_SIGNAL}
        signalType="pain"
        onSelect={vi.fn()}
        isLocked
      />,
    );

    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
  });

  it("calls onSelect on line click", () => {
    const onSelect = vi.fn();
    render(
      <SignalCompactLine
        signal={MOCK_SIGNAL}
        signalType="pain"
        onSelect={onSelect}
      />,
    );

    fireEvent.click(screen.getByText(/Lost 5h\/week/));
    expect(onSelect).toHaveBeenCalledWith(MOCK_SIGNAL, "pain");
  });

  it("calls onValidate on validate button click without propagating", () => {
    const onSelect = vi.fn();
    const onValidate = vi.fn();
    render(
      <SignalCompactLine
        signal={MOCK_SIGNAL}
        signalType="pain"
        onSelect={onSelect}
        onValidate={onValidate}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /validate/i }));
    expect(onValidate).toHaveBeenCalledWith(MOCK_SIGNAL, "pain");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("calls onReject on reject button click without propagating", () => {
    const onSelect = vi.fn();
    const onReject = vi.fn();
    render(
      <SignalCompactLine
        signal={MOCK_SIGNAL}
        signalType="pain"
        onSelect={onSelect}
        onReject={onReject}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(onReject).toHaveBeenCalledWith(MOCK_SIGNAL, "pain");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("renders with reduced opacity for REJECTED signals", () => {
    const rejected = { ...MOCK_SIGNAL, status: "REJECTED" };
    const { container } = render(
      <SignalCompactLine
        signal={rejected}
        signalType="pain"
        onSelect={vi.fn()}
      />,
    );

    const line = container.firstChild;
    expect(line).toHaveStyle({ opacity: 0.5 });
  });

  it("renders tech-stack product name as summary", () => {
    const tsSignal = {
      id: "ts1",
      status: "PENDING",
      tech_catalog_entry: { product_name: "Salesforce", company_name: "SFDC" },
    };
    render(
      <SignalCompactLine
        signal={tsSignal}
        signalType="tech-stack"
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Salesforce")).toBeInTheDocument();
  });
});
