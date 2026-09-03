// frontend/src/components/signals/SignalDetailPanel.jsx
//
// B3.5.3 — the signal DETAIL, dé-coqué. This is the first real content injected
// into the single workspace drawer coque (WorkspaceDrawer). It is NOT a drawer:
// it owns no <Drawer> shell and no open/close chrome — callers inject it via
// openDrawer(<SignalDetailPanel signal=… />) and the coque provides the shell,
// the header and the close button (closeDrawer). Clicking another signal calls
// openDrawer again with a fresh panel: React reconciles the same component in
// place, so the content is REPLACED without the coque closing/reopening.
//
// It wraps the shared SignalDetailContent (unchanged) and keeps the only piece
// of behaviour that lived in the old SignalQuickDrawer: navigating to the origin
// activity (there is no activity drawer) closes the coque first, then routes to
// the canonical /activities/{id}.

"use client";

import PropTypes from "prop-types";
import { useRouter } from "next/navigation";

// Project imports
import SignalDetailContent from "components/signals/SignalDetailContent";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";

// ==============================|| SIGNAL DETAIL PANEL ||============================== //

export default function SignalDetailPanel({
  signal,
  signalType,
  onValidate,
  onReject,
  onEdit,
  onReopen,
  isLocked,
}) {
  const router = useRouter();
  const { closeDrawer } = useWorkspaceDrawer();

  if (!signal) return null;

  // Origin activity is navigated to (there is no activity drawer) — matches the
  // canonical /activities/{id} route. Close the coque first so it doesn't linger
  // over the destination.
  const openOriginActivity = (activityId) => {
    closeDrawer();
    router.push(`/activities/${activityId}`);
  };

  return (
    <SignalDetailContent
      signal={signal}
      signalType={signalType}
      onValidate={onValidate}
      onReject={onReject}
      onEdit={onEdit}
      onReopen={onReopen}
      onOpenActivity={openOriginActivity}
      isLocked={isLocked}
    />
  );
}

SignalDetailPanel.propTypes = {
  signal: PropTypes.object,
  signalType: PropTypes.string,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  onReopen: PropTypes.func,
  isLocked: PropTypes.bool,
};
