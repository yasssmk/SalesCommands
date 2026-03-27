// frontend/src/sections/campaigns/create/CampaignCreateModal.jsx
/**
 * Campaign Create Wizard
 * Pattern: TerritoryModal (modal wrapper) + MUI Stepper (wizard nav)
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback } from "react";

// material-ui
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import Modal from "@mui/material/Modal";
import Stack from "@mui/material/Stack";
import Step from "@mui/material/Step";
import StepLabel from "@mui/material/StepLabel";
import Stepper from "@mui/material/Stepper";
import Typography from "@mui/material/Typography";

// project imports
import MainCard from "components/MainCard";
import StepSelectType from "./StepSelectType";
import StepConfigureTarget from "./StepConfigureTarget";
import StepObjectiveMembers from "./StepObjectiveMembers";
import StepReviewCreate from "./StepReviewCreate";

// api
import { createCampaign, CAMPAIGN_TYPES } from "api/campaigns/campaigns";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";
import { handleFormikError } from "utils/formErrorHandler";

// icons
import ArrowLeftOutlined from "@ant-design/icons/ArrowLeftOutlined";
import ArrowRightOutlined from "@ant-design/icons/ArrowRightOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";

// ==============================|| STEP DEFINITIONS ||============================== //

const STEPS = [
  { label: "Campaign Type" },
  { label: "Target" },
  { label: "Details" },
  { label: "Review" },
];

// ==============================|| INITIAL WIZARD STATE ||============================== //

const INITIAL_STATE = {
  // Step 0: Type
  family: "",
  // Step 1: Target
  territory_ids: [],
  selectedTerritories: [],
  account_ids: [],
  // Step 2: Details
  name: "",
  description: "",
  sequence_type: "",
  start_date: null,
  end_date: null,
  objective_type: "",
  objective_target: "",
  executor_id: null,
  selectedExecutor: null,
  // Channel strategy — AUTO lets backend pick variant per contact channels
  channel_override: "AUTO",
};

// ==============================|| CAMPAIGN CREATE MODAL ||============================== //

export default function CampaignCreateModal({ open, onClose, onSuccess }) {
  const theme = useTheme();

  // ==============================|| STATE ||============================== //

  const [activeStep, setActiveStep] = useState(0);
  const [wizardData, setWizardData] = useState(INITIAL_STATE);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});
  const [fieldTouched, setFieldTouched] = useState({});

  // ==============================|| WIZARD DATA HANDLERS ||============================== //

  /**
   * Update wizard data (partial merge)
   */
  const updateData = useCallback((updates) => {
    setWizardData((prev) => ({ ...prev, ...updates }));
  }, []);

  /**
   * Reset wizard to initial state
   */
  const resetWizard = useCallback(() => {
    setActiveStep(0);
    setWizardData(INITIAL_STATE);
    setIsSubmitting(false);
    setFieldErrors({});
    setFieldTouched({});
  }, []);

  // ==============================|| NAVIGATION ||============================== //

  // Required fields per step — marks them touched so errors display immediately
  const STEP_REQUIRED_FIELDS = {
    2: ["name", "start_date", "end_date"],
  };

  const handleNext = () => {
    const requiredFields = STEP_REQUIRED_FIELDS[activeStep];
    if (requiredFields) {
      const newErrors = {};
      const newTouched = {};
      requiredFields.forEach((field) => {
        newTouched[field] = true;
        if (!wizardData[field]) {
          newErrors[field] = "This field is required.";
        }
      });
      setFieldTouched((prev) => ({ ...prev, ...newTouched }));
      setFieldErrors((prev) => ({ ...prev, ...newErrors }));
      if (Object.keys(newErrors).length > 0) return; // Block navigation
    }
    setActiveStep((prev) => Math.min(prev + 1, STEPS.length - 1));
  };
  const handleBack = () => {
    setActiveStep((prev) => Math.max(prev - 1, 0));
  };

  const handleClose = () => {
    resetWizard();
    onClose();
  };

  // ==============================|| STEP VALIDATION ||============================== //

  /**
   * Check if current step is valid to proceed
   */
  const isStepValid = () => {
    switch (activeStep) {
      case 0:
        return Boolean(wizardData.family);
      case 1:
        // Only OUTBOUND is selectable — requires at least one territory
        if (wizardData.family === CAMPAIGN_TYPES.OUTBOUND) {
          return wizardData.territory_ids.length > 0;
        }
        return false;
      case 2:
        return Boolean(wizardData.name);
      case 3:
        return true; // Review step — always valid
      default:
        return false;
    }
  };

  // ==============================|| SUBMIT ||============================== //

  const handleCreate = async () => {
    setIsSubmitting(true);
    try {
      const payload = {
        name: wizardData.name,
        description: wizardData.description,
        campaign_type: wizardData.family,
        sequence_type: wizardData.family || null,
        territory_ids: wizardData.territory_ids || [],
        start_date: wizardData.start_date,
        end_date: wizardData.end_date,
        // Nested objective (backend CampaignCreateSerializer accepts optional dict)
        ...(wizardData.objective_type && {
          objective: {
            objective_type: wizardData.objective_type,
            target_value: wizardData.objective_target || null,
            is_primary: true,
          },
        }),
        // Executor assignment — single optional user
        executor_id: wizardData.executor_id || null,
        // Channel strategy override — AUTO defers to backend per-contact logic
        channel_override: wizardData.channel_override || "AUTO",
      };

      const result = await createCampaign(payload);

      if (result.success) {
        displaySuccessSnackbar("Campaign created successfully");
        handleClose();
        if (onSuccess) onSuccess();
      } else {
        // Formik-compatible adapter — bridges handleFormikError with wizard state
        const formikAdapter = {
          setFieldError: (field, message) =>
            setFieldErrors((prev) => ({ ...prev, [field]: message })),
          setFieldTouched: (field) =>
            setFieldTouched((prev) => ({ ...prev, [field]: true })),
          setSubmitting: (val) => setIsSubmitting(val),
        };
        handleFormikError(result, formikAdapter);
        // Navigate to step containing the first field error
        _navigateToFieldError(result);
      }
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Map backend field names → wizard step index
  const FIELD_STEP_MAP = {
    name: 2,
    description: 2,
    start_date: 2,
    end_date: 2,
    planned_start_date: 2,
    planned_end_date: 2,
    objective_type: 2,
    objective_target: 2,
    channel_override: 2,
    territory_ids: 1,
    campaign_type: 0,
  };

  const _navigateToFieldError = (result) => {
    const data = result?.response?.data || result?.data || result;
    if (!data || typeof data !== "object") return;
    const errorFields = Object.keys(data).filter(
      (k) => !["detail", "error", "message", "success", "status"].includes(k),
    );
    for (const field of errorFields) {
      const step = FIELD_STEP_MAP[field];
      if (step !== undefined) {
        setActiveStep(step);
        return;
      }
    }
  };

  // ==============================|| STEP CONTENT ||============================== //

  const renderStepContent = () => {
    switch (activeStep) {
      case 0:
        return (
          <StepSelectType
            selectedFamily={wizardData.family}
            onSelect={(family) => {
              updateData({ family });
              handleNext();
            }}
          />
        );
      case 1:
        return (
          <StepConfigureTarget
            family={wizardData.family}
            territoryIds={wizardData.territory_ids}
            selectedTerritories={wizardData.selectedTerritories}
            accountIds={wizardData.account_ids}
            onUpdate={updateData}
          />
        );
      case 2:
        return (
          <StepObjectiveMembers
            data={wizardData}
            onUpdate={updateData}
            errors={fieldErrors}
            touched={fieldTouched}
          />
        );
      case 3:
        return <StepReviewCreate data={wizardData} />;
      default:
        return null;
    }
  };

  // ==============================|| RENDER ||============================== //

  const isLastStep = activeStep === STEPS.length - 1;
  const isFirstStep = activeStep === 0;

  return (
    <>
      {open && (
        <Modal
          open={open}
          onClose={handleClose}
          aria-labelledby="modal-campaign-create"
          sx={{ "& .MuiPaper-root:focus": { outline: "none" } }}
        >
          <MainCard
            sx={{
              width: "calc(100% - 48px)",
              minWidth: 340,
              maxWidth: 720,
              height: "auto",
              maxHeight: "calc(100vh - 48px)",
            }}
            modal
            content={false}
          >
            <Box
              sx={{
                maxHeight: "calc(100vh - 48px)",
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
              }}
            >
              {/* ==================== HEADER ==================== */}
              <Box sx={{ px: 3, pt: 3, pb: 2, flexShrink: 0 }}>
                <Typography variant="h4" component="h2">
                  Create Campaign
                </Typography>
              </Box>

              {/* ==================== STEPPER ==================== */}
              <Box sx={{ px: 3, pb: 2, flexShrink: 0 }}>
                <Stepper activeStep={activeStep} alternativeLabel>
                  {STEPS.map((step, index) => (
                    <Step key={step.label} completed={index < activeStep}>
                      <StepLabel>{step.label}</StepLabel>
                    </Step>
                  ))}
                </Stepper>
              </Box>

              <Divider sx={{ flexShrink: 0 }} />

              {/* ==================== STEP CONTENT (scrollable) ==================== */}
              <Box
                sx={{
                  px: 3,
                  py: 3,
                  flexGrow: 1,
                  minHeight: 300,
                  overflowY: "auto",
                  WebkitOverflowScrolling: "touch",
                  overscrollBehavior: "contain",
                }}
              >
                {renderStepContent()}
              </Box>

              <Divider sx={{ flexShrink: 0 }} />

              {/* ==================== FOOTER NAVIGATION (sticky) ==================== */}
              <Box sx={{ px: 3, py: 2, flexShrink: 0 }}>
                <Stack
                  direction="row"
                  justifyContent="space-between"
                  alignItems="center"
                >
                  {/* Left: Cancel / Back */}
                  <Stack direction="row" spacing={1}>
                    <Button color="error" onClick={handleClose}>
                      Cancel
                    </Button>
                    {!isFirstStep && (
                      <Button
                        variant="outlined"
                        startIcon={<ArrowLeftOutlined />}
                        onClick={handleBack}
                      >
                        Back
                      </Button>
                    )}
                  </Stack>

                  {/* Right: Next / Create */}
                  {!isLastStep ? (
                    <Button
                      variant="contained"
                      endIcon={<ArrowRightOutlined />}
                      onClick={handleNext}
                      disabled={!isStepValid()}
                    >
                      Next
                    </Button>
                  ) : (
                    <Button
                      variant="contained"
                      startIcon={<PlusOutlined />}
                      onClick={handleCreate}
                      disabled={isSubmitting || !isStepValid()}
                    >
                      {isSubmitting ? "Creating..." : "Create Campaign"}
                    </Button>
                  )}
                </Stack>
              </Box>
            </Box>
          </MainCard>
        </Modal>
      )}
    </>
  );
}

// ==============================|| PROP TYPES ||============================== //

CampaignCreateModal.propTypes = {
  /** Whether the modal is open */
  open: PropTypes.bool.isRequired,
  /** Callback to close the modal */
  onClose: PropTypes.func.isRequired,
  /** Callback after successful creation (e.g. refresh list) */
  onSuccess: PropTypes.func,
};
