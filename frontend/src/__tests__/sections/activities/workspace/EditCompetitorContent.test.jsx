// frontend/src/__tests__/sections/activities/workspace/EditCompetitorContent.test.jsx
//
// Sprint Competitor C2 — the Competitor (competitors) EDIT drawer, a clone of
// EditObjectionContent on the standard chassis. Fields: §1 competitor_name
// (required, ≤ COMPETITOR_NAME_MAX_LENGTH), §2 summary (≥ SIGNAL_SUMMARY_MIN_LENGTH,
// as Objection), §3 source_quote (last). Save PATCHes
// updateSignal("competitors", id, {competitor_name, summary, source_quote}).

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

// ---- mocks (before importing the component) ----
vi.mock("api/signals/signals", () => ({
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));
const closeDrawer = vi.fn();
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ closeDrawer, openDrawer: vi.fn() }),
}));

import EditCompetitorContent from "sections/activities/workspace/EditCompetitorContent";
import { updateSignal } from "api/signals/signals";
import {
  COMPETITOR_NAME_MAX_LENGTH,
  SIGNAL_SUMMARY_MIN_LENGTH,
} from "sections/activities/signals/signalValidationRules";

const COMPETITOR = {
  id: "competitor-1",
  status: "PENDING",
  competitor_name: "Intercom",
  summary: "The prospect is also evaluating Intercom instead of us.",
  source_quote: "We're also looking at Intercom.",
};

const renderEdit = (competitor = COMPETITOR, props = {}) =>
  render(
    <AphoriqTheme>
      <EditCompetitorContent competitor={competitor} {...props} />
    </AphoriqTheme>,
  );

const save = async () => {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
  });
};

const edit = (name, value) => {
  fireEvent.click(screen.getByTestId(`inline-read-${name}`));
  fireEvent.change(screen.getByTestId(`inline-input-${name}`), { target: { value } });
};

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("EditCompetitorContent (Competitor C2)", () => {
  it("renders the 3 fields pre-filled in order (name, summary, quote) + no own 'Edit competitor' title", () => {
    renderEdit();
    const reads = ["competitor_name", "summary", "source_quote"].map((name) =>
      screen.getByTestId(`inline-read-${name}`),
    );
    for (let i = 1; i < reads.length; i += 1) {
      expect(
        reads[i - 1].compareDocumentPosition(reads[i]) & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
    }
    expect(reads[0]).toHaveTextContent("Intercom");
    expect(reads[1]).toHaveTextContent(COMPETITOR.summary);
    expect(reads[2]).toHaveTextContent(COMPETITOR.source_quote);
    expect(screen.queryByText("Edit competitor")).not.toBeInTheDocument();
  });

  it("Save → updateSignal('competitors', id, {competitor_name, summary, source_quote}) only", async () => {
    renderEdit();
    edit("competitor_name", "  HubSpot  ");
    edit("summary", "HubSpot is the other option the prospect is weighing.");
    edit("source_quote", "We're starting to look at HubSpot.");
    await save();
    expect(updateSignal).toHaveBeenCalledTimes(1);
    const [type, id, patch] = updateSignal.mock.calls[0];
    expect(type).toBe("competitors");
    expect(id).toBe("competitor-1");
    expect(patch).toEqual({
      competitor_name: "HubSpot",
      summary: "HubSpot is the other option the prospect is weighing.",
      source_quote: "We're starting to look at HubSpot.",
    });
  });

  it("summary shorter than the minimum → Save disabled, no PATCH", async () => {
    renderEdit();
    edit("summary", "x".repeat(SIGNAL_SUMMARY_MIN_LENGTH - 1));
    // Validation is async (Yup) — let it settle.
    await act(async () => {});
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
    await save();
    expect(updateSignal).not.toHaveBeenCalled();
  });

  it("empty name → Save disabled, no PATCH", async () => {
    renderEdit();
    edit("competitor_name", "   ");
    await act(async () => {});
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
    await save();
    expect(updateSignal).not.toHaveBeenCalled();
  });

  it("name longer than the limit → Save disabled, no PATCH; at the limit → saved", async () => {
    renderEdit();
    edit("competitor_name", "a".repeat(COMPETITOR_NAME_MAX_LENGTH + 1));
    await act(async () => {});
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
    await save();
    expect(updateSignal).not.toHaveBeenCalled();

    // The field is still in edit mode: type into the open input.
    fireEvent.change(screen.getByTestId("inline-input-competitor_name"), {
      target: { value: "a".repeat(COMPETITOR_NAME_MAX_LENGTH) },
    });
    await act(async () => {});
    await save();
    expect(updateSignal).toHaveBeenCalledTimes(1);
  });

  it("Save returns to the detail — onSaved gets the rebuilt signal", async () => {
    const onSaved = vi.fn();
    renderEdit(COMPETITOR, { onSaved });
    edit("competitor_name", "HubSpot");
    await save();
    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(onSaved.mock.calls[0][0]).toMatchObject({
      id: "competitor-1",
      status: "PENDING",
      competitor_name: "HubSpot",
      summary: COMPETITOR.summary,
      source_quote: COMPETITOR.source_quote,
    });
    expect(closeDrawer).not.toHaveBeenCalled();
  });

  it("Cancel → onCancel, no PATCH", () => {
    const onCancel = vi.fn();
    renderEdit(COMPETITOR, { onCancel });
    edit("competitor_name", "HubSpot");
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(updateSignal).not.toHaveBeenCalled();
  });
});
