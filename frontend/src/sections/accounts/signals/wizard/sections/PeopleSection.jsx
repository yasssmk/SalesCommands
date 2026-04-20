// frontend/src/sections/accounts/signals/wizard/sections/PeopleSection.jsx
/**
 * PeopleSection — wizard section for capturing PeopleSignals.
 *
 * Responsibilities:
 *   - Display list of staged people signals with toggle VALIDATED / REJECTED
 *   - "+ Add People" button reveals InlinePeopleForm inline
 *   - Calls onAdd(payload) to stage a new signal in the wizard
 *   - Calls onToggleStatus(_key) to flip a staged signal between VALIDATED / REJECTED
 *
 * Staged signal shape (managed by WizardSignalAdd):
 *   { _key: string, _status: 'VALIDATED'|'REJECTED', ...payload }
 *
 * choices is used locally to resolve role + influence_level display labels.
 * target_contact is a UUID — not resolved to a name in the card (no fetch at this level).
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo, useEffect } from "react";

// material-ui
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
import InlinePeopleForm from "../forms/InlinePeopleForm";
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

// ==============================|| STAGED PEOPLE CARD ||============================== //

/**
 * StagedPeopleCard — displays a single staged PeopleSignal with a VALIDATED/REJECTED toggle.
 *
 * Primary display: role label (bold) + influence level chip.
 * Notes shown truncated if present.
 */
function StagedPeopleCard({
  signal,
  choices,
  onToggleStatus,
  onEdit,
  onRemove,
}) {
  const isRejected = signal._status === "REJECTED";

  const roleLabel = useMemo(
    () => resolveLabel(choices?.people_roles, signal.role),
    [choices, signal.role],
  );

  const influenceLabel = useMemo(
    () => resolveLabel(choices?.influence_levels, signal.influence_level),
    [choices, signal.influence_level],
  );

  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: isRejected ? "error.light" : "secondary.light",
        borderRadius: 1.5,
        p: 1.5,
        bgcolor: isRejected ? "error.lighter" : "secondary.lighter",
        transition: "border-color 0.15s, background-color 0.15s",
        opacity: isRejected ? 0.75 : 1,
      }}
    >
      <Stack direction="row" spacing={1.5} alignItems="flex-start">
        {/* Content */}
        <Stack spacing={0.75} flex={1} minWidth={0}>
          {/* Role — primary identifier */}
          <Typography
            variant="body2"
            fontWeight={600}
            sx={{
              textDecoration: isRejected ? "line-through" : "none",
              color: isRejected ? "text.disabled" : "text.primary",
            }}
          >
            {roleLabel || "—"}
          </Typography>

          {/* Influence level chip */}
          {signal.influence_level && (
            <Box>
              <Chip
                label={influenceLabel}
                size="small"
                color={isRejected ? "default" : "secondary"}
                variant="outlined"
                sx={{ fontSize: "0.65rem", height: 20 }}
              />
            </Box>
          )}

          {/* Notes — truncated */}
          {signal.notes && (
            <Typography
              variant="caption"
              color={isRejected ? "text.disabled" : "text.secondary"}
              sx={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {signal.notes}
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

StagedPeopleCard.propTypes = {
  signal: PropTypes.shape({
    _key: PropTypes.string.isRequired,
    _status: PropTypes.oneOf(["VALIDATED", "REJECTED"]).isRequired,
    role: PropTypes.string,
    influence_level: PropTypes.string,
    notes: PropTypes.string,
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
        No people signals staged yet.
        <br />
        Click &ldquo;Add People&rdquo; to capture one.
      </Typography>
    </Stack>
  );
}

// ==============================|| PEOPLE SECTION ||============================== //

/**
 * PeopleSection
 *
 * @param {Array}    stagedSignals    - Staged people signals managed by WizardSignalAdd
 * @param {Function} onAdd            - (payload: Object) => void
 * @param {Function} onToggleStatus   - (_key: string) => void
 * @param {Object}   choices          - From useGetSignalChoices()
 * @param {boolean}  choicesLoading
 * @param {string}   accountId
 * @param {Object}   defaultContact   - Full contact object to pre-fill source_contact
 * @param {Function} onFormOpenChange  - Notifies the wizard when inline form opens/closes
 */
export default function PeopleSection({
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
      editingSignal ? buildEditInitialValues("people", editingSignal) : null,
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
      {/* ---- Section header ---- */}
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="subtitle1" fontWeight={600}>
            People Signals
          </Typography>
          {stagedSignals.length > 0 && (
            <Chip
              label={`${validatedCount} / ${stagedSignals.length}`}
              size="small"
              color={validatedCount > 0 ? "secondary" : "default"}
              sx={{ height: 20, fontSize: "0.68rem" }}
            />
          )}
        </Stack>

        {/* Add button — hidden when any form (create or edit) is open */}
        {!isFormVisible && (
          <Button
            size="small"
            variant="outlined"
            color="secondary"
            startIcon={<PlusOutlined style={{ fontSize: 12 }} />}
            onClick={() => setFormOpen(true)}
          >
            Add People
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
              <InlinePeopleForm
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
              <StagedPeopleCard
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
        <InlinePeopleForm
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

PeopleSection.propTypes = {
  stagedSignals: PropTypes.arrayOf(
    PropTypes.shape({
      _key: PropTypes.string.isRequired,
      _status: PropTypes.oneOf(["VALIDATED", "REJECTED"]).isRequired,
      role: PropTypes.string,
      influence_level: PropTypes.string,
      notes: PropTypes.string,
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
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
  accountId: PropTypes.string.isRequired,
  defaultContact: PropTypes.object,
};
