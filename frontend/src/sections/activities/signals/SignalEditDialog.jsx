// frontend/src/sections/activities/signals/SignalEditDialog.jsx
/**
 * SignalEditDialog — Dialog for editing an existing signal of any type.
 *
 * Reuses the 3 InlineXxxForm components from the wizard.
 * Passes pre-filled initialValues via buildEditInitialValues().
 * Submits via updateSignal() (PATCH) instead of createSignal().
 *
 * No staging, no review step — single signal, single save action.
 *
 * Edit is available for PENDING and VALIDATED signals (per SignalCard actions).
 * The form is identical to the creation form for each type.
 *
 * Error handling:
 *   Field-level errors surfaced via handleFormikError if the backend returns
 *   structured validation errors. Generic errors shown via displayErrorSnackbar.
 */

"use client";

import PropTypes from "prop-types";
import { useMemo, useCallback } from "react";

// material-ui
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";

// ant-design icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";

// project imports
import { updateSignal } from "api/signals/signals";
import {
  displayErrorSnackbar,
  displaySuccessSnackbar,
} from "utils/displayError";

import { getMissingFields } from "./signalValidationRules";
import SignalIncompleteAlert from "./SignalIncompleteAlert";
import { buildEditInitialValues } from "./wizard/forms/buildEditInitialValues";
import InlinePainForm from "./wizard/forms/InlinePainForm";
import InlineObjectiveForm from "./wizard/forms/InlineObjectiveForm";
import InlineImpactForm from "./wizard/forms/InlineImpactForm";
import InlineTechStackForm from "./wizard/forms/InlineTechStackForm";
import BlockerEditForm from "./BlockerEditForm";

// ==============================|| TYPE CONFIG ||============================== //

const TYPE_LABELS = {
  pain: "Pain Signal",
  objective: "Objective Signal",
  impact: "Impact Signal",
  "tech-stack": "Tech Stack Signal",
  blockers: "Blocker Signal",
};

// ==============================|| SIGNAL EDIT DIALOG ||============================== //

/**
 * SignalEditDialog
 *
 * @param {boolean}  open           - Dialog open state
 * @param {Function} onClose        - Called on cancel / backdrop click
 * @param {Function} onSuccess      - Called after successful PATCH
 * @param {Object}   signal         - Signal object to edit (from backend read serializer)
 * @param {string}   signalType     - 'pain' | 'objective' | 'impact' | 'tech-stack'
 * @param {string}   accountId      - Account UUID — scopes contact search
 * @param {Object}   choices        - From useGetSignalChoices()
 * @param {boolean}  choicesLoading
 */
export default function SignalEditDialog({
  open,
  onClose,
  onSuccess,
  signal,
  signalType,
  accountId,
  choices,
  choicesLoading,
}) {
  // ==============================|| INITIAL VALUES ||============================== //

  /**
   * Pre-fill form from backend signal object.
   * Re-computed only when signal or signalType changes — stable reference
   * prevents Formik from reinitializing on every render.
   */
  const initialValues = useMemo(
    () => buildEditInitialValues(signalType, signal),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [signal?.id, signalType],
  );

  // ==============================|| SUBMIT HANDLER ||============================== //

  /**
   * Receives the built payload from the inline form's onSubmit.
   * Calls PATCH, surfaces errors, closes on success.
   *
   * The inline form marks itself as submitting during this call via
   * Formik's isSubmitting — the submit button is disabled automatically.
   *
   * Contact normalization (post-standardisation refactor)
   * -----------------------------------------------------
   * target_contact (Objective PERSONAL scope) is the only remaining
   * contact-shaped field on the form payloads. Inline forms store it
   * as a full contact object for AsyncContactSelect compatibility; the
   * backend expects a UUID — we extract .id here before sending the PATCH.
   */
  const handleSave = useCallback(
    async (payload) => {
      if (!signal?.id) return;

      const normalizedPayload = { ...payload };
      if (
        normalizedPayload.target_contact &&
        typeof normalizedPayload.target_contact === "object"
      ) {
        normalizedPayload.target_contact = normalizedPayload.target_contact.id;
      }

      const result = await updateSignal(
        signalType,
        signal.id,
        normalizedPayload,
      );

      if (result.success) {
        displaySuccessSnackbar("Signal updated successfully");
        onSuccess();
        onClose();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [signal, signalType, onSuccess, onClose],
  );

  // ==============================|| RENDER ||============================== //

  const title = TYPE_LABELS[signalType] ?? "Edit Signal";

  /**
   * Shared props passed to all inline forms.
   * initialValues pre-fills the form from the existing signal.
   * submitLabel overrides the default "Add X" label.
   * onCancel closes the dialog.
   */
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
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby="signal-edit-dialog-title"
    >
      {/* ---- Header ---- */}
      <DialogTitle id="signal-edit-dialog-title" sx={{ pr: 6 }}>
        Edit {title}
        {/* Close button */}
        <IconButton
          size="small"
          onClick={onClose}
          aria-label="Close"
          sx={{
            position: "absolute",
            right: 16,
            top: 14,
            color: "text.secondary",
          }}
        >
          <CloseOutlined style={{ fontSize: 14 }} />
        </IconButton>
      </DialogTitle>

      <Divider />

      {/* ---- Form ---- */}
      <DialogContent sx={{ pt: 2.5, pb: 3 }}>
        {!signal ? (
          // Guard — should not happen in practice
          <Stack alignItems="center" py={4}>
            <CircularProgress size={24} />
          </Stack>
        ) : (
          <>
            <SignalIncompleteAlert
              missingFields={getMissingFields(signal, signalType)}
            />
            {signalType === "pain" && <InlinePainForm {...sharedFormProps} />}
            {signalType === "objective" && (
              <InlineObjectiveForm {...sharedFormProps} />
            )}
            {signalType === "impact" && (
              <InlineImpactForm {...sharedFormProps} />
            )}
            {signalType === "tech-stack" && (
              <InlineTechStackForm {...sharedFormProps} />
            )}
            {signalType === "blockers" && (
              <BlockerEditForm {...sharedFormProps} />
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ==============================|| PROP TYPES ||============================== //

SignalEditDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func.isRequired,
  signal: PropTypes.shape({
    id: PropTypes.string.isRequired,
  }),
  signalType: PropTypes.oneOf([
    "pain",
    "objective",
    "impact",
    "tech-stack",
    "blockers",
  ]),
  accountId: PropTypes.string.isRequired,
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
};
