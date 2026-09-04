// frontend/src/__tests__/components/drawer/InlineEditableValue.test.jsx
//
// SE-b — the shared double-click-to-edit field. Read by default (label + value,
// placeholder when empty); DOUBLE-CLICK the value flips it to an inline themed
// input; typing calls onChange (a draft raised to the parent — NO per-field
// PATCH); Enter/blur returns to read (value kept), Escape reverts the in-flight
// edit. Reusable by every edit drawer.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

import ThemeCustomization from "themes/index";
import InlineEditableValue from "components/drawer/InlineEditableValue";

function renderField(props) {
  return render(
    <ThemeCustomization>
      <InlineEditableValue name="title" label="Title" onChange={() => {}} {...props} />
    </ThemeCustomization>,
  );
}

describe("InlineEditableValue — read mode", () => {
  it("shows the label and the value, no input by default", () => {
    renderField({ value: "Discovery call" });
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Discovery call")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("shows the placeholder when empty", () => {
    renderField({ value: "", placeholder: "Add a title…" });
    expect(screen.getByText("Add a title…")).toBeInTheDocument();
  });

  it("maps a select value to its option label in read mode", () => {
    renderField({
      value: "CALL",
      type: "select",
      options: [{ value: "CALL", label: "Phone Call" }, { value: "EMAIL", label: "Email" }],
    });
    expect(screen.getByText("Phone Call")).toBeInTheDocument();
  });
});

describe("InlineEditableValue — double-click to edit (draft, no PATCH)", () => {
  it("enters edit mode on DOUBLE-CLICK (not single click)", () => {
    renderField({ value: "Discovery call" });
    const read = screen.getByTestId("inline-read-title");
    fireEvent.click(read);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument(); // single click does nothing
    fireEvent.doubleClick(read);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("typing raises onChange with the new value (a draft) and never triggers a save", async () => {
    const onChange = vi.fn();
    renderField({ value: "Discovery call", onChange });
    fireEvent.doubleClick(screen.getByTestId("inline-read-title"));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Discovery call!" } });
    await waitFor(() => expect(onChange).toHaveBeenCalledWith("Discovery call!"));
  });

  it("Enter returns to read mode keeping the value", async () => {
    const onChange = vi.fn();
    const { rerender } = renderField({ value: "A", onChange });
    fireEvent.doubleClick(screen.getByTestId("inline-read-title"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "AB" } });
    // parent would push the new value back down; simulate that
    rerender(
      <ThemeCustomization>
        <InlineEditableValue name="title" label="Title" value="AB" onChange={onChange} />
      </ThemeCustomization>,
    );
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
    await waitFor(() => expect(screen.queryByRole("textbox")).not.toBeInTheDocument());
    expect(screen.getByText("AB")).toBeInTheDocument();
  });

  it("Escape reverts the in-flight edit to the value at edit start", async () => {
    const onChange = vi.fn();
    renderField({ value: "Original", onChange });
    fireEvent.doubleClick(screen.getByTestId("inline-read-title"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Changed" } });
    onChange.mockClear();
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Escape" });
    // reverts to the start value via onChange, and exits edit
    await waitFor(() => expect(onChange).toHaveBeenCalledWith("Original"));
    await waitFor(() => expect(screen.queryByRole("textbox")).not.toBeInTheDocument());
  });
});
