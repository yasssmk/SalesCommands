// frontend/src/__tests__/components/EditableTextBlock.autosave.test.jsx
//
// Sprint « Source / Notes » — notes panel, N4: EditableTextBlock's optional
// AUTOSAVE mode (autosave / onValueChange / indicator). Always in edit, no
// Save / Cancel; every change reported; read-only when locked; follows the
// server's value only while nothing was typed since the last one received.
// Without `autosave` the block is unchanged (its own tests + the regression).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";
import PropTypes from "prop-types";

import EditableTextBlock from "components/EditableTextBlock";

afterEach(() => cleanup());

const block = (props = {}) => (
  <EditableTextBlock
    label="Notes"
    field="outcome_notes"
    initialValue="Server v1"
    onSave={vi.fn()}
    autosave
    {...props}
  />
);

describe("EditableTextBlock — autosave mode", () => {
  it("is always in edit, with no Save / Cancel", () => {
    render(block());
    expect(screen.getByRole("textbox", { name: "Notes" })).toHaveValue("Server v1");
    expect(screen.queryByRole("button", { name: /save/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();
  });

  it("reports every change through onValueChange, never through onSave", () => {
    const onValueChange = vi.fn();
    const onSave = vi.fn();
    render(block({ onValueChange, onSave }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Server v1 +" } });
    expect(onValueChange).toHaveBeenCalledWith("Server v1 +");
    expect(onSave).not.toHaveBeenCalled();
  });

  it("renders the indicator slot on the label row", () => {
    render(block({ indicator: <span data-testid="ind">Saved · 10:15</span> }));
    expect(screen.getByTestId("ind")).toHaveTextContent("Saved · 10:15");
  });

  it("locked → read-only: the text as typed, no text box", () => {
    const { rerender } = render(block());
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Typed" } });
    rerender(block({ isLocked: true }));
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByText("Typed")).toBeInTheDocument();
  });

  it("follows the server's value while nothing was typed since", () => {
    const { rerender } = render(block());
    rerender(block({ initialValue: "Server v2" }));
    expect(screen.getByRole("textbox")).toHaveValue("Server v2");
  });

  it("never overwrites what was typed since the last value received", () => {
    const { rerender } = render(block());
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Mine" } });
    rerender(block({ initialValue: "Server v2" }));
    expect(screen.getByRole("textbox")).toHaveValue("Mine");
    // its own save coming back: the text matches it — it follows again
    rerender(block({ initialValue: "Mine" }));
    rerender(block({ initialValue: "Server v3" }));
    expect(screen.getByRole("textbox")).toHaveValue("Server v3");
  });
});

describe("EditableTextBlock — onSave is optional (N6b)", () => {
  it("read-only without onSave: renders, no crash", () => {
    render(<EditableTextBlock label="Notes" field="outcome_notes" initialValue="Read me" isLocked />);
    expect(screen.getByText("Read me")).toBeInTheDocument();
  });

  it("editable without onSave: Save just leaves the edit, no crash", async () => {
    render(<EditableTextBlock label="Notes" field="outcome_notes" initialValue="v1" />);
    fireEvent.click(screen.getByText("v1"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "v2" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("onSave is no longer a required prop", () => {
    expect(EditableTextBlock.propTypes.onSave).toBe(PropTypes.func);
  });
});

describe("EditableTextBlock — without autosave, unchanged", () => {
  it("still follows the server's value outside edit", () => {
    const { rerender } = render(block({ autosave: undefined }));
    rerender(block({ autosave: undefined, initialValue: "Server v2" }));
    fireEvent.click(screen.getByText("Server v2"));
    expect(screen.getByRole("textbox")).toHaveValue("Server v2");
  });

  it("still click-to-edit with Save / Cancel", () => {
    render(block({ autosave: undefined }));
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Server v1"));
    expect(screen.getByRole("textbox")).toHaveValue("Server v1");
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });
});
