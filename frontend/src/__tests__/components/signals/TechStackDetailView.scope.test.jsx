// frontend/src/__tests__/components/signals/TechStackDetailView.scope.test.jsx
//
// Sprint « Cycle de vie des contacts », étape 2b (2) — the TechStack detail
// (Activity chassis) shows the SCOPE in §1 Technology: « Account-wide » /
// « This deal », label from the choices (tech_scopes), else scope_display;
// a payload without scope reads Account-wide (the backend default).

import { describe, it, expect, afterEach } from "vitest";
import { render as rtlRender, screen, cleanup } from "@testing-library/react";
import AphoriqTheme from "../../_utils/aphoriqTheme";
import SignalDetailPanel from "components/signals/SignalDetailPanel";

const render = (ui, opts) => rtlRender(ui, { wrapper: AphoriqTheme, ...opts });

afterEach(() => cleanup());

const CHOICES = {
  usage_scopes: [{ value: "COMPANY", label: "Company" }, { value: "UNKNOWN", label: "Unknown" }],
  tech_scopes: [
    { value: "ACCOUNT", label: "Account-wide" },
    { value: "DEAL", label: "This deal" },
  ],
};

const TECH = {
  id: "ts-scope",
  status: "PENDING",
  tech_name: "HubSpot",
  scope: "DEAL",
  scope_display: "This deal",
  usage_scope: "COMPANY",
  usage_departments: [],
  is_discontinued: false,
  source_quote: "We evaluate HubSpot.",
  source_context: { activity: { id: "act-1" }, contacts: [] },
};

const renderDetail = (signal, choices = CHOICES) =>
  render(
    <SignalDetailPanel
      signal={signal}
      signalType="tech-stack"
      currentActivityId="act-1"
      choices={choices}
    />,
  );

describe("TechStack detail — scope (étape 2b)", () => {
  it("shows « This deal » for a DEAL tool", () => {
    renderDetail(TECH);
    expect(screen.getByTestId("techstack-scope")).toHaveTextContent("Scope");
    expect(screen.getByTestId("techstack-scope")).toHaveTextContent("This deal");
  });

  it("shows « Account-wide » for an ACCOUNT tool", () => {
    renderDetail({ ...TECH, scope: "ACCOUNT", scope_display: "Account-wide" });
    expect(screen.getByTestId("techstack-scope")).toHaveTextContent("Account-wide");
  });

  it("falls back to scope_display without choices", () => {
    renderDetail(TECH, { usage_scopes: CHOICES.usage_scopes });
    expect(screen.getByTestId("techstack-scope")).toHaveTextContent("This deal");
  });

  it("a payload without scope reads Account-wide", () => {
    const { scope, scope_display, ...legacy } = TECH;
    renderDetail(legacy);
    expect(screen.getByTestId("techstack-scope")).toHaveTextContent("Account-wide");
  });
});
