// frontend/src/sections/activities/signals/SignalEditDialog.jsx

"use client";

import PropTypes from "prop-types";
import { useMemo, useCallback, useState } from "react";

// material-ui
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";

// ant-design icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import { UndoOutlined } from "@ant-design/icons";

// project imports
import { updateSignal, reopenSignal } from "api/signals/signals";
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
import NextStepEditForm from "./NextStepEditForm";

// ==============================|| TYPE CONFIG ||============================== //

const TYPE_LABELS = {
  pain: "Pain Signal",
  objective: "Objective Signal",
  impact: "Impact Signal",
  "tech-stack": "Tech Stack Signal",
  blockers: "Blocker Signal",
  "next-steps": "Next Step Suggestion",
};

// ==============================|| SIGNAL EDIT DIALOG ||============================== //

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
  const [reopening, setReopening] = useState(false);

  const initialValues = useMemo(
    () => buildEditInitialValues(signalType, signal),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [signal?.id, signalType],
  );

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
    signal &&
    (signal.status === "VALIDATED" || signal.status === "REJECTED");

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
        <Stack direction="row" spacing={1.5} alignItems="center">
          <span>Edit {title}</span>
          {canReopen && (
            <Button
              variant="outlined"
              size="small"
              startIcon={
                reopening ? (
                  <CircularProgress size={14} />
                ) : (
                  <UndoOutlined style={{ fontSize: 14 }} />
                )
              }
              onClick={handleReopen}
              disabled={reopening}
            >
              Reopen
            </Button>
          )}
        </Stack>
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
            {signalType === "next-steps" && (
              <NextStepEditForm {...sharedFormProps} />
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
};
