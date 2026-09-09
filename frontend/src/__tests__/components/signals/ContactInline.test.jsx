// frontend/src/__tests__/components/signals/ContactInline.test.jsx
//
// SIG-5f — the shared inline contact: full name emphasised (bold, text.primary),
// job title · department muted (text.secondary). Separators live in the muted
// span, so the name reads first and the rest recedes.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import ContactInline from "components/signals/ContactInline";

afterEach(() => cleanup());

const CONTACT = {
  id: "c1",
  first_name: "Dana",
  last_name: "Lee",
  job_title: "CMO",
  department: { id: "d1", name: "Marketing" },
};

describe("ContactInline", () => {
  it("renders the full name in bold text.primary", () => {
    render(<ContactInline contact={CONTACT} />);
    const name = screen.getByText("Dana Lee");
    expect(getComputedStyle(name).fontWeight).toBe("600");
    expect(getComputedStyle(name).color).toBe("rgba(0, 0, 0, 0.87)");
  });

  it("renders the job title · department in muted text.secondary", () => {
    render(<ContactInline contact={CONTACT} />);
    const meta = screen.getByText(/CMO · Marketing/);
    expect(getComputedStyle(meta).color).toBe("rgba(0, 0, 0, 0.6)");
  });

  it("renders name only when there is no job/department", () => {
    render(<ContactInline contact={{ first_name: "Sam", last_name: "Roe" }} />);
    expect(screen.getByText("Sam Roe")).toBeInTheDocument();
  });

  it("renders nothing for a null contact", () => {
    const { container } = render(<ContactInline contact={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
