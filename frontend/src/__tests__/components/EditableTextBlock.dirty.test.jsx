// frontend/src/__tests__/components/EditableTextBlock.dirty.test.jsx
//
// Sprint « Source / Notes » 2.4 — EditableTextBlock reports its UNSAVED state
// through the optional onDirtyChange(dirty): true while editing with a value
// different from the saved one, false once saved, cancelled or back to the
// saved value. Without the prop, nothing changes.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";

import EditableTextBlock from "components/EditableTextBlock";

afterEach(() => cleanup());

function renderBlock(props = {}) {
  const onDirtyChange = vi.fn();
  const onSave = vi.fn(() => Promise.resolve(true));
  render(
    <EditableTextBlock
      label="Notes"
      field="outcome_notes"
      initialValue="Saved"
      onSave={onSave}
      onDirtyChange={onDirtyChange}
      {...props}
    />,
  );
  return { onDirtyChange, onSave };
}

const lastDirty = (fn) => fn.mock.calls.at(-1)?.[0];

describe("EditableTextBlock — onDirtyChange", () => {
  it("is dirty while editing with a changed value", () => {
    const { onDirtyChange } = renderBlock();
    fireEvent.click(screen.getByText("Saved"));
    expect(lastDirty(onDirtyChange)).not.toBe(true);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Saved, then more" } });
    expect(lastDirty(onDirtyChange)).toBe(true);
  });

  it("back to the saved value: not dirty", () => {
    const { onDirtyChange } = renderBlock();
    fireEvent.click(screen.getByText("Saved"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "x" } });
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Saved" } });
    expect(lastDirty(onDirtyChange)).toBe(false);
  });

  it("Cancel: not dirty", () => {
    const { onDirtyChange } = renderBlock();
    fireEvent.click(screen.getByText("Saved"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: /Cancel/ }));
    expect(lastDirty(onDirtyChange)).toBe(false);
  });

  it("a successful Save: not dirty", async () => {
    const { onDirtyChange } = renderBlock();
    fireEvent.click(screen.getByText("Saved"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "x" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /Save/ })); });
    expect(lastDirty(onDirtyChange)).toBe(false);
  });

  it("a refused Save: still dirty (the edit stays)", async () => {
    const { onDirtyChange } = renderBlock({ onSave: vi.fn(() => Promise.resolve(false)) });
    fireEvent.click(screen.getByText("Saved"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "x" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /Save/ })); });
    expect(lastDirty(onDirtyChange)).toBe(true);
  });
});
