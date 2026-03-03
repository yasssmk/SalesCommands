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
import { createCampaign, CAMPAIGN_FAMILIES } from "api/campaigns/campaigns";

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
  territory_id: "",
  territory_name: "",
  account_ids: [],

  // Step 2: Details
  name: "",
  description: "",
  sequence_type: "",
  start_date: null,
  end_date: null,
  objective_type: "",
  objective_target: "",
  member_ids: [],
};

// ==============================|| CAMPAIGN CREATE MODAL ||============================== //

export default function CampaignCreateModal({ open, onClose }) {
  const theme = useTheme();

  // ==============================|| STATE ||============================== //

  const [activeStep, setActiveStep] = useState(0);
  const [wizardData, setWizardData] = useState(INITIAL_STATE);
  const [isSubmitting, setIsSubmitting] = useState(false);

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
  }, []);

  // ==============================|| NAVIGATION ||============================== //

  const handleNext = () => {
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
        if (wizardData.family === CAMPAIGN_FAMILIES.OUTBOUND) {
          return Boolean(wizardData.territory_id);
        }
        // Targeted: at least 1 account selected
        return wizardData.account_ids.length > 0;
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
        sequence_type: wizardData.sequence_type || null,
        territory_id: wizardData.territory_id || null,
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
        // Member assignment
        owner_ids: [], // Current user auto-assigned by backend
        executor_ids: wizardData.member_ids || [],
      };

      const result = await createCampaign(payload);
      console.log("TODO: Campaign created", result);

      // TODO: displaySuccessSnackbar('Campaign created');
      // TODO: navigate to campaign workspace or refresh list
      handleClose();
    } catch (err) {
      console.error("TODO: handle create error", err);
    } finally {
      setIsSubmitting(false);
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
            territoryId={wizardData.territory_id}
            territoryName={wizardData.territory_name}
            accountIds={wizardData.account_ids}
            onUpdate={updateData}
          />
        );
      case 2:
        return <StepObjectiveMembers data={wizardData} onUpdate={updateData} />;
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
};
