// frontend/src/components/signals/SignalEditDrawer.jsx
//
// Unified signal edit surface — a themed right-anchored Drawer that replaces
// the two duplicated SignalEditDialog modals (activities + accounts).
//
// The two former copies diverged for ONE real reason: the source fields.
//   - context="activity": the signal is born from a known activity, so the
//     source is IMPLICIT — the activity form set surfaces no source picker.
//   - context="account": there is no implicit activity, so the account form
//     set surfaces required source_activity + source_contact pickers, and the
//     submit payload's source_contact (a full object) must be normalized to a
//     UUID.
// This drawer mounts the correct form set per (context, type) and normalizes
// accordingly. The two wizard/forms trees are reused as-is; their dedup is
// tracked as separate tech debt.
//
// Base behaviour is the activities copy (superset): 6 types + reopen +
// SignalIncompleteAlert.

"use client";

import PropTypes from "prop-types";
import { useMemo, useCallback, useState } from "react";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// ant-design icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import { UndoOutlined } from "@ant-design/icons";

// project imports
import { updateSignal, reopenSignal } from "api/signals/signals";
import {
  displayErrorSnackbar,
  displaySuccessSnackbar,
} from "utils/displayError";
import { getMissingFields } from "sections/activities/signals/signalValidationRules";
import SignalIncompleteAlert from "components/signals/SignalIncompleteAlert";

// --- Activity form tree (implicit source; the superset of types) ---
import { buildEditInitialValues as buildActivityInitialValues } from "sections/activities/signals/wizard/forms/buildEditInitialValues";
import ActInlinePainForm from "sections/activities/signals/wizard/forms/InlinePainForm";
import ActInlineObjectiveForm from "sections/activities/signals/wizard/forms/InlineObjectiveForm";
import ActInlineImpactForm from "sections/activities/signals/wizard/forms/InlineImpactForm";
import ActInlineTechStackForm from "sections/activities/signals/wizard/forms/InlineTechStackForm";
import BlockerEditForm from "sections/activities/signals/BlockerEditForm";
import NextStepEditForm from "sections/activities/signals/NextStepEditForm";

// --- Account form tree (explicit source pickers) — only the 3 types that
//     have a source-picker variant. Other types fall back to the activity tree. ---
import { buildEditInitialValues as buildAccountInitialValues } from "sections/accounts/signals/wizard/forms/buildEditInitialValues";
import AccInlinePainForm from "sections/accounts/signals/wizard/forms/InlinePainForm";
import AccInlineObjectiveForm from "sections/accounts/signals/wizard/forms/InlineObjectiveForm";
import AccInlineTechStackForm from "sections/accounts/signals/wizard/forms/InlineTechStackForm";

// ==============================|| TYPE CONFIG ||============================== //

const TYPE_LABELS = {
  pain: "Pain Signal",
  objective: "Objective Signal",
  impact: "Impact Signal",
  "tech-stack": "Tech Stack Signal",
  blockers: "Blocker Signal",
  "next-steps": "Next Step Suggestion",
};

// Activity tree covers all 6 types.
const ACTIVITY_FORMS = {
  pain: ActInlinePainForm,
  objective: ActInlineObjectiveForm,
  impact: ActInlineImpactForm,
  "tech-stack": ActInlineTechStackForm,
  blockers: BlockerEditForm,
  "next-steps": NextStepEditForm,
};

// In account context these three types swap to the explicit-source form; every
// other type has no account variant and keeps the activity form.
const ACCOUNT_FORMS = {
  pain: AccInlinePainForm,
  objective: AccInlineObjectiveForm,
  "tech-stack": AccInlineTechStackForm,
};

/**
 * Resolve the form component + its initial-values builder for a (context, type).
 * Account context uses the explicit-source form + builder for its three
 * supported types; everything else falls back to the activity tree.
 */
function resolveForm(context, signalType) {
  if (context === "account" && ACCOUNT_FORMS[signalType]) {
    return {
      Form: ACCOUNT_FORMS[signalType],
      buildInitialValues: buildAccountInitialValues,
    };
  }
  return {
    Form: ACTIVITY_FORMS[signalType] ?? null,
    buildInitialValues: buildActivityInitialValues,
  };
}

// ==============================|| SIGNAL EDIT DRAWER ||============================== //

export default function SignalEditDrawer({
  open,
  onClose,
  onSuccess,
  signal,
  signalType,
  accountId,
  choices,
  choicesLoading,
  context = "activity",
}) {
  const theme = useTheme();
  const aq = theme.aphoriQ;

  const [reopening, setReopening] = useState(false);

  const { Form, buildInitialValues } = resolveForm(context, signalType);

  const initialValues = useMemo(
    () => buildInitialValues(signalType, signal),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [signal?.id, signalType, context],
  );

  const handleSave = useCallback(
    async (payload) => {
      if (!signal?.id) return;

      // Normalize contact fields (full object → UUID). source_contact only
      // exists in account context (explicit source picker); normalizing it is
      // harmless when absent.
      const normalizedPayload = { ...payload };
      if (
        context === "account" &&
        normalizedPayload.source_contact &&
        typeof normalizedPayload.source_contact === "object"
      ) {
        normalizedPayload.source_contact = normalizedPayload.source_contact.id;
      }
      if (
        normalizedPayload.target_contact &&
        typeof normalizedPayload.target_contact === "object"
      ) {
        normalizedPayload.target_contact = normalizedPayload.target_contact.id;
      }

      const result = await updateSignal(signalType, signal.id, normalizedPayload);

      if (result.success) {
        displaySuccessSnackbar("Signal updated successfully");
        onSuccess();
        onClose();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [signal, signalType, onSuccess, onClose, context],
  );

  const handleReopen = useCallback(async () => {
    if (!signal?.id) return;
    setReopening(true);

    const result = await reopenSignal(signalType, signal.id);

    if (result.success) {
      displaySuccessSnackbar("Signal reopened — now pending");
      onSuccess();
      onClose();
    } else {
      displayErrorSnackbar(result);
    }

    setReopening(false);
  }, [signal, signalType, onSuccess, onClose]);

  const title = TYPE_LABELS[signalType] ?? "Edit Signal";
  const canReopen =
    signal && (signal.status === "VALIDATED" || signal.status === "REJECTED");

  const sharedFormProps = {
    choices,
    choicesLoading,
    accountId,
    onAdd: handleSave,
    onCancel: onClose,
    initialValues,
    submitLabel: "Save changes",
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: { xs: "100%", sm: theme.spacing(60) },
          backgroundColor: aq.surface.level1,
        },
      }}
    >
      <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
        {/* ---- Header ---- */}
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          sx={{
            px: 2.5,
            py: 2,
            borderBottomStyle: "solid",
            borderBottomWidth: aq.border.width.hairline,
            borderBottomColor: aq.border.color,
          }}
        >
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Typography variant="h5">Edit {title}</Typography>
            {canReopen && (
              <Button
                variant="outlined"
                size="small"
                startIcon={
                  reopening ? (
                    <CircularProgress size={theme.iconSizes.sm} />
                  ) : (
                    <UndoOutlined style={{ fontSize: theme.iconSizes.sm }} />
                  )
                }
                onClick={handleReopen}
                disabled={reopening}
              >
                Reopen
              </Button>
            )}
          </Stack>
          <IconButton size="small" onClick={onClose} aria-label="Close drawer">
            <CloseOutlined style={{ fontSize: theme.iconSizes.sm }} />
          </IconButton>
        </Stack>

        {/* ---- Body ---- */}
        <Box sx={{ p: 2.5, flex: 1, overflowY: "auto" }}>
          {!signal ? (
            <Stack alignItems="center" py={4}>
              <CircularProgress size={theme.iconSizes.xxl} />
            </Stack>
          ) : !Form ? null : (
            <>
              <SignalIncompleteAlert
                missingFields={getMissingFields(signal, signalType)}
              />
              <Form {...sharedFormProps} />
            </>
          )}
        </Box>
      </Box>
    </Drawer>
  );
}

// ==============================|| PROP TYPES ||============================== //

SignalEditDrawer.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func.isRequired,
  signal: PropTypes.shape({
    id: PropTypes.string.isRequired,
    status: PropTypes.string,
  }),
  signalType: PropTypes.oneOf([
    "pain",
    "objective",
    "impact",
    "tech-stack",
    "blockers",
    "next-steps",
  ]),
  accountId: PropTypes.string.isRequired,
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
  /** 'activity' = implicit source (no picker); 'account' = explicit source pickers. */
  context: PropTypes.oneOf(["activity", "account"]),
};
