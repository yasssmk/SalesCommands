// frontend/src/sections/accounts/decision-cycles/Decision-steps/DecisionStepContactsTab.jsx

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback, useMemo } from 'react';

// MUI
import { alpha } from '@mui/material/styles';
import Autocomplete from '@mui/material/Autocomplete';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// Icons
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import MailOutlined from '@ant-design/icons/MailOutlined';
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';

// Project imports
import { useGetContacts } from 'api/businessData/contacts';
import { updateDecisionStep } from 'api/accounts/decisionCycles';
import { displaySuccessSnackbar, displayErrorSnackbar } from 'utils/displayError';

// ==============================|| INFLUENCE LEVEL COLORS ||============================== //

const INFLUENCE_COLORS = {
  DECISION_MAKER: 'success',
  INFLUENCER: 'info',
  CHAMPION: 'primary',
  USER: 'default',
  GATEKEEPER: 'warning',
  BLOCKER: 'error',
  UNKNOWN: 'default'
};

// ==============================|| CONTACT CARD ||============================== //

function ContactCard({ contact, onRemove }) {
  const fullName = contact.contact_name || contact.full_name || 
    `${contact.first_name || ''} ${contact.last_name || ''}`.trim() || 'Unknown';
  
  const influenceLevel = contact.influence_level || contact.contact?.influence_level;
  const jobTitle = contact.job_title || contact.contact?.job_title;
  const email = contact.contact_email || contact.email || contact.contact?.email;
  const phone = contact.phone_number || contact.contact?.phone_number;
  
  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 2,
        bgcolor: (theme) => alpha(theme.palette.primary.main, 0.02),
        border: '1px solid',
        borderColor: 'divider',
        position: 'relative',
        '&:hover': {
          borderColor: 'primary.light',
          '& .remove-btn': { opacity: 1 }
        }
      }}
    >
      {/* Remove button */}
      <IconButton
        className="remove-btn"
        size="small"
        onClick={() => onRemove(contact)}
        sx={{
          position: 'absolute',
          top: 8,
          right: 8,
          opacity: 0,
          transition: 'opacity 0.2s',
          bgcolor: 'background.paper',
          '&:hover': { bgcolor: 'error.lighter', color: 'error.main' }
        }}
      >
        <CloseOutlined style={{ fontSize: 12 }} />
      </IconButton>
      
      <Stack direction="row" spacing={2} alignItems="flex-start">
        {/* Avatar */}
        <Avatar sx={{ bgcolor: 'primary.lighter', color: 'primary.main', width: 44, height: 44 }}>
          <UserOutlined />
        </Avatar>
        
        {/* Info */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="subtitle1" fontWeight={600} noWrap>
            {fullName}
          </Typography>
          
          {jobTitle && (
            <Typography variant="body2" color="text.secondary" noWrap>
              {jobTitle}
            </Typography>
          )}
          
          <Stack direction="row" spacing={2} sx={{ mt: 1 }} flexWrap="wrap">
            {email && (
              <Stack direction="row" spacing={0.5} alignItems="center">
                <MailOutlined style={{ fontSize: 12, opacity: 0.6 }} />
                <Typography variant="caption" color="text.secondary" noWrap>
                  {email}
                </Typography>
              </Stack>
            )}
            {phone && (
              <Stack direction="row" spacing={0.5} alignItems="center">
                <PhoneOutlined style={{ fontSize: 12, opacity: 0.6 }} />
                <Typography variant="caption" color="text.secondary">
                  {phone}
                </Typography>
              </Stack>
            )}
          </Stack>
          
          {influenceLevel && influenceLevel !== 'UNKNOWN' && (
            <Chip
              label={influenceLevel.replace('_', ' ')}
              size="small"
              color={INFLUENCE_COLORS[influenceLevel] || 'default'}
              variant="outlined"
              sx={{ mt: 1 }}
            />
          )}
        </Box>
      </Stack>
    </Box>
  );
}

ContactCard.propTypes = {
  contact: PropTypes.object.isRequired,
  onRemove: PropTypes.func.isRequired
};

// ==============================|| DECISION STEP CONTACTS TAB ||============================== //

/**
 * Decision Step Contacts Tab
 * 
 * MVP: Simple chip list showing contacts linked to this step.
 * - Display contacts as cards
 * - Add contacts from account contacts
 * - Remove contacts from step
 * 
 * @param {object} step - Decision Step data
 * @param {string} accountId - Account UUID for fetching available contacts
 */
export default function DecisionStepContactsTab({ step, accountId }) {
  const [saving, setSaving] = useState(false);
  const [addMode, setAddMode] = useState(false);
  const [selectedContacts, setSelectedContacts] = useState([]);
  
  // Current step contacts
  const stepContacts = step?.step_contacts || [];
  const stepContactIds = useMemo(() => 
    stepContacts.map(sc => sc.contact_id || sc.contact?.id),
    [stepContacts]
  );
  
  // Fetch all account contacts for the add dropdown
  const { contacts: accountContacts = [], contactsLoading } = useGetContacts({
    pageSize: 100,
    filters: { account_id: accountId }
  });
  
  // Available contacts (not already in step)
  const availableContacts = useMemo(() => 
    accountContacts.filter(c => !stepContactIds.includes(c.id)),
    [accountContacts, stepContactIds]
  );
  
  // ==============================|| HANDLERS ||============================== //
  
  // Add contacts to step
  const handleAddContacts = useCallback(async () => {
  if (selectedContacts.length === 0) return;
  
  setSaving(true);
  try {
    const newContactIds = [...stepContactIds, ...selectedContacts.map(c => c.id)];
    const result = await updateDecisionStep(step.id, { contact_ids: newContactIds }, step.cycle);
    
    if (result.success) {
      displaySuccessSnackbar(`${selectedContacts.length} contact(s) added`);
      setSelectedContacts([]);
      setAddMode(false);
      onUpdate?.(); // Triggers mutateStep → SWR revalidates step data
    } else {
      displayErrorSnackbar({
        message: result.error || 'Failed to add contacts',
        status: result.status
      });
    }
  } catch (error) {
    displayErrorSnackbar({
      message: error?.message || 'An unexpected error occurred',
      status: 500
    });
  } finally {
    setSaving(false);
  }
}, [selectedContacts, stepContactIds, step?.id, step?.cycle, onUpdate]);

const handleRemoveContact = useCallback(async (contact) => {
  const contactIdToRemove = contact.contact_id || contact.contact?.id || contact.id;
  
  setSaving(true);
  try {
    const newContactIds = stepContactIds.filter(id => id !== contactIdToRemove);
    const result = await updateDecisionStep(step.id, { contact_ids: newContactIds }, step.cycle);
    
    if (result.success) {
      displaySuccessSnackbar('Contact removed');
      onUpdate?.(); // Triggers mutateStep → SWR revalidates step data
    } else {
      displayErrorSnackbar({
        message: result.error || 'Failed to remove contact',
        status: result.status
      });
    }
  } catch (error) {
    displayErrorSnackbar({
      message: error?.message || 'An unexpected error occurred',
      status: 500
    });
  } finally {
    setSaving(false);
  }
}, [stepContactIds, step?.id, step?.cycle, onUpdate]);
  
  // Cancel add mode
  const handleCancelAdd = useCallback(() => {
    setSelectedContacts([]);
    setAddMode(false);
  }, []);
  
  // ==============================|| RENDER ||============================== //
  
  return (
    <Box>
      {/* Header */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h6">Contacts</Typography>
          <Typography variant="body2" color="text.secondary">
            People involved in this decision step.
          </Typography>
        </Box>
        
        {!addMode && (
          <Button
            variant="contained"
            startIcon={<PlusOutlined />}
            onClick={() => setAddMode(true)}
            disabled={availableContacts.length === 0}
          >
            Add Contact
          </Button>
        )}
      </Stack>
      
      {/* Add Contact Form */}
      {addMode && (
        <Box
          sx={{
            p: 2,
            mb: 3,
            borderRadius: 2,
            bgcolor: 'primary.lighter',
            border: '1px solid',
            borderColor: 'primary.light'
          }}
        >
          <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
            Select contacts to add
          </Typography>
          <Stack direction="row" spacing={2} alignItems="flex-start">
            <Autocomplete
              multiple
              fullWidth
              size="small"
              options={availableContacts}
              value={selectedContacts}
              onChange={(_, newValue) => setSelectedContacts(newValue)}
              getOptionLabel={(option) => 
                option.full_name || `${option.first_name || ''} ${option.last_name || ''}`.trim() || option.email || ''
              }
              isOptionEqualToValue={(option, val) => option.id === val.id}
              loading={contactsLoading}
              renderInput={(params) => (
                <TextField
                  {...params}
                  placeholder="Search contacts..."
                  InputProps={{
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {contactsLoading ? <CircularProgress size={16} /> : null}
                        {params.InputProps.endAdornment}
                      </>
                    )
                  }}
                />
              )}
              renderTags={(tagValue, getTagProps) =>
                tagValue.map((option, index) => (
                  <Chip
                    label={option.full_name || option.email}
                    size="small"
                    {...getTagProps({ index })}
                    key={option.id}
                  />
                ))
              }
              disabled={saving}
            />
            <Button
              variant="contained"
              onClick={handleAddContacts}
              disabled={saving || selectedContacts.length === 0}
            >
              {saving ? <CircularProgress size={20} /> : 'Add'}
            </Button>
            <Button
              variant="outlined"
              color="secondary"
              onClick={handleCancelAdd}
              disabled={saving}
            >
              Cancel
            </Button>
          </Stack>
          
          {availableContacts.length === 0 && !contactsLoading && (
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
              All account contacts are already added to this step.
            </Typography>
          )}
        </Box>
      )}
      
      {/* Empty state */}
      {stepContacts.length === 0 && !addMode && (
        <Box
          sx={{
            py: 6,
            textAlign: 'center',
            border: '2px dashed',
            borderColor: 'divider',
            borderRadius: 2
          }}
        >
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No contacts linked
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Add contacts to track who is involved in this decision step.
          </Typography>
          <Button
            variant="outlined"
            startIcon={<PlusOutlined />}
            onClick={() => setAddMode(true)}
            disabled={availableContacts.length === 0}
          >
            Add First Contact
          </Button>
        </Box>
      )}
      
      {/* Contacts Grid */}
      {stepContacts.length > 0 && (
        <Grid container spacing={2}>
          {stepContacts.map((contact) => (
            <Grid item xs={12} sm={6} md={4} key={contact.contact_id || contact.id}>
              <ContactCard
                contact={contact}
                onRemove={handleRemoveContact}
              />
            </Grid>
          ))}
        </Grid>
      )}
      
      {/* Loading overlay */}
      {saving && (
        <Box
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            bgcolor: 'rgba(255,255,255,0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
          }}
        >
          <CircularProgress />
        </Box>
      )}
    </Box>
  );
}

DecisionStepContactsTab.propTypes = {
  step: PropTypes.object.isRequired,
  accountId: PropTypes.string
};
