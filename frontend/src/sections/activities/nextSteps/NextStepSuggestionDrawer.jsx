// frontend/src/sections/activities/nextSteps/NextStepSuggestionDrawer.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import {
  CloseOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  EyeOutlined,
  RobotOutlined,
} from "@ant-design/icons";

// Project imports
import DrawerFieldRow from "components/display/DrawerFieldRow";
import DrawerSection from "components/display/DrawerSection";
import SignalStatusChip from "components/chips/SignalStatusChip";
import { ACTIVITY_TYPE_LABELS } from "api/accounts/activities";

const DRAWER_WIDTH = 400;

function formatDate(dateStr) {
  if (!dateStr) return null;
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function formatContacts(contacts) {
  if (!contacts || contacts.length === 0) return null;
  return contacts
    .map((c) => `${c.first_name || ""} ${c.last_name || ""}`.trim())
    .filter(Boolean)
    .join(" · ");
}

// ==============================|| NEXT STEP SUGGESTION DRAWER ||============================== //

export default function NextStepSuggestionDrawer({
  open,
  signal,
  onClose,
  onConvert,
  onReject,
  onEdit,
  onViewActivity,
  isLocked,
}) {
  if (!signal) return null;

  const isPending = signal.status === "PENDING";
  const isValidated = signal.status === "VALIDATED";
  const isRejected = signal.status === "REJECTED";
  const linked = signal.linked_activity;
  const contactsText = formatContacts(signal.suggested_contacts);

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: { width: DRAWER_WIDTH, p: 0 },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 2.5,
          py: 2,
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip
            icon={<RobotOutlined style={{ fontSize: 12 }} />}
            label="AI Suggestion"
            size="small"
            color="warning"
            variant="outlined"
            sx={{ height: 22 }}
          />
          <SignalStatusChip status={signal.status} size="small" />
        </Stack>
        <IconButton size="small" onClick={onClose} aria-label="Close drawer">
          <CloseOutlined style={{ fontSize: 14 }} />
        </IconButton>
      </Box>

      <Divider />

      {/* Body */}
      <Box sx={{ px: 2.5, py: 2, flex: 1, overflow: "auto" }}>
        {/* Title */}
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
          {signal.suggested_title || "Untitled suggestion"}
        </Typography>

        {/* Suggestion details */}
        <DrawerSection title="SUGGESTION">
          <DrawerFieldRow
            label="Activity type"
            value={
              ACTIVITY_TYPE_LABELS[signal.suggested_activity_type] ||
              signal.suggested_activity_type_display ||
              signal.suggested_activity_type
            }
          />
          <DrawerFieldRow
            label="Due date"
            value={formatDate(signal.suggested_due_date)}
          />
        </DrawerSection>

        {/* Contacts */}
        {contactsText && (
          <DrawerSection title="SUGGESTED CONTACTS">
            <DrawerFieldRow label="Contacts" value={contactsText} />
          </DrawerSection>
        )}

        {/* Source */}
        {signal.source_quote && (
          <DrawerSection title="SOURCE">
            <Box
              sx={{
                p: 1.5,
                bgcolor: "grey.50",
                borderRadius: 1,
                borderLeft: 3,
                borderColor: "primary.main",
              }}
            >
              <Typography
                variant="body2"
                sx={{ fontStyle: "italic" }}
                color="text.secondary"
              >
                &ldquo;{signal.source_quote}&rdquo;
              </Typography>
            </Box>
          </DrawerSection>
        )}

        {/* Notes */}
        {signal.notes && (
          <DrawerSection title="NOTES">
            <Typography variant="body2">{signal.notes}</Typography>
          </DrawerSection>
        )}

        {/* Linked activity */}
        {linked && (
          <DrawerSection title="LINKED ACTIVITY">
            <DrawerFieldRow label="Title" value={linked.title} />
            <DrawerFieldRow
              label="Type"
              value={linked.activity_type_display}
            />
            <DrawerFieldRow
              label="Status"
              value={linked.status_display}
            />
            <DrawerFieldRow
              label="Date"
              value={formatDate(linked.scheduled_date)}
            />
          </DrawerSection>
        )}
      </Box>

      <Divider />

      {/* Actions */}
      <Box sx={{ px: 2.5, py: 2 }}>
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          {!isLocked && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<EditOutlined style={{ fontSize: 14 }} />}
              onClick={() => onEdit?.(signal)}
            >
              Edit
            </Button>
          )}
          {isPending && !isLocked && (
            <>
              <Button
                variant="outlined"
                size="small"
                color="error"
                startIcon={<CloseCircleOutlined style={{ fontSize: 14 }} />}
                onClick={() => onReject?.(signal)}
              >
                Reject
              </Button>
              <Button
                variant="contained"
                size="small"
                color="primary"
                startIcon={<CheckCircleOutlined style={{ fontSize: 14 }} />}
                onClick={() => onConvert?.(signal)}
              >
                Convert to Activity
              </Button>
            </>
          )}
          {isValidated && linked && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<EyeOutlined style={{ fontSize: 14 }} />}
              onClick={() => onViewActivity?.(linked)}
            >
              View Activity
            </Button>
          )}
        </Stack>
      </Box>
    </Drawer>
  );
}

// ==============================|| PROP TYPES ||============================== //

NextStepSuggestionDrawer.propTypes = {
  open: PropTypes.bool.isRequired,
  signal: PropTypes.shape({
    id: PropTypes.string,
    status: PropTypes.string,
    suggested_title: PropTypes.string,
    suggested_activity_type: PropTypes.string,
    suggested_activity_type_display: PropTypes.string,
    suggested_due_date: PropTypes.string,
    suggested_contacts: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.string,
        first_name: PropTypes.string,
        last_name: PropTypes.string,
      }),
    ),
    source_quote: PropTypes.string,
    notes: PropTypes.string,
    linked_activity: PropTypes.shape({
      id: PropTypes.string,
      title: PropTypes.string,
      activity_type_display: PropTypes.string,
      status_display: PropTypes.string,
      scheduled_date: PropTypes.string,
    }),
  }),
  onClose: PropTypes.func.isRequired,
  onConvert: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  onViewActivity: PropTypes.func,
  isLocked: PropTypes.bool,
};
