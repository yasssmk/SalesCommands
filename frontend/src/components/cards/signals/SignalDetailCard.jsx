// frontend/src/components/cards/signals/SignalDetailCard.jsx

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  UserOutlined,
  CalendarOutlined,
} from "@ant-design/icons";

// Project imports
import SignalStatusChip from "components/chips/SignalStatusChip";
import SignalTypeChip from "components/chips/SignalTypeChip";
import { getMissingFields } from "sections/activities/signals/signalValidationRules";
import SignalIncompleteAlert from "sections/activities/signals/SignalIncompleteAlert";
import {
  getTechSummary,
  getContact,
  formatContact,
  getNextStepSummary,
  formatSuggestedContacts,
  getPeopleSummary,
  getConstraintSummary,
} from "sections/activities/signals/utils/signalDisplay";

// ==============================|| HELPERS ||============================== //

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
  if (signalType === "next-steps") {
    return getNextStepSummary(signal);
  }
  if (signalType === "people") {
    return getPeopleSummary(signal);
  }
  if (signalType === "constraints") {
    return getConstraintSummary(signal);
  }
  return signal.summary || "—";
}

// ==============================|| SIGNAL DETAIL CARD ||============================== //

export default function SignalDetailCard({
  signal,
  signalType,
  onValidate,
  onReject,
  onEdit,
  isLocked,
}) {
  const isPending = signal.status === "PENDING";
  const isRejected = signal.status === "REJECTED";

  const missingFields = useMemo(
    () => (isPending ? getMissingFields(signal, signalType) : []),
    [signal, signalType, isPending],
  );

  const isNextStep = signalType === "next-steps";
  const isPeople = signalType === "people";
  const hasTheme = !isNextStep && !isPeople && Boolean(signal.what_display && signal.dimension_display);
  const contact = isNextStep ? null : isPeople ? null : getContact(signal);
  const contactName = isNextStep
    ? formatSuggestedContacts(signal.suggested_contacts)
    : isPeople
      ? formatContact(signal.target_contact)
      : formatContact(contact);
  const validateDisabled = missingFields.length > 0;

  return (
    <Box
      sx={{
        border: 1,
        borderColor: "divider",
        borderRadius: 1.5,
        p: 2.5,
        mb: 2,
        opacity: isRejected ? 0.5 : 1,
        transition: "opacity 0.15s",
      }}
    >
      {/* Header chips */}
      <Stack
        direction="row"
        spacing={0.75}
        alignItems="center"
        flexWrap="wrap"
        sx={{ mb: 1.5 }}
      >
        <SignalTypeChip signalType={signalType} size="small" />
        {hasTheme && (
          <Chip
            label={`${signal.what_display} × ${signal.dimension_display}`}
            size="small"
            variant="outlined"
          />
        )}
        {isPeople && signal.role_display && (
          <Chip label={signal.role_display} size="small" variant="outlined" />
        )}
        {isPeople && signal.influence_display && (
          <Chip label={signal.influence_display} size="small" variant="outlined" />
        )}
        {signalType === "constraints" && signal.rigidity_display && (
          <Chip label={signal.rigidity_display} size="small" variant="outlined" />
        )}
        <SignalStatusChip status={signal.status} size="small" />
      </Stack>

      {/* Incomplete alert (PENDING only) */}
      {isPending && missingFields.length > 0 && (
        <SignalIncompleteAlert missingFields={missingFields} />
      )}

      {/* Summary */}
      <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>
        {getSummary(signal, signalType)}
      </Typography>

      {/* Source quote */}
      {signal.source_quote && (
        <Box
          sx={{
            mb: 1.5,
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

      {/* Objective (next-steps) — what the proposed activity is for */}
      {isNextStep && signal.suggested_objective && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          {signal.suggested_objective}
        </Typography>
      )}

      {/* Contact */}
      {contactName && (
        <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mb: 1 }}>
          <UserOutlined style={{ fontSize: 13, color: "#8c8c8c" }} />
          <Typography variant="caption" color="text.secondary">
            {contactName}
          </Typography>
        </Stack>
      )}

      {/* Date */}
      {signal.created_at && (
        <Stack
          direction="row"
          spacing={0.5}
          alignItems="center"
          sx={{ mb: 1.5 }}
        >
          <CalendarOutlined style={{ fontSize: 13, color: "#8c8c8c" }} />
          <Typography variant="caption" color="text.secondary">
            Extracted: {formatDate(signal.created_at)}
          </Typography>
        </Stack>
      )}

      {/* Actions */}
      {!isLocked && (
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          <Button
            variant="outlined"
            size="small"
            startIcon={<EditOutlined style={{ fontSize: 14 }} />}
            onClick={() => onEdit?.(signal, signalType)}
          >
            Edit
          </Button>
          {isPending && (
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
      )}
    </Box>
  );
}

SignalDetailCard.propTypes = {
  signal: PropTypes.shape({
    id: PropTypes.string.isRequired,
    status: PropTypes.string.isRequired,
    summary: PropTypes.string,
    source_quote: PropTypes.string,
    what_display: PropTypes.string,
    dimension_display: PropTypes.string,
    created_at: PropTypes.string,
    contact: PropTypes.object,
    source_context: PropTypes.shape({
      contacts: PropTypes.arrayOf(PropTypes.object),
    }),
    tech_name: PropTypes.string,
    is_to_replace: PropTypes.bool,
    metadata: PropTypes.object,
  }).isRequired,
  signalType: PropTypes.oneOf([
    "pain",
    "objective",
    "impact",
    "tech-stack",
    "blockers",
    "next-steps",
    "people",
    "constraints",
  ]).isRequired,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  isLocked: PropTypes.bool,
};
