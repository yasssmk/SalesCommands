// frontend/src/__tests__/sections/activities/workspace/RunAIAnalysisButton.test.jsx
//
// Lot 3 / 11 (TD-302) — the Run AI action is the shared pill for every entry
// point (the Source band shows it in its header). Its cases, formerly tested
// through ActivityNotesTab (which no longer renders it): availability (the
// transcript, the CANCELLED-only lock), the wizard, "Analyzing…" + polling.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup, act } from "@testing-library/react";
import AphoriqTheme from "../../../_utils/aphoriqTheme";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

import RunAIAnalysisButton from "sections/activities/workspace/RunAIAnalysisButton";
import { PIPELINE_STATE } from "hooks/usePipelineRunner";

const render = (ui) => rtlRender(<AphoriqTheme>{ui}</AphoriqTheme>);
afterEach(() => cleanup());

const ACTIVITY = { id: "act-1", transcript: "B".repeat(200), outcome_notes: "", status: "PLANNED" };
const runner = (over = {}) => ({ run: vi.fn(), state: PIPELINE_STATE.IDLE, pollProgress: null, ...over });
const renderPill = (props = {}) =>
  render(<RunAIAnalysisButton activity={ACTIVITY} pipelineRunner={runner()} lastRun={null}
    runsByPipeline={{ TRANSCRIPT_SIGNALS: null, NEXT_STEPS: null }} {...props} />);
const pill = () => screen.getByRole("button", { name: "Run AI Analysis" });
const isDisabled = (el) => el.getAttribute("aria-disabled") === "true";

describe("RunAIAnalysisButton — the shared pill (TD-302)", () => {
  it("is a pill (not a MUI button), available with a long enough transcript", () => {
    renderPill();
    expect(pill()).not.toHaveClass("MuiButton-root");
    expect(isDisabled(pill())).toBe(false);
  });

  it.each([
    ["the transcript is empty", { ...ACTIVITY, transcript: "" }],
    ["the transcript is < 50 chars", { ...ACTIVITY, transcript: "Short" }],
    ["the activity is CANCELLED", { ...ACTIVITY, status: "CANCELLED" }],
  ])("is disabled when %s", (_label, activity) => {
    renderPill({ activity });
    expect(isDisabled(pill())).toBe(true);
  });

  it("stays available on a COMPLETED activity", () => {
    renderPill({ activity: { ...ACTIVITY, status: "COMPLETED" } });
    expect(isDisabled(pill())).toBe(false);
  });

  it.each([PIPELINE_STATE.SUCCESS, PIPELINE_STATE.PARTIAL, PIPELINE_STATE.ERROR])(
    "stays available after a run ending %s", (state) => {
      renderPill({ pipelineRunner: runner({ state }) });
      expect(isDisabled(pill())).toBe(false);
    },
  );

  it("a click opens the wizard", async () => {
    renderPill();
    await act(async () => { fireEvent.click(pill()); });
    expect(screen.getByText(/Select objectives/)).toBeInTheDocument();
  });

  it("controlled: a click asks the caller to open (onOpenChange)", async () => {
    const onOpenChange = vi.fn();
    renderPill({ open: false, onOpenChange });
    await act(async () => { fireEvent.click(pill()); });
    expect(onOpenChange).toHaveBeenCalledWith(true);
  });

  it("running: a disabled « Analyzing… » pill, the polling progress when known", () => {
    renderPill({ pipelineRunner: runner({ state: PIPELINE_STATE.RUNNING, pollProgress: { attempt: 3, max: 12 } }) });
    expect(screen.getByRole("button", { name: "Analyzing…" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Polling for result (3/12)…")).toBeInTheDocument();
  });

  it("running without polling progress: no progress line", () => {
    renderPill({ pipelineRunner: runner({ state: PIPELINE_STATE.RUNNING }) });
    expect(screen.getByText("Analyzing…")).toBeInTheDocument();
    expect(screen.queryByText(/Polling for result/)).toBeNull();
  });
});

// ==============================|| « SOURCE / NOTES » 3.2 — EVERYTHING ANALYSED ||============================== //
// The pill is DISABLED once everything AVAILABLE is analysed: the
// qualification done AND the next steps done or unavailable (no decision
// cycle, no successful campaign outcome — hasSuggestedNextSteps). ONE
// predicate, canRunAIAnalysis(activity, pipelineState, runsByPipeline).

import { canRunAIAnalysis } from "sections/activities/workspace/RunAIAnalysisButton";

const RUN = { last_run_at: "2026-11-01T10:00:00Z" };
const DC_ACTIVITY = { ...ACTIVITY, decision_cycle: "dc-1" };
const ANALYSED_TOOLTIP = "Already analysed: an analysis is never re-run";

describe("RunAIAnalysisButton — everything available already analysed (3.2)", () => {
  it("qualification AND next steps analysed: disabled, with its tooltip", async () => {
    renderPill({ activity: DC_ACTIVITY, runsByPipeline: { TRANSCRIPT_SIGNALS: RUN, NEXT_STEPS: RUN } });
    expect(isDisabled(pill())).toBe(true);
    fireEvent.mouseOver(pill().parentElement);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(ANALYSED_TOOLTIP);
  });

  it("qualification analysed, next steps UNAVAILABLE (no cycle): disabled", () => {
    renderPill({ activity: ACTIVITY, runsByPipeline: { TRANSCRIPT_SIGNALS: RUN, NEXT_STEPS: null } });
    expect(isDisabled(pill())).toBe(true);
  });

  it("qualification analysed, next steps still AVAILABLE: active", () => {
    renderPill({ activity: DC_ACTIVITY, runsByPipeline: { TRANSCRIPT_SIGNALS: RUN, NEXT_STEPS: null } });
    expect(isDisabled(pill())).toBe(false);
  });

  it("next steps analysed, qualification not: active", () => {
    renderPill({ activity: DC_ACTIVITY, runsByPipeline: { TRANSCRIPT_SIGNALS: null, NEXT_STEPS: RUN } });
    expect(isDisabled(pill())).toBe(false);
  });

  it("nothing analysed: active", () => {
    renderPill({ activity: DC_ACTIVITY });
    expect(isDisabled(pill())).toBe(false);
  });

  it("the predicate itself: one rule for every entry point", () => {
    const all = { TRANSCRIPT_SIGNALS: RUN, NEXT_STEPS: RUN };
    expect(canRunAIAnalysis(DC_ACTIVITY, PIPELINE_STATE.IDLE, all)).toBe(false);
    expect(canRunAIAnalysis(DC_ACTIVITY, PIPELINE_STATE.IDLE, { TRANSCRIPT_SIGNALS: RUN })).toBe(true);
    expect(canRunAIAnalysis(ACTIVITY, PIPELINE_STATE.IDLE, { TRANSCRIPT_SIGNALS: RUN })).toBe(false);
    expect(canRunAIAnalysis({ ...DC_ACTIVITY, status: "CANCELLED" }, PIPELINE_STATE.IDLE, {})).toBe(false);
  });
});
