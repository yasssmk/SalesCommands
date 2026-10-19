// frontend/src/__tests__/components/signals/CompetitorDetailView.test.jsx
//
// Sprint Competitor C1 — the Competitor detail on the standard drawer chassis
// (Activity surface only), skeleton of ObjectionDetailView. 2 sections in this
// order: Competitor → Source (Source LAST).
//   - §1 Competitor: the competitor NAME as the headline of the shared summary
//     box (as TechStack does with the tool name), the AI sentence (summary)
//     below it.
//   - §2 Source: quote + participants + origin-activity link.
//   - No "Mentioned by".
// DC / Account (no currentActivityId, or the cluster coque's leading/trailing
// actions) keep the flush branch (CompetitorDetails) unchanged.

import { describe, it, expect, afterEach } from "vitest";
import { render as rtlRender, screen, cleanup, within } from "@testing-library/react";
import AphoriqTheme from "../../_utils/aphoriqTheme";
import SignalDetailPanel from "components/signals/SignalDetailPanel";
import SignalDetailContent from "components/signals/SignalDetailContent";

const render = (ui, opts) => rtlRender(ui, { wrapper: AphoriqTheme, ...opts });

afterEach(() => cleanup());

const COMPETITOR = {
  id: "cmp-chassis",
  status: "PENDING",
  competitor_name: "Intercom",
  summary: "The prospect is also evaluating Intercom instead of us.",
  source_quote: "We're also looking at Intercom.",
  source_context: {
    activity: { id: "act-origin" },
    contacts: [{ id: "c2", first_name: "Jane", last_name: "Doe" }],
  },
};

const renderChassis = (signal, extra = {}) =>
  render(
    <SignalDetailPanel
      signal={signal}
      signalType="competitors"
      currentActivityId="act-1"
      {...extra}
    />,
  );

describe("Competitor detail on the chassis (Activity, C1)", () => {
  it("C1-1: competitors + currentActivityId → chassis body, Competitor then Source (last)", () => {
    renderChassis(COMPETITOR);
    const body = screen.getByTestId("competitor-detail-body");
    // Without the coque, the in-content header also reads "Competitor": take
    // the §1 section title, i.e. the one outside that header.
    const header = screen.getByTestId("competitor-detail-header");
    const competitor = within(body)
      .getAllByText("Competitor")
      .find((el) => !header.contains(el));
    const source = within(body).getByText("Source");
    expect(
      competitor.compareDocumentPosition(source) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // Flush marker absent.
    expect(screen.queryByText("COMPETITOR")).not.toBeInTheDocument();
  });

  it("C1-2: §1 the name heads the summary box, the AI sentence comes below it", () => {
    renderChassis(COMPETITOR);
    const name = screen.getByTestId("competitor-summary-text");
    expect(name).toHaveTextContent("Intercom");
    expect(name).not.toHaveTextContent("evaluating");
    const sentence = screen.getByTestId("competitor-summary");
    expect(sentence).toHaveTextContent("The prospect is also evaluating Intercom instead of us.");
    expect(
      name.compareDocumentPosition(sentence) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("C1-3: no 'Mentioned by'", () => {
    renderChassis(COMPETITOR);
    expect(screen.queryByText(/Mentioned by/i)).not.toBeInTheDocument();
  });

  it("C1-4: §2 Source — quote, participants and origin link", () => {
    renderChassis(COMPETITOR);
    const source = screen.getByTestId("competitor-source");
    expect(source).toHaveTextContent("We're also looking at Intercom.");
    expect(within(source).getByText("Jane Doe")).toBeInTheDocument();
    expect(within(source).getByRole("button", { name: /view origin activity/i })).toBeInTheDocument();
  });

  it("C1-5 (witness): competitors WITHOUT currentActivityId (DC/Account) → flush branch unchanged", () => {
    render(<SignalDetailPanel signal={COMPETITOR} signalType="competitors" />);
    expect(screen.queryByTestId("competitor-detail-body")).not.toBeInTheDocument();
    expect(screen.getByText("COMPETITOR")).toBeInTheDocument();
  });

  it("C1-6 (witness): competitors + leading/trailing (cluster coque) → flush branch", () => {
    render(
      <SignalDetailContent
        signal={COMPETITOR}
        signalType="competitors"
        currentActivityId="act-1"
        leadingAction={<span>back</span>}
        trailingAction={<span>close</span>}
      />,
    );
    expect(screen.queryByTestId("competitor-detail-body")).not.toBeInTheDocument();
    expect(screen.getByText("COMPETITOR")).toBeInTheDocument();
  });
});
