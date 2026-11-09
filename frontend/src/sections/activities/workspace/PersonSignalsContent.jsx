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
//   - 8h: the inline type filter (InlinePillsFilter on
//     QUALIFICATION_TYPE_FILTER) — the chosen types go to the server
//     (signal_type, repeated, via toQueryParams); none chosen = the 8;
//   - the shared SignalsValidationList, READ-ONLY (no validate / reject);
//   - a click → the signal's detail, read-only. Back goes up ONE level at a
//     time (8g-6e): the detail's Back re-opens this list with its filter
//     state (initialFilters — the drawer has no stack: the onBack pattern of
//     ActivitySignalsTab), the list's Back re-opens the person's fiche.
// Honest wording: « from conversations with », never « said by ».

"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// MUI
import Stack from "@mui/material/Stack";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import useAggregatedSignals from "api/signals/aggregatedSignals";
import { useGetSignalChoices } from "api/signals/signals";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import SignalsValidationList from "components/signals/SignalsValidationList";
import SignalDetailPanel from "components/signals/SignalDetailPanel";
import { SIGNAL_STATUS_PILL } from "components/signals/signalStatusPill";
import InlinePillsFilter from "components/filters/InlinePillsFilter";
import { getSignalTypeLabel } from "utils/signalTypes";
import { toQueryParams } from "utils/filters/filterDefinitions";
import { QUALIFICATION_TYPE_FILTER } from "utils/filters/signalFilters";

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
  initialFilters,
}) {
  const { openDrawer } = useWorkspaceDrawer();
  const [filters, setFilters] = useState(() => initialFilters ?? { types: [] });
  const params = toQueryParams([QUALIFICATION_TYPE_FILTER], filters);
  const { signals, loading } = useAggregatedSignals({
    accountId,
    contact: contactId,
    stakeholder: stakeholderId,
    statuses: PERSON_SIGNAL_STATUSES,
    signalTypes: params.signal_type,
    pageSize: 100,
  });

  // The detail's Back: this list again, same person, same filters.
  const reopenList = () =>
    openDrawer(
      <PersonSignalsContent
        accountId={accountId}
        contactId={contactId}
        stakeholderId={stakeholderId}
        personName={personName}
        currentActivityId={currentActivityId}
        onBack={onBack}
        initialFilters={filters}
      />,
      { title: personSignalsTitle(personName) },
    );

  const openDetail = (signal, signalType) =>
    openDrawer(
      <PersonSignalDetail
        signal={signal}
        signalType={signalType}
        isLocked
        onBack={reopenList}
        currentActivityId={currentActivityId}
        headerInCoque
      />,
      { title: getSignalTypeLabel(signalType), status: signal.status, statusMap: SIGNAL_STATUS_PILL },
    );

  return (
    <DrawerContentLayout readActions={{ onBack, isLocked: true }}>
      <Stack spacing={2}>
        <InlinePillsFilter
          definition={QUALIFICATION_TYPE_FILTER}
          value={filters.types}
          onChange={(types) => setFilters((f) => ({ ...f, types }))}
        />
        <SignalsValidationList
          signals={signals ?? []}
          loading={loading}
          onSelect={openDetail}
          emptyMessage={`No signals from conversations with ${personName}`}
        />
      </Stack>
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
  /** The filter state to open with (the detail's Back restores it). */
  initialFilters: PropTypes.shape({ types: PropTypes.arrayOf(PropTypes.string) }),
};
