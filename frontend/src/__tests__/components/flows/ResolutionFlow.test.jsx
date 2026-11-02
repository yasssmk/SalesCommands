// frontend/src/__tests__/components/flows/ResolutionFlow.test.jsx
//
// Sprint « Cycle de vie des contacts », étape 5 (3) — the generic resolution
// flow extracted from NextStepValidateFlow (shared with PeopleValidateFlow):
//   - ResolutionFlow: the wizard steps + the caller's action bar, Cancel
//     labelled "Back";
//   - ResolutionChoiceStep: exclusive options, a disabled option, the note;
//   - CandidateList: single choice, the "Proposed" pill on the candidates the
//     CALLER's predicate marks (not necessarily the first one).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import AphoriqTheme from "../../_utils/aphoriqTheme";

import ResolutionFlow, {
  CandidateList,
  ResolutionChoiceStep,
} from "components/flows/ResolutionFlow";

afterEach(() => cleanup());

const wrap = (ui) => render(<AphoriqTheme>{ui}</AphoriqTheme>);

describe("ResolutionFlow (generic chassis)", () => {
  it("renders the steps, the content and the caller's bar (Back / save label)", () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();
    wrap(
      <ResolutionFlow
        steps={[{ key: "a", label: "Who" }, { key: "b", label: "Confirm" }]}
        activeStep={0}
        bar={{ onSave, onCancel, saveLabel: "Next", saveDisabled: false }}
        testId="the-flow"
      >
        <div>step content</div>
      </ResolutionFlow>,
    );
    const flow = screen.getByTestId("the-flow");
    expect(within(flow).getByText("Who")).toBeInTheDocument();
    expect(within(flow).getByText("step content")).toBeInTheDocument();
    fireEvent.click(within(flow).getByRole("button", { name: "Next" }));
    fireEvent.click(within(flow).getByRole("button", { name: "Back" }));
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});

describe("ResolutionChoiceStep", () => {
  it("offers the options, one disabled, with the note", () => {
    const onChoice = vi.fn();
    wrap(
      <ResolutionChoiceStep
        title="How?"
        options={[
          { value: "LINK", label: "Link" },
          { value: "CREATE", label: "Create", disabled: true },
        ]}
        choice={null}
        onChoice={onChoice}
        note="Why Create is off"
      />,
    );
    fireEvent.click(screen.getByLabelText("Link"));
    expect(onChoice).toHaveBeenCalledWith("LINK");
    expect(screen.getByLabelText("Create")).toBeDisabled();
    expect(screen.getByText("Why Create is off")).toBeInTheDocument();
  });
});

describe("CandidateList", () => {
  const candidates = [
    { id: "a", name: "Alice" },
    { id: "b", name: "Bob", proposed: true },
  ];

  it("marks « Proposed » with the caller's predicate, not by position", () => {
    wrap(
      <CandidateList
        title="Who is it?"
        candidates={candidates}
        selectedId="b"
        onSelect={vi.fn()}
        isProposed={(c) => Boolean(c.proposed)}
        renderCandidate={(c) => <span>{c.name}</span>}
        getAriaLabel={(c) => `Select ${c.name}`}
        candidateTestIdPrefix="cand-"
      />,
    );
    expect(within(screen.getByTestId("cand-a")).queryByText("Proposed")).not.toBeInTheDocument();
    expect(within(screen.getByTestId("cand-b")).getByText("Proposed")).toBeInTheDocument();
    expect(screen.getByLabelText("Select Bob")).toBeChecked();
  });

  it("a click on a radio or on the card selects the candidate", () => {
    const onSelect = vi.fn();
    wrap(
      <CandidateList
        title="Who is it?"
        candidates={candidates}
        selectedId="b"
        onSelect={onSelect}
        isProposed={() => false}
        renderCandidate={(c, select) => (
          <button type="button" onClick={select}>{`card ${c.name}`}</button>
        )}
        getAriaLabel={(c) => `Select ${c.name}`}
        candidateTestIdPrefix="cand-"
      />,
    );
    fireEvent.click(screen.getByLabelText("Select Alice"));
    fireEvent.click(screen.getByRole("button", { name: "card Bob" }));
    expect(onSelect).toHaveBeenNthCalledWith(1, "a");
    expect(onSelect).toHaveBeenNthCalledWith(2, "b");
  });

  it("shows the empty text when there is no candidate", () => {
    wrap(
      <CandidateList
        title="Who is it?"
        candidates={[]}
        onSelect={vi.fn()}
        isProposed={() => false}
        renderCandidate={() => null}
        getAriaLabel={() => ""}
        candidateTestIdPrefix="cand-"
        emptyText="Nobody yet"
      />,
    );
    expect(screen.getByText("Nobody yet")).toBeInTheDocument();
  });
});
