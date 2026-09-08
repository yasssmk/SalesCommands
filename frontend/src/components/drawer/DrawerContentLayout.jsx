// frontend/src/components/drawer/DrawerContentLayout.jsx
//
// SE-b — the SHARED scaffold for any drawer's injected content (edit activity
// today, a contact card tomorrow, …). It renders an INVARIANT structure:
//
//   - a bold h3 title at the top (themed);
//   - ONE content box grounded on the page background (background.default) with
//     radius lg + a hairline border — the single box that holds the field groups;
//   - a global Save / Cancel action row, right-aligned.
//
// It does NOT render the coque or the close cross — those belong to
// WorkspaceDrawer (CoqueHeader). The cross sits in that separate top strip
// (WorkspaceDrawer.jsx CoqueHeader, px:2 / py:1.5), so this title shares the same
// horizontal inset (the content box below the cross); pixel-aligning it onto the
// cross's own line would require changing the coque and is out of scope here.
//
// 100% theme tokens (radius / border / typography / spacing) — no hardcoded
// hex/px, no MainCard.

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  ReloadOutlined,
} from "@ant-design/icons";

// ==============================|| READ-SIGNAL ACTION BAR (UI-2) ||============================== //

// The single "read signal" action bar (rule 6): Edit (NEUTRE) · Reject (error
// outline) · Validate (success contained), gated by status; Reopen (neutral
// role kept from before) replaces Reject/Validate once the signal is REJECTED.
// Colours are theme ROLES only — never hardcoded. Shares position/size with the
// edit bar (flex-end, size small).
function ReadActionBar({ onEdit, onReject, onValidate, onReopen, status, isLocked, validateDisabled }) {
  const isPending = status === "PENDING";
  const isRejected = status === "REJECTED";
  return (
    <Box data-testid="drawer-actions" sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
      {!isLocked && (
        <Button
          variant="outlined"
          color="inherit"
          size="small"
          startIcon={<EditOutlined style={{ fontSize: 14 }} />}
          onClick={onEdit}
        >
          Edit
        </Button>
      )}
      {isPending && !isLocked && (
        <>
          <Button
            variant="outlined"
            color="error"
            size="small"
            startIcon={<CloseCircleOutlined style={{ fontSize: 14 }} />}
            onClick={onReject}
          >
            Reject
          </Button>
          <Tooltip title={validateDisabled ? "Complete missing fields before validating" : ""}>
            <span>
              <Button
                variant="contained"
                color="success"
                size="small"
                disabled={validateDisabled}
                startIcon={<CheckCircleOutlined style={{ fontSize: 14 }} />}
                onClick={onValidate}
              >
                Validate
              </Button>
            </span>
          </Tooltip>
        </>
      )}
      {isRejected && !isLocked && (
        <Button
          variant="outlined"
          size="small"
          startIcon={<ReloadOutlined style={{ fontSize: 14 }} />}
          onClick={onReopen}
        >
          Reopen
        </Button>
      )}
    </Box>
  );
}
ReadActionBar.propTypes = {
  onEdit: PropTypes.func,
  onReject: PropTypes.func,
  onValidate: PropTypes.func,
  onReopen: PropTypes.func,
  status: PropTypes.string,
  isLocked: PropTypes.bool,
  validateDisabled: PropTypes.bool,
};

export default function DrawerContentLayout({
  title,
  onSave,
  onCancel,
  saveDisabled = false,
  saveLabel = "Save",
  cancelLabel = "Cancel",
  readActions,
  children,
}) {
  const aq = useTheme().aphoriQ;

  return (
    <Stack spacing={2}>
      {/* Title is OPTIONAL: when the coque renders it in its header (Option A),
          the layout omits it to avoid a duplicate. */}
      {title ? (
        <Typography variant="h3" component="h2" sx={{ fontWeight: "bold" }} data-testid="drawer-title">
          {title}
        </Typography>
      ) : null}

      {/* The content box is OPTIONAL — a bar-only call (readActions with no
          children, e.g. the signal detail) renders just the action row. */}
      {children != null && (
        <Box
          data-testid="drawer-content-box"
          sx={{
            backgroundColor: "background.default",
            // Optional chaining keeps the shared box safe in theme-less render
            // contexts (e.g. the signal detail mounted bare in cluster-drawer tests).
            borderRadius: aq?.radius?.lg && `${aq.radius.lg}px`,
            border: aq?.border && `${aq.border.width.hairline}px solid ${aq.border.color}`,
            p: 2,
          }}
        >
          {children}
        </Box>
      )}

      {/* One action bar, two regimes:
          - read signal (readActions): Edit / Reject / Validate / Reopen;
          - edit (onSave/onCancel): Cancel / Save|Complete.
          A read-only content (e.g. the Contact fiche) passes none and gets the
          content alone. */}
      {readActions ? (
        <ReadActionBar {...readActions} />
      ) : (
        (onSave || onCancel) && (
          <Box data-testid="drawer-actions" sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
            {onCancel && (
              <Button variant="text" color="inherit" onClick={onCancel}>
                {cancelLabel}
              </Button>
            )}
            {onSave && (
              <Button variant="contained" onClick={onSave} disabled={saveDisabled}>
                {saveLabel}
              </Button>
            )}
          </Box>
        )
      )}
    </Stack>
  );
}

DrawerContentLayout.propTypes = {
  /** Optional bold h3 title. Omit when the coque renders the title (Option A). */
  title: PropTypes.string,
  /** Global save handler. Optional — omit (with onCancel) for a read-only
      content that wants no global action row. */
  onSave: PropTypes.func,
  /** Global cancel handler. Optional — see onSave. */
  onCancel: PropTypes.func,
  /** Disable the Save button (e.g. invalid or pristine form). */
  saveDisabled: PropTypes.bool,
  saveLabel: PropTypes.string,
  cancelLabel: PropTypes.string,
  /** Read-signal action bar (rule 6): { onEdit, onReject, onValidate, onReopen,
      status, isLocked, validateDisabled }. When set, the layout renders the read
      bar instead of the edit (Save/Cancel) bar. */
  readActions: PropTypes.shape({
    onEdit: PropTypes.func,
    onReject: PropTypes.func,
    onValidate: PropTypes.func,
    onReopen: PropTypes.func,
    status: PropTypes.string,
    isLocked: PropTypes.bool,
    validateDisabled: PropTypes.bool,
  }),
  /** The field groups (the single content box's children). */
  children: PropTypes.node,
};
