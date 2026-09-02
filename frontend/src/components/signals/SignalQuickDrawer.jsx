// frontend/src/components/signals/SignalQuickDrawer.jsx
//
// Single-signal drawer used across the flat views and the grouped tech/blocker
// sections. It is a thin themed MUI Drawer shell around the shared
// SignalDetailContent (header chips + close, body, and the lifecycle actions).
// The same content renders inside the cluster drawer's signal view (C5) so the
// two never stack.

"use client";

import PropTypes from "prop-types";
import { useRouter } from "next/navigation";

// MUI
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";

// Icons
import { CloseOutlined } from "@ant-design/icons";

// Project imports
import SignalDetailContent from "components/signals/SignalDetailContent";

const DRAWER_WIDTH = 400;

// ==============================|| SIGNAL QUICK DRAWER ||============================== //

export default function SignalQuickDrawer({
  open,
  signal,
  signalType,
  onClose,
  onValidate,
  onReject,
  onEdit,
  onReopen,
  isLocked,
}) {
  const router = useRouter();

  if (!signal) return null;

  // Origin activity is navigated to (there is no activity drawer) — matches
  // the canonical /activities/{id} route used across the app.
  const openOriginActivity = (activityId) => {
    onClose?.();
    router.push(`/activities/${activityId}`);
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { width: DRAWER_WIDTH, p: 0 } }}
    >
      <SignalDetailContent
        signal={signal}
        signalType={signalType}
        onValidate={onValidate}
        onReject={onReject}
        onEdit={onEdit}
        onReopen={onReopen}
        onOpenActivity={openOriginActivity}
        isLocked={isLocked}
        trailingAction={
          <IconButton size="small" onClick={onClose} aria-label="Close drawer">
            <CloseOutlined style={{ fontSize: 14 }} />
          </IconButton>
        }
      />
    </Drawer>
  );
}

SignalQuickDrawer.propTypes = {
  open: PropTypes.bool.isRequired,
  signal: PropTypes.object,
  signalType: PropTypes.string,
  onClose: PropTypes.func.isRequired,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  onReopen: PropTypes.func,
  isLocked: PropTypes.bool,
};
