// frontend/src/sections/accounts/signals/wizard/sections/PainSection.jsx
/**
 * PainSection — wizard section for capturing PainSignals.
 *
 * Responsibilities:
 *   - Display list of staged pain signals with toggle VALIDATED / REJECTED
 *   - "+ Add Pain" button reveals InlinePainForm inline
 *   - Calls onAdd(payload) to stage a new signal in the wizard
 *   - Calls onToggleStatus(_key) to flip a staged signal between VALIDATED / REJECTED
 *
 * Staged signal shape (managed by WizardSignalAdd):
 *   { _key: string, _status: 'VALIDATED'|'REJECTED', ...payload }
 *
 * choices is used locally to resolve category + pain_level display labels.
 * The payload itself only stores raw values — no display metadata.
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
import EditOutlined from "@ant-design/icons/EditOutlined";
import InboxOutlined from "@ant-design/icons/InboxOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";

// project imports
import InlinePainForm from "../forms/InlinePainForm";
import { buildEditInitialValues } from "../forms/buildEditInitialValues";

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

// ==============================|| STAGED PAIN CARD ||============================== //

/**
 * StagedPainCard — displays a single staged PainSignal with a VALIDATED/REJECTED toggle.
 *
 * Card border turns error color when REJECTED.
 * Toggle button flips the status — no confirmation needed.
 */
function StagedPainCard({ signal, choices, onToggleStatus, onEdit, onRemove }) {
  const isRejected = signal._status === "REJECTED";

  const categoryLabel = useMemo(
    () => resolveLabel(choices?.pain_categories, signal.category),
    [choices, signal.category],
  );

  const painLevelLabel = useMemo(
    () => resolveLabel(choices?.pain_levels, signal.pain_level),
    [choices, signal.pain_level],
  );

  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: isRejected ? "error.light" : "success.light",
        borderRadius: 1.5,
        p: 1.5,
        bgcolor: isRejected ? "error.lighter" : "success.lighter",
        transition: "border-color 0.15s, background-color 0.15s",
        opacity: isRejected ? 0.75 : 1,
      }}
    >
      <Stack direction="row" spacing={1.5} alignItems="flex-start">
        {/* Content */}
        <Stack spacing={0.75} flex={1} minWidth={0}>
          {/* Summary */}
          <Typography
            variant="body2"
            fontWeight={600}
            sx={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              textDecoration: isRejected ? "line-through" : "none",
              color: isRejected ? "text.disabled" : "text.primary",
            }}
          >
            {signal.summary || "—"}
          </Typography>

          {/* Category + pain level chips */}
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {signal.category && (
              <Chip
                label={categoryLabel}
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.65rem", height: 20 }}
              />
            )}
            {signal.pain_level && (
              <Chip
                label={painLevelLabel}
                size="small"
                color={isRejected ? "default" : "error"}
                variant="outlined"
                sx={{ fontSize: "0.65rem", height: 20 }}
              />
            )}
          </Stack>

          {/* Business cost if set */}
          {signal.business_cost && (
            <Typography variant="caption" color="text.secondary">
              Cost: {signal.business_cost}
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
            onClick={() => onEdit(signal._key)}
            aria-label="Edit signal"
            sx={{
              color: "text.disabled",
              "&:hover": { color: "primary.main" },
            }}
          >
            <EditOutlined style={{ fontSize: 13 }} />
          </IconButton>
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

StagedPainCard.propTypes = {
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
  onEdit: PropTypes.func.isRequired,
  onRemove: PropTypes.func.isRequired,
};

// ==============================|| EMPTY STATE ||============================== //

function EmptyState() {
  return (
    <Stack spacing={1} alignItems="center" py={4}>
      <InboxOutlined style={{ fontSize: 28, color: "#bfbfbf" }} />
      <Typography variant="body2" color="text.disabled" textAlign="center">
        No pain signals staged yet.
        <br />
        Click &ldquo;Add Pain&rdquo; to capture one.
      </Typography>
    </Stack>
  );
}

// ==============================|| PAIN SECTION ||============================== //

/**
 * PainSection
 *
 * @param {Array}    stagedSignals    - Staged pain signals managed by WizardSignalAdd
 * @param {Function} onAdd            - (payload: Object) => void
 * @param {Function} onToggleStatus   - (_key: string) => void
 * @param {Object}   choices          - From useGetSignalChoices()
 * @param {boolean}  choicesLoading
 * @param {string}   accountId
 * @param {Object}   defaultContact   - Full contact object to pre-fill source_contact
 * @param {Function} onFormOpenChange  - Notifies the wizard when inline form opens/closes
 */
export default function PainSection({
  stagedSignals,
  onAdd,
  onToggleStatus,
  onEdit,
  onUpdate,
  onRemove,
  editingKey,
  onCancelEdit,
  choices,
  choicesLoading,
  accountId,
  defaultContact,
  onFormOpenChange,
  hasActivityContext,
}) {
  const [formOpen, setFormOpen] = useState(false);

  const isEditMode = editingKey != null;
  const isFormVisible = formOpen || isEditMode;

  // Notify parent wizard when any form (create OR edit) is visible
  useEffect(() => {
    onFormOpenChange?.(isFormVisible);
  }, [isFormVisible, onFormOpenChange]);

  // Find the staged signal being edited — stable reference for initialValues
  const editingSignal = useMemo(
    () =>
      isEditMode
        ? (stagedSignals.find((s) => s._key === editingKey) ?? null)
        : null,
    [isEditMode, editingKey, stagedSignals],
  );

  // Pre-fill the inline form when entering edit mode
  const editInitialValues = useMemo(
    () =>
      editingSignal ? buildEditInitialValues("pain", editingSignal) : null,
    [editingSignal],
  );

  const handleAdd = useCallback(
    (payload) => {
      onAdd(payload);
      setFormOpen(false);
    },
    [onAdd],
  );

  const handleUpdate = useCallback(
    (payload) => {
      if (editingKey) onUpdate(editingKey, payload);
    },
    [onUpdate, editingKey],
  );

  const handleCancel = useCallback(() => {
    if (isEditMode) {
      onCancelEdit?.();
    } else {
      setFormOpen(false);
    }
  }, [isEditMode, onCancelEdit]);

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
          Pain signals should be linked to a conversation. Open this wizard from
          an <strong>Activity</strong> to automatically attach them to a call or
          meeting.
        </Alert>
      )}

      {/* ---- Section header ---- */}
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="subtitle1" fontWeight={600}>
            Pain Signals
          </Typography>
          {stagedSignals.length > 0 && (
            <Chip
              label={`${validatedCount} / ${stagedSignals.length}`}
              size="small"
              color={validatedCount > 0 ? "error" : "default"}
              sx={{ height: 20, fontSize: "0.68rem" }}
            />
          )}
        </Stack>

        {/* Add button — hidden when any form (create or edit) is open */}
        {!isFormVisible && (
          <Button
            size="small"
            variant="outlined"
            color="error"
            startIcon={<PlusOutlined style={{ fontSize: 12 }} />}
            onClick={() => setFormOpen(true)}
          >
            Add Pain
          </Button>
        )}
      </Stack>

      {/* ---- Staged signals list ---- */}
      {stagedSignals.length === 0 && !isFormVisible && <EmptyState />}

      {stagedSignals.length > 0 && (
        <Stack spacing={1}>
          {stagedSignals.map((signal) =>
            // In edit mode, the edited signal is replaced inline by the form
            isEditMode && signal._key === editingKey ? (
              <InlinePainForm
                key={signal._key}
                choices={choices}
                choicesLoading={choicesLoading}
                accountId={accountId}
                defaultContact={defaultContact}
                onAdd={handleUpdate}
                onCancel={handleCancel}
                initialValues={editInitialValues}
                submitLabel="Save changes"
              />
            ) : (
              <StagedPainCard
                key={signal._key}
                signal={signal}
                choices={choices}
                onToggleStatus={onToggleStatus}
                onEdit={onEdit}
                onRemove={onRemove}
              />
            ),
          )}
        </Stack>
      )}

      {/* ---- Divider before create form ---- */}
      {formOpen && stagedSignals.length > 0 && <Divider />}

      {/* ---- Inline form for CREATE (edit form is rendered inside the list above) ---- */}
      {formOpen && (
        <InlinePainForm
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

PainSection.propTypes = {
  stagedSignals: PropTypes.arrayOf(
    PropTypes.shape({
      _key: PropTypes.string.isRequired,
      _status: PropTypes.oneOf(["VALIDATED", "REJECTED"]).isRequired,
      summary: PropTypes.string,
      category: PropTypes.string,
      pain_level: PropTypes.string,
      business_cost: PropTypes.string,
    }),
  ).isRequired,
  onAdd: PropTypes.func.isRequired,
  onToggleStatus: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onUpdate: PropTypes.func.isRequired,
  onRemove: PropTypes.func.isRequired,
  editingKey: PropTypes.string,
  onCancelEdit: PropTypes.func,
  onFormOpenChange: PropTypes.func,
  hasActivityContext: PropTypes.bool,
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
  accountId: PropTypes.string.isRequired,
  defaultContact: PropTypes.object,
};
