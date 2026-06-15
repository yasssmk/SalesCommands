// frontend/src/sections/accounts/dc-workspace/CycleCloseDialog.jsx
/**
 * Cycle Close / Reopen logic extracted for reuse across
 * DecisionCycleTimeline header and DC Workspace header.
 *
 * useCycleCloseReopen — hook exposing state, handlers, formik
 * CycleCloseDialog — the Dialog JSX (controlled by hook state)
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback } from "react";
import { useFormik } from "formik";
import * as Yup from "yup";

// MUI
import { useTheme } from "@mui/material/styles";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import FormControl from "@mui/material/FormControl";
import FormHelperText from "@mui/material/FormHelperText";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";

// Icons
import CheckCircleFilled from "@ant-design/icons/CheckCircleFilled";
import CloseCircleFilled from "@ant-design/icons/CloseCircleFilled";
import MinusCircleOutlined from "@ant-design/icons/MinusCircleOutlined";
import PauseCircleOutlined from "@ant-design/icons/PauseCircleOutlined";

// Project imports
import { closeCycle, reopenCycle } from "api/accounts/decisionCycles";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| HOOK ||============================== //

export function useCycleCloseReopen({ cycle, onRefresh }) {
  const [closeDialogOpen, setCloseDialogOpen] = useState(false);
  const [reopenLoading, setReopenLoading] = useState(false);

  const closeFormik = useFormik({
    initialValues: {
      outcome: "",
      outcome_notes: "",
      hold_until: "",
    },
    validationSchema: Yup.object({
      outcome: Yup.string().required("Please select an outcome"),
      outcome_notes: Yup.string().when("outcome", {
        is: "ON_HOLD",
        then: (schema) => schema.required("Notes are required for On Hold"),
        otherwise: (schema) => schema.nullable(),
      }),
      hold_until: Yup.string().when("outcome", {
        is: "ON_HOLD",
        then: (schema) =>
          schema
            .required("Hold until date is required for On Hold")
            .test("not-in-past", "Hold until date cannot be in the past", (value) => {
              if (!value) return true;
              const today = new Date();
              today.setHours(0, 0, 0, 0);
              return new Date(value) >= today;
            }),
        otherwise: (schema) => schema.nullable(),
      }),
    }),
    enableReinitialize: true,
    onSubmit: async (values, { setSubmitting, resetForm }) => {
      if (!cycle?.id) return;
      try {
        const payload = {
          outcome: values.outcome,
          outcome_notes: values.outcome_notes.trim() || null,
        };
        if (values.outcome === "ON_HOLD" && values.hold_until) {
          payload.hold_until = values.hold_until;
        }
        const result = await closeCycle(cycle.id, payload);
        if (result.success) {
          displaySuccessSnackbar("Decision cycle closed successfully");
          setCloseDialogOpen(false);
          resetForm();
          onRefresh?.();
        } else {
          displayErrorSnackbar(result);
        }
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setSubmitting(false);
      }
    },
  });

  const handleCloseDialogDismiss = useCallback(() => {
    setCloseDialogOpen(false);
    closeFormik.resetForm();
  }, [closeFormik]);

  const handleReopenCycle = useCallback(async () => {
    if (!cycle?.id) return;
    setReopenLoading(true);
    try {
      const result = await reopenCycle(cycle.id);
      if (result.success) {
        displaySuccessSnackbar("Decision cycle reopened successfully");
        onRefresh?.();
      } else {
        displayErrorSnackbar(result);
      }
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setReopenLoading(false);
    }
  }, [cycle?.id, onRefresh]);

  return {
    closeDialogOpen,
    setCloseDialogOpen,
    closeFormik,
    handleCloseDialogDismiss,
    reopenLoading,
    handleReopenCycle,
  };
}

// ==============================|| DIALOG ||============================== //

export default function CycleCloseDialog({
  open,
  onClose,
  formik,
}) {
  const theme = useTheme();

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Close Decision Cycle</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <FormControl
            fullWidth
            error={formik.touched.outcome && Boolean(formik.errors.outcome)}
          >
            <InputLabel>Outcome</InputLabel>
            <Select
              name="outcome"
              value={formik.values.outcome}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              label="Outcome"
            >
              <MenuItem value="WON">
                <Stack direction="row" spacing={1} alignItems="center">
                  <CheckCircleFilled
                    style={{ color: theme.palette.success.main }}
                  />
                  <span>Won</span>
                </Stack>
              </MenuItem>
              <MenuItem value="LOST">
                <Stack direction="row" spacing={1} alignItems="center">
                  <CloseCircleFilled
                    style={{ color: theme.palette.error.main }}
                  />
                  <span>Lost</span>
                </Stack>
              </MenuItem>
              <MenuItem value="ON_HOLD">
                <Stack direction="row" spacing={1} alignItems="center">
                  <PauseCircleOutlined
                    style={{ color: theme.palette.warning.main }}
                  />
                  <span>On Hold</span>
                </Stack>
              </MenuItem>
              <MenuItem value="NOT_QUALIFIED">
                <Stack direction="row" spacing={1} alignItems="center">
                  <MinusCircleOutlined
                    style={{ color: theme.palette.grey[500] }}
                  />
                  <span>Not Qualified</span>
                </Stack>
              </MenuItem>
            </Select>
            {formik.touched.outcome && formik.errors.outcome && (
              <FormHelperText error>{formik.errors.outcome}</FormHelperText>
            )}
          </FormControl>

          {formik.values.outcome === "ON_HOLD" && (
            <TextField
              name="hold_until"
              label="Hold until"
              type="date"
              fullWidth
              required
              value={formik.values.hold_until}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              error={
                formik.touched.hold_until && Boolean(formik.errors.hold_until)
              }
              helperText={formik.touched.hold_until && formik.errors.hold_until}
              InputLabelProps={{ shrink: true }}
              inputProps={{ min: new Date().toISOString().split("T")[0] }}
            />
          )}

          <TextField
            name="outcome_notes"
            label={
              formik.values.outcome === "ON_HOLD"
                ? "Notes"
                : "Notes (optional)"
            }
            fullWidth
            multiline
            rows={2}
            required={formik.values.outcome === "ON_HOLD"}
            value={formik.values.outcome_notes}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={
              formik.touched.outcome_notes &&
              Boolean(formik.errors.outcome_notes)
            }
            helperText={
              formik.touched.outcome_notes && formik.errors.outcome_notes
            }
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={formik.isSubmitting}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={formik.handleSubmit}
          disabled={formik.isSubmitting}
        >
          {formik.isSubmitting ? "Closing..." : "Confirm"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

CycleCloseDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  formik: PropTypes.object.isRequired,
};
