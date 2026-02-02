// frontend/src/sections/accounts/decision-cycles/DecisionCycleModal.jsx
/**
 * Decision Cycle Modal Component
 * 
 * Modal for creating and editing decision cycles.
 * Simple form with name and description.
 * 
 * Features:
 * - Create new cycle
 * - Edit existing cycle (rename/description)
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useEffect } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import InputLabel from '@mui/material/InputLabel';
import Modal from '@mui/material/Modal';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// third-party
import { useFormik } from 'formik';
import * as Yup from 'yup';

// project imports
import MainCard from 'components/MainCard';
import { 
  createDecisionCycle, 
  updateDecisionCycle 
} from 'api/accounts/decisionCycles';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| VALIDATION SCHEMA ||============================== //

const validationSchema = Yup.object({
  name: Yup.string()
    .required('Cycle name is required')
    .max(255, 'Name must be at most 255 characters'),
  description: Yup.string()
    .max(1000, 'Description must be at most 1000 characters')
});

// ==============================|| DECISION CYCLE MODAL ||============================== //

/**
 * DecisionCycleModal Component
 * 
 * @param {boolean} open - Modal open state
 * @param {Function} onClose - Close modal callback
 * @param {Object} cycle - Existing cycle for edit mode (null for create)
 * @param {string} accountId - Parent account UUID (required for create)
 * @param {Function} onSuccess - Success callback with created/updated cycle
 */
export default function DecisionCycleModal({ 
  open, 
  onClose, 
  cycle = null,
  accountId,
  onSuccess
}) {
  const [submitting, setSubmitting] = useState(false);
  
  const isEditMode = Boolean(cycle?.id);
  
  // Formik setup
  const formik = useFormik({
    initialValues: {
      name: cycle?.name || '',
      description: cycle?.description || ''
    },
    validationSchema,
    enableReinitialize: true,
    onSubmit: async (values) => {
      setSubmitting(true);
      
      try {
        let result;
        
        if (isEditMode) {
          // Update existing cycle
          result = await updateDecisionCycle(cycle.id, {
            name: values.name.trim(),
            description: values.description?.trim() || null
          });
        } else {
          // Create new cycle
          result = await createDecisionCycle({
            account_id: accountId,
            name: values.name.trim(),
            description: values.description?.trim() || null,
            is_active: true
          });
        }
        
        if (result.success) {
          displaySuccessSnackbar(
            isEditMode 
              ? 'Decision cycle updated successfully' 
              : 'Decision cycle created successfully'
          );
          onSuccess?.(result.data);
          handleClose();
        } else {
          displayErrorSnackbar({
            message: result.error || (isEditMode ? 'Failed to update decision cycle' : 'Failed to create decision cycle'),
            status: result.status
          });
        }
        } catch (err) {
        displayErrorSnackbar({
          message: err?.message || 'An unexpected error occurred',
          status: 500
        });
        } finally {
        setSubmitting(false);
      }
    }
  });

  const { values, errors, touched, handleChange, handleBlur, handleSubmit, resetForm } = formik;
  
  // Reset form when modal opens/closes
  useEffect(() => {
    if (open) {
      resetForm({
        values: {
          name: cycle?.name || '',
          description: cycle?.description || ''
        }
      });
    }
  }, [open, cycle, resetForm]);
  
  const handleClose = () => {
    resetForm();
    onClose();
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Modal
      open={open}
      onClose={handleClose}
      aria-labelledby="modal-cycle-title"
      sx={{
        '& .MuiPaper-root:focus': { outline: 'none' }
      }}
    >
      <MainCard
        sx={{
          width: `calc(100% - 48px)`,
          minWidth: 340,
          maxWidth: 500,
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)'
        }}
        modal
        content={false}
      >
        <Box component="form" onSubmit={handleSubmit}>
          {/* Header */}
          <Box sx={{ p: 2.5, pb: 2 }}>
            <Typography variant="h5" id="modal-cycle-title">
              {isEditMode ? 'Edit Decision Cycle' : 'Create Decision Cycle'}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {isEditMode 
                ? 'Update the cycle name and description'
                : 'Create a new decision cycle to track the buyer journey'
              }
            </Typography>
          </Box>
          
          <Divider />
          
          {/* Form Content */}
          <Box sx={{ p: 2.5 }}>
            <Grid container spacing={2.5}>
              
              {/* Name */}
              <Grid item xs={12}>
                <Stack spacing={1}>
                  <InputLabel required>Cycle Name</InputLabel>
                  <TextField
                    fullWidth
                    name="name"
                    placeholder="e.g., Main Sales Cycle, Enterprise Deal 2024..."
                    value={values.name}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    error={touched.name && Boolean(errors.name)}
                    helperText={touched.name && errors.name}
                    autoFocus
                  />
                </Stack>
              </Grid>
              
              {/* Description */}
              <Grid item xs={12}>
                <Stack spacing={1}>
                  <InputLabel>Description</InputLabel>
                  <TextField
                    fullWidth
                    multiline
                    rows={3}
                    name="description"
                    placeholder="Optional description of this decision cycle..."
                    value={values.description}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    error={touched.description && Boolean(errors.description)}
                    helperText={touched.description && errors.description}
                  />
                </Stack>
              </Grid>
              
            </Grid>
          </Box>
          
          <Divider />
          
          {/* Actions */}
          <Box sx={{ p: 2.5 }}>
            <Stack direction="row" spacing={2} justifyContent="flex-end">
              <Button 
                color="secondary" 
                onClick={handleClose}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button 
                type="submit" 
                variant="contained"
                disabled={submitting}
                startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : null}
              >
                {submitting 
                  ? (isEditMode ? 'Saving...' : 'Creating...') 
                  : (isEditMode ? 'Save Changes' : 'Create Cycle')
                }
              </Button>
            </Stack>
          </Box>
        </Box>
      </MainCard>
    </Modal>
  );
}

DecisionCycleModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  cycle: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string,
    description: PropTypes.string
  }),
  accountId: PropTypes.string,
  onSuccess: PropTypes.func
};