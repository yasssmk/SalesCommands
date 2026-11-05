// frontend/src/sections/activities/workspace/PersonSignalsContent.jsx
//
// Sprint « Cycle de vie des contacts », 8g-6 (TD-232 « See signals ») — the
// signals « from conversations with » a person: a contact OR a non-converted
// stakeholder, opened from its fiche (ContactDrawerContent) by « See signals ».
// Mounted only then, so the request leaves on that click, never before.
//   - the aggregated endpoint (useAggregatedSignals): the account scope + the
//     person filter (contact / stakeholder — the activities it took part in),
//     PENDING + VALIDATED (no rejected), the 8 qualification types
//     (QUALIFICATION_SIGNAL_TYPES — no next steps);
//   - the shared SignalsValidationList, READ-ONLY (no validate / reject);
//   - a click → the signal's detail, read-only, whose « Back » (like this
//     list's — the read bar's onBack) returns to the person's fiche.
// Honest wording: « from conversations with », never « said by ».

"use client";

import PropTypes from "prop-types";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import useAggregatedSignals from "api/signals/aggregatedSignals";
import { useGetSignalChoices } from "api/signals/signals";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import SignalsValidationList from "components/signals/SignalsValidationList";
import SignalDetailPanel from "components/signals/SignalDetailPanel";
import { SIGNAL_STATUS_PILL } from "components/signals/signalStatusPill";
import { getSignalTypeLabel, QUALIFICATION_SIGNAL_TYPES } from "utils/signalTypes";

export const PERSON_SIGNAL_STATUSES = ["PENDING", "VALIDATED"];

// THE label of the view (the coque title) — the honest wording.
export const personSignalsTitle = (name) => `Signals from conversations with ${name}`;

// The read-only detail (choices for its labels, as the Signals band's).
function PersonSignalDetail(props) {
  const { choices } = useGetSignalChoices();
  return <SignalDetailPanel {...props} choices={choices} />;
}

export default function PersonSignalsContent({
  accountId,
  contactId,
  stakeholderId,
  personName,
  currentActivityId,
  onBack,
}) {
  const { openDrawer } = useWorkspaceDrawer();
  const { signals, loading } = useAggregatedSignals({
    accountId,
    contact: contactId,
    stakeholder: stakeholderId,
    statuses: PERSON_SIGNAL_STATUSES,
    signalTypes: QUALIFICATION_SIGNAL_TYPES,
    pageSize: 100,
  });

  const openDetail = (signal, signalType) =>
    openDrawer(
      <PersonSignalDetail
        signal={signal}
        signalType={signalType}
        isLocked
        onBack={onBack}
        currentActivityId={currentActivityId}
        headerInCoque
      />,
      { title: getSignalTypeLabel(signalType), status: signal.status, statusMap: SIGNAL_STATUS_PILL },
    );

  return (
    <DrawerContentLayout readActions={{ onBack, isLocked: true }}>
      <SignalsValidationList
        signals={signals ?? []}
        loading={loading}
        onSelect={openDetail}
        emptyMessage={`No signals from conversations with ${personName}`}
      />
    </DrawerContentLayout>
  );
}

PersonSignalsContent.propTypes = {
  /** The account whose activities are read (the endpoint's scope). */
  accountId: PropTypes.string.isRequired,
  /** The person: a contact … */
  contactId: PropTypes.string,
  /** … or a non-converted stakeholder. */
  stakeholderId: PropTypes.string,
  /** Its name, for the wording. */
  personName: PropTypes.string.isRequired,
  /** The Activity the fiche was opened from (the detail's chassis gate). */
  currentActivityId: PropTypes.string,
  /** « Back » → the person's fiche. */
  onBack: PropTypes.func.isRequired,
};
