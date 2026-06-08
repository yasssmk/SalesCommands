// frontend/src/sections/activities/signals/SignalQuickDrawer.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  CloseOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  UserOutlined,
  CalendarOutlined,
} from "@ant-design/icons";

// Project imports
import SignalTypeChip from "components/chips/SignalTypeChip";
import SignalStatusChip from "components/chips/SignalStatusChip";
import { getMissingFields } from "./signalValidationRules";
import SignalIncompleteAlert from "./SignalIncompleteAlert";
import {
  getTechSummary,
  getContact,
  formatContact,
} from "./utils/signalDisplay";

const DRAWER_WIDTH = 400;

function formatDate(dateStr) {
  if (!dateStr) return null;
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

function getSummary(signal, signalType) {
  if (signalType === "tech-stack") {
    return getTechSummary(signal).name;
  }
  return signal.summary || "—";
}

// ==============================|| SIGNAL QUICK DRAWER ||============================== //

export default function SignalQuickDrawer({
  open,
  signal,
  signalType,
  onClose,
  onValidate,
  onReject,
  onEdit,
  isLocked,
}) {
  if (!signal) return null;

  const isPending = signal.status === "PENDING";
  const contact = getContact(signal);
  const contactName = formatContact(contact);
  const missingFields = isPending
    ? getMissingFields(signal, signalType)
    : [];
  const validateDisabled = missingFields.length > 0;

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
          <SignalTypeChip signalType={signalType} size="small" />
          <SignalStatusChip status={signal.status} size="small" />
        </Stack>
        <IconButton size="small" onClick={onClose} aria-label="Close drawer">
          <CloseOutlined style={{ fontSize: 14 }} />
        </IconButton>
      </Box>

      <Divider />

      {/* Body */}
      <Box sx={{ px: 2.5, py: 2, flex: 1, overflow: "auto" }}>
        {/* Incomplete alert */}
        <SignalIncompleteAlert missingFields={missingFields} />

        {/* Summary */}
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
          {getSummary(signal, signalType)}
        </Typography>

        {/* Theme (qualification signals only) */}
        {signal.what_display && signal.dimension_display && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Theme
            </Typography>
            <Typography variant="body2">
              {signal.what_display} × {signal.dimension_display}
            </Typography>
          </Box>
        )}

        {/* Source quote */}
        {signal.source_quote && (
          <Box
            sx={{
              mb: 2,
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
        )}

        {/* Contact */}
        {contactName && (
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
            <UserOutlined style={{ fontSize: 14, color: "#8c8c8c" }} />
            <Typography variant="body2" color="text.secondary">
              {contactName}
            </Typography>
          </Stack>
        )}

        {/* Extraction date */}
        {signal.created_at && (
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            sx={{ mb: 1.5 }}
          >
            <CalendarOutlined style={{ fontSize: 14, color: "#8c8c8c" }} />
            <Typography variant="body2" color="text.secondary">
              Extracted: {formatDate(signal.created_at)}
            </Typography>
          </Stack>
        )}

        {/* Source */}
        {signal.source && (
          <Box sx={{ mb: 1.5 }}>
            <Typography variant="caption" color="text.secondary">
              Source
            </Typography>
            <Typography variant="body2">{signal.source}</Typography>
          </Box>
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
              onClick={() => onEdit?.(signal, signalType)}
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
                onClick={() => onReject?.(signal, signalType)}
              >
                Reject
              </Button>
              <Tooltip
                title={
                  validateDisabled
                    ? "Complete missing fields before validating"
                    : ""
                }
              >
                <span>
                  <Button
                    variant="contained"
                    size="small"
                    color="success"
                    disabled={validateDisabled}
                    startIcon={
                      <CheckCircleOutlined style={{ fontSize: 14 }} />
                    }
                    onClick={() => onValidate?.(signal, signalType)}
                  >
                    Validate
                  </Button>
                </span>
              </Tooltip>
            </>
          )}
        </Stack>
      </Box>
    </Drawer>
  );
}

SignalQuickDrawer.propTypes = {
  open: PropTypes.bool.isRequired,
  signal: PropTypes.shape({
    id: PropTypes.string,
    status: PropTypes.string,
    summary: PropTypes.string,
    source_quote: PropTypes.string,
    what_display: PropTypes.string,
    dimension_display: PropTypes.string,
    created_at: PropTypes.string,
    source: PropTypes.string,
    contact: PropTypes.object,
    source_context: PropTypes.shape({
      contacts: PropTypes.arrayOf(PropTypes.object),
    }),
    tech_catalog_entry: PropTypes.object,
  }),
  signalType: PropTypes.string,
  onClose: PropTypes.func.isRequired,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  isLocked: PropTypes.bool,
};
