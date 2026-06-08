// frontend/src/__tests__/signals/SignalIncompleteAlert.test.jsx

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import SignalIncompleteAlert from "sections/activities/signals/SignalIncompleteAlert";

afterEach(() => {
  cleanup();
});

describe("SignalIncompleteAlert", () => {
  it("renders nothing when missingFields is empty", () => {
    const { container } = render(<SignalIncompleteAlert missingFields={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when missingFields is null", () => {
    const { container } = render(<SignalIncompleteAlert missingFields={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when missingFields is undefined", () => {
    const { container } = render(<SignalIncompleteAlert />);
    expect(container.firstChild).toBeNull();
  });

  it("renders warning alert with single missing field", () => {
    render(
      <SignalIncompleteAlert
        missingFields={[{ key: "summary", label: "Summary" }]}
      />,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Summary")).toBeInTheDocument();
    expect(screen.getByText(/Complete before validating/)).toBeInTheDocument();
  });

  it("renders warning alert with multiple missing fields", () => {
    render(
      <SignalIncompleteAlert
        missingFields={[
          { key: "what", label: "What" },
          { key: "dimension", label: "Dimension" },
          { key: "summary", label: "Summary" },
        ]}
      />,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("What, Dimension, Summary")).toBeInTheDocument();
  });

  it("renders with warning severity", () => {
    const { container } = render(
      <SignalIncompleteAlert
        missingFields={[{ key: "summary", label: "Summary" }]}
      />,
    );

    const alert = container.querySelector(".MuiAlert-standardWarning");
    expect(alert).toBeInTheDocument();
  });
});
