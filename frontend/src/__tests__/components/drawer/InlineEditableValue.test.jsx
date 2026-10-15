// frontend/src/__tests__/components/drawer/InlineEditableValue.test.jsx
//
// SE-b — the shared click-to-edit field. Read by default (label + value,
// placeholder when empty); a single CLICK on the value flips it to an inline themed
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

import { useState } from "react";
import Box from "@mui/material/Box";
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

describe("InlineEditableValue — single click to edit (draft, no PATCH)", () => {
  it("enters edit mode on a SINGLE click (PO decision: one click, everywhere)", () => {
    renderField({ value: "Discovery call" });
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument(); // read by default
    fireEvent.click(screen.getByTestId("inline-read-title"));
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("typing raises onChange with the new value (a draft) and never triggers a save", async () => {
    const onChange = vi.fn();
    renderField({ value: "Discovery call", onChange });
    fireEvent.click(screen.getByTestId("inline-read-title"));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Discovery call!" } });
    await waitFor(() => expect(onChange).toHaveBeenCalledWith("Discovery call!"));
  });

  it("Enter returns to read mode keeping the value", async () => {
    const onChange = vi.fn();
    const { rerender } = renderField({ value: "A", onChange });
    fireEvent.click(screen.getByTestId("inline-read-title"));
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
    fireEvent.click(screen.getByTestId("inline-read-title"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Changed" } });
    onChange.mockClear();
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Escape" });
    // reverts to the start value via onChange, and exits edit
    await waitFor(() => expect(onChange).toHaveBeenCalledWith("Original"));
    await waitFor(() => expect(screen.queryByRole("textbox")).not.toBeInTheDocument());
  });
});

describe("InlineEditableValue — select: one click opens the menu, a choice closes", () => {
  const OPTIONS = [{ value: "CALL", label: "Phone Call" }, { value: "EMAIL", label: "Email" }];

  it("a click opens the field with its menu already open (no second click)", () => {
    renderField({ value: "CALL", type: "select", options: OPTIONS });
    fireEvent.click(screen.getByTestId("inline-read-title"));
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });

  it("picking an option raises onChange and returns to READ", async () => {
    const onChange = vi.fn();
    renderField({ value: "CALL", type: "select", options: OPTIONS, onChange });
    fireEvent.click(screen.getByTestId("inline-read-title"));
    fireEvent.click(screen.getByRole("option", { name: "Email" }));
    expect(onChange).toHaveBeenCalledWith("EMAIL");
    await waitFor(() => expect(screen.queryByTestId("inline-input-title")).not.toBeInTheDocument());
  });

  it("Escape with the menu open returns to READ, value untouched", async () => {
    const onChange = vi.fn();
    renderField({ value: "CALL", type: "select", options: OPTIONS, onChange });
    fireEvent.click(screen.getByTestId("inline-read-title"));
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByTestId("inline-input-title")).not.toBeInTheDocument());
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText("Phone Call")).toBeInTheDocument();
  });
});

describe("InlineEditableValue — renderEditor (custom editor, same mechanics)", () => {
  const A = { id: 1, name: "Alice" };
  const B = { id: 2, name: "Bob" };
  // A parent that holds the draft, like Formik does.
  function Harness({ onChange = () => {} }) {
    const [value, setValue] = useState(A);
    return (
      <ThemeCustomization>
        <InlineEditableValue
          name="who"
          label="Who"
          value={value}
          onChange={(v) => {
            onChange(v);
            setValue(v);
          }}
          formatValue={(v) => v?.name ?? null}
          renderEditor={({ value: v, onChange: change, commit }) => (
            <Box>
              <input data-testid="custom-editor" readOnly value={v?.name ?? ""} />
              <button type="button" onClick={() => { change(B); commit(); }}>pick-bob</button>
            </Box>
          )}
        />
      </ThemeCustomization>
    );
  }

  it("reads through formatValue; one click shows the custom editor with the value", () => {
    render(<Harness />);
    expect(screen.getByTestId("inline-read-who")).toHaveTextContent("Alice");
    expect(screen.queryByTestId("custom-editor")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("inline-read-who"));
    expect(screen.getByTestId("custom-editor")).toHaveValue("Alice");
  });

  it("onChange + commit from the editor → back to READ with the new value", () => {
    render(<Harness />);
    fireEvent.click(screen.getByTestId("inline-read-who"));
    fireEvent.click(screen.getByRole("button", { name: "pick-bob" }));
    expect(screen.queryByTestId("custom-editor")).not.toBeInTheDocument();
    expect(screen.getByTestId("inline-read-who")).toHaveTextContent("Bob");
  });

  it("Escape inside the editor cancels: back to READ with the value at edit start", () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    fireEvent.click(screen.getByTestId("inline-read-who"));
    fireEvent.keyDown(screen.getByTestId("custom-editor"), { key: "Escape" });
    expect(screen.queryByTestId("custom-editor")).not.toBeInTheDocument();
    expect(onChange).toHaveBeenCalledWith(A);
    expect(screen.getByTestId("inline-read-who")).toHaveTextContent("Alice");
  });

  it("focus leaving the editor commits (click outside) → back to READ", () => {
    render(<Harness />);
    fireEvent.click(screen.getByTestId("inline-read-who"));
    fireEvent.blur(screen.getByTestId("custom-editor"));
    expect(screen.queryByTestId("custom-editor")).not.toBeInTheDocument();
    expect(screen.getByTestId("inline-read-who")).toHaveTextContent("Alice");
  });
});

describe("InlineEditableValue — inputPlaceholder (opt-in edit placeholder)", () => {
  it("passes inputPlaceholder to the OPEN input; the read placeholder is unchanged", () => {
    renderField({ value: "", type: "textarea", placeholder: "No title", inputPlaceholder: "Type a title" });
    // Read mode still shows the read placeholder.
    expect(screen.getByText("No title")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("inline-read-title"));
    expect(screen.getByTestId("inline-input-title")).toHaveAttribute("placeholder", "Type a title");
  });

  it("without inputPlaceholder the OPEN input has NO placeholder (retro-compat)", () => {
    renderField({ value: "", type: "text", placeholder: "No title" });
    fireEvent.click(screen.getByTestId("inline-read-title"));
    expect(screen.getByTestId("inline-input-title")).not.toHaveAttribute("placeholder");
  });
});
