// frontend/src/sections/accounts/signals/wizard/sections/TechStackSection.jsx
/**
 * TechStackSection — wizard section for capturing TechStackSignals.
 *
 * Responsibilities:
 *   - Display list of staged tech stack signals with toggle VALIDATED / REJECTED
 *   - "+ Add Tech Stack" button reveals InlineTechStackForm inline
 *   - Calls onAdd(payload) to stage a new signal in the wizard
 *   - Calls onToggleStatus(_key) to flip a staged signal between VALIDATED / REJECTED
 *
 * Staged signal shape (managed by WizardSignalAdd):
 *   { _key: string, _status: 'VALIDATED'|'REJECTED', ...payload }
 *
 * choices is used locally to resolve category + satisfaction display labels.
 * tech_name is a free text field — displayed as-is.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo, useEffect } from "react";

// material-ui
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// ant-design icons
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import CloseCircleOutlined from "@ant-design/icons/CloseCircleOutlined";
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import InboxOutlined from "@ant-design/icons/InboxOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";

// project imports
import InlineTechStackForm from "../forms/InlineTechStackForm";

// ==============================|| HELPERS ||============================== //

/**
 * Resolve a display label from a choices array by value.
 *
 * @param {Array<{value: string, label: string}>} options
 * @param {string} value
 * @returns {string}
 */
function resolveLabel(options, value) {
  if (!value || !options) return value ?? "—";
  return options.find((o) => o.value === value)?.label ?? value;
}

// ==============================|| STAGED TECH STACK CARD ||============================== //

/**
 * StagedTechStackCard — displays a single staged TechStackSignal with a VALIDATED/REJECTED toggle.
 *
 * Primary display: tech_name (bold) + category chip + satisfaction chip.
 * usage shown truncated if present.
 */
function StagedTechStackCard({ signal, choices, onToggleStatus, onRemove }) {
  const isRejected = signal._status === "REJECTED";

  const categoryLabel = useMemo(
    () => resolveLabel(choices?.tech_categories, signal.category),
    [choices, signal.category],
  );

  const satisfactionLabel = useMemo(
    () => resolveLabel(choices?.satisfaction, signal.satisfaction),
    [choices, signal.satisfaction],
  );

  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: isRejected ? "error.light" : "primary.light",
        borderRadius: 1.5,
        p: 1.5,
        bgcolor: isRejected ? "error.lighter" : "primary.lighter",
        transition: "border-color 0.15s, background-color 0.15s",
        opacity: isRejected ? 0.75 : 1,
      }}
    >
      <Stack direction="row" spacing={1.5} alignItems="flex-start">
        {/* Content */}
        <Stack spacing={0.75} flex={1} minWidth={0}>
          {/* Tech name — primary identifier */}
          <Typography
            variant="body2"
            fontWeight={600}
            sx={{
              textDecoration: isRejected ? "line-through" : "none",
              color: isRejected ? "text.disabled" : "text.primary",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {signal.tech_name || "Unnamed tool"}
          </Typography>

          {/* Category + satisfaction chips */}
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {signal.category && (
              <Chip
                label={categoryLabel}
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.65rem", height: 20 }}
              />
            )}
            {signal.satisfaction && (
              <Chip
                label={satisfactionLabel}
                size="small"
                color={isRejected ? "default" : "primary"}
                variant="outlined"
                sx={{ fontSize: "0.65rem", height: 20 }}
              />
            )}
          </Stack>

          {/* Usage — truncated */}
          {signal.usage && (
            <Typography
              variant="caption"
              color={isRejected ? "text.disabled" : "text.secondary"}
              sx={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {signal.usage}
            </Typography>
          )}

          {/* Renewal date if set */}
          {signal.renewal_date && (
            <Typography variant="caption" color="text.secondary">
              Renewal: {signal.renewal_date}
            </Typography>
          )}
        </Stack>

        {/* Actions */}
        <Stack direction="row" spacing={0.5} alignItems="center" flexShrink={0}>
          <Button
            size="small"
            variant="outlined"
            color={isRejected ? "error" : "success"}
            onClick={() => onToggleStatus(signal._key)}
            startIcon={
              isRejected ? (
                <CloseCircleOutlined style={{ fontSize: 13 }} />
              ) : (
                <CheckCircleOutlined style={{ fontSize: 13 }} />
              )
            }
            sx={{ fontSize: "0.7rem", px: 1, py: 0.5 }}
          >
            {isRejected ? "Excluded" : "Include"}
          </Button>
          <IconButton
            size="small"
            onClick={() => onRemove(signal._key)}
            aria-label="Remove signal"
            sx={{ color: "text.disabled", "&:hover": { color: "error.main" } }}
          >
            <DeleteOutlined style={{ fontSize: 13 }} />
          </IconButton>
        </Stack>
      </Stack>
    </Box>
  );
}

StagedTechStackCard.propTypes = {
  signal: PropTypes.shape({
    _key: PropTypes.string.isRequired,
    _status: PropTypes.oneOf(["VALIDATED", "REJECTED"]).isRequired,
    summary: PropTypes.string,
    category: PropTypes.string,
    pain_level: PropTypes.string,
    business_cost: PropTypes.string,
  }).isRequired,
  choices: PropTypes.object,
  onToggleStatus: PropTypes.func.isRequired,
  onRemove: PropTypes.func.isRequired,
};

// ==============================|| EMPTY STATE ||============================== //

function EmptyState() {
  return (
    <Stack spacing={1} alignItems="center" py={4}>
      <InboxOutlined style={{ fontSize: 28, color: "#bfbfbf" }} />
      <Typography variant="body2" color="text.disabled" textAlign="center">
        No tech stack signals staged yet.
        <br />
        Click &ldquo;Add Tech Stack&rdquo; to capture one.
      </Typography>
    </Stack>
  );
}

// ==============================|| TECH STACK SECTION ||============================== //

/**
 * TechStackSection
 *
 * @param {Array}    stagedSignals    - Staged tech stack signals managed by WizardSignalAdd
 * @param {Function} onAdd            - (payload: Object) => void
 * @param {Function} onToggleStatus   - (_key: string) => void
 * @param {Object}   choices          - From useGetSignalChoices()
 * @param {boolean}  choicesLoading
 * @param {string}   accountId
 * @param {Object}   defaultContact   - Full contact object to pre-fill source_contact
 * @param {Function} onFormOpenChange  - Notifies the wizard when inline form opens/closes
 */
export default function TechStackSection({
  stagedSignals,
  onAdd,
  onToggleStatus,
  onRemove,
  choices,
  choicesLoading,
  accountId,
  defaultContact,
  onFormOpenChange,
  hasActivityContext,
}) {
  const [formOpen, setFormOpen] = useState(false);

  // Notify parent wizard when the inline form opens or closes
  useEffect(() => {
    onFormOpenChange?.(formOpen);
  }, [formOpen, onFormOpenChange]);

  const handleAdd = useCallback(
    (payload) => {
      onAdd(payload);
      setFormOpen(false);
    },
    [onAdd],
  );

  const handleCancel = useCallback(() => setFormOpen(false), []);

  const validatedCount = useMemo(
    () => stagedSignals.filter((s) => s._status === "VALIDATED").length,
    [stagedSignals],
  );

  // ==============================|| RENDER ||============================== //

  return (
    <Stack spacing={2}>
      {/* ---- No activity context warning ---- */}
      {!hasActivityContext && (
        <Alert severity="warning" sx={{ fontSize: "0.8rem" }}>
          Tech stack signals should be linked to a conversation. Open this
          wizard from an <strong>Activity</strong> to automatically attach them
          to a call or meeting.
        </Alert>
      )}

      {/* ---- Section header ---- */}
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="subtitle1" fontWeight={600}>
            Tech Stack Signals
          </Typography>
          {stagedSignals.length > 0 && (
            <Chip
              label={`${validatedCount} / ${stagedSignals.length}`}
              size="small"
              color={validatedCount > 0 ? "primary" : "default"}
              sx={{ height: 20, fontSize: "0.68rem" }}
            />
          )}
        </Stack>

        {/* Add button — hidden when form is already open */}
        {!formOpen && (
          <Button
            size="small"
            variant="outlined"
            color="primary"
            startIcon={<PlusOutlined style={{ fontSize: 12 }} />}
            onClick={() => setFormOpen(true)}
          >
            Add Tech Stack
          </Button>
        )}
      </Stack>

      {/* ---- Staged signals list ---- */}
      {stagedSignals.length === 0 && !formOpen && <EmptyState />}

      {stagedSignals.length > 0 && (
        <Stack spacing={1}>
          {stagedSignals.map((signal) => (
            <StagedTechStackCard
              key={signal._key}
              signal={signal}
              choices={choices}
              onToggleStatus={onToggleStatus}
              onRemove={onRemove}
            />
          ))}
        </Stack>
      )}

      {/* ---- Divider before form ---- */}
      {formOpen && stagedSignals.length > 0 && <Divider />}

      {/* ---- Inline form ---- */}
      {formOpen && (
        <InlineTechStackForm
          choices={choices}
          choicesLoading={choicesLoading}
          accountId={accountId}
          defaultContact={defaultContact}
          onAdd={handleAdd}
          onCancel={handleCancel}
        />
      )}
    </Stack>
  );
}

// ==============================|| PROP TYPES ||============================== //

TechStackSection.propTypes = {
  stagedSignals: PropTypes.arrayOf(
    PropTypes.shape({
      _key: PropTypes.string.isRequired,
      _status: PropTypes.oneOf(["VALIDATED", "REJECTED"]).isRequired,
      tech_name: PropTypes.string,
      category: PropTypes.string,
      satisfaction: PropTypes.string,
      usage: PropTypes.string,
      renewal_date: PropTypes.string,
    }),
  ).isRequired,
  onAdd: PropTypes.func.isRequired,
  onToggleStatus: PropTypes.func.isRequired,
  onRemove: PropTypes.func.isRequired,
  onFormOpenChange: PropTypes.func,
  hasActivityContext: PropTypes.bool,
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
  accountId: PropTypes.string.isRequired,
  defaultContact: PropTypes.object,
};
