// frontend/src/sections/activities/workspace/ActivityOverviewTab.jsx
/**
 * Activity Overview Tab Component
 * 
 * Displays activity details in organized sections:
 * 1. Details - Core information (type, description, CTA, account)
 * 2. People - Owner + Contacts + Invited Users
 * 3. Schedule - Dates, times
 * 4. Status & Result - Status management + outcome (if completed)
 * 5. Linked Activities - Decision cycle/step + Previous/Next activity
 * 6. Coming Soon - Future features placeholder
 */

'use client';

import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useRouter } from 'next/navigation';

// MUI
import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// Date pickers
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs from 'dayjs';

// Project imports
import {
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_COLORS,
  ACTIVITY_OUTCOME_LABELS,
  ACTIVITY_OUTCOME_COLORS,
  ACTIVITY_STATUSES,
  ACTIVITY_OUTCOMES,
  completeActivity,
  cancelActivity,
  reopenActivity
} from 'api/accounts/activities';
import { useGetContacts } from 'api/businessData/contacts';
import { useGetUsers } from 'api/admin/users';
import {
  useGetDecisionCyclesByAccount,
  useGetDecisionStepsByCycle
} from 'api/accounts/decisionCycles';
import AsyncUserSelect from 'components/AsyncSelection/AsyncUserSelect';
import { displaySuccessSnackbar, displayErrorSnackbar } from 'utils/displayError';
import { useAuth } from 'hooks/useAuth';

// Icons
import CheckOutlined from '@ant-design/icons/CheckOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';
import FileTextOutlined from '@ant-design/icons/FileTextOutlined';
import LinkOutlined from '@ant-design/icons/LinkOutlined';
import RocketOutlined from '@ant-design/icons/RocketOutlined';
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import StopOutlined from '@ant-design/icons/StopOutlined';
import ReloadOutlined from '@ant-design/icons/ReloadOutlined';
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import MailOutlined from '@ant-design/icons/MailOutlined';

// ==============================|| SECTION HEADER ||============================== //

function SectionHeader({ icon: Icon, title }) {
  return (
    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
      {Icon && <Icon style={{ fontSize: 18, color: '#8c8c8c' }} />}
      <Typography variant="subtitle1" fontWeight={600}>
        {title}
      </Typography>
    </Stack>
  );
}

SectionHeader.propTypes = {
  icon: PropTypes.elementType,
  title: PropTypes.string.isRequired
};

// ==============================|| DELETE CONFIRMATION DIALOG ||============================== //

function ConfirmDialog({ open, onClose, onConfirm, title, message, confirmLabel = 'Confirm', confirmColor = 'primary' }) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <DialogContentText>{message}</DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="inherit">Cancel</Button>
        <Button onClick={onConfirm} color={confirmColor} variant="contained">{confirmLabel}</Button>
      </DialogActions>
    </Dialog>
  );
}

ConfirmDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
  title: PropTypes.string.isRequired,
  message: PropTypes.string.isRequired,
  confirmLabel: PropTypes.string,
  confirmColor: PropTypes.string
};

// ==============================|| REMOVABLE CARD ||============================== //

function RemovableCard({ children, onRemove, removeTooltip = 'Remove' }) {
  const [hovered, setHovered] = useState(false);

  return (
    <Box
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      sx={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        p: 1.5,
        borderRadius: 1,
        bgcolor: 'grey.50',
        border: '1px solid',
        borderColor: 'grey.200',
        transition: 'border-color 0.2s',
        '&:hover': { borderColor: 'grey.300' }
      }}
    >
      {children}
      {hovered && onRemove && (
        <Tooltip title={removeTooltip}>
          <IconButton
            size="small"
            onClick={onRemove}
            sx={{
              position: 'absolute',
              top: 4,
              right: 4,
              bgcolor: 'background.paper',
              boxShadow: 1,
              '&:hover': { bgcolor: 'error.lighter', color: 'error.main' }
            }}
          >
            <CloseOutlined style={{ fontSize: 12 }} />
          </IconButton>
        </Tooltip>
      )}
    </Box>
  );
}

RemovableCard.propTypes = {
  children: PropTypes.node.isRequired,
  onRemove: PropTypes.func,
  removeTooltip: PropTypes.string
};

// ==============================|| EDITABLE FIELD ||============================== //

function EditableField({ label, value, fieldKey, onSave, type = 'text', options = [], displayValue }) {
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value || '');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTempValue(value || '');
  }, [value]);

  const handleSave = async () => {
    if (tempValue === value) {
      setEditing(false);
      return;
    }
    setSaving(true);
    const success = await onSave(fieldKey, tempValue || null);
    setSaving(false);
    if (success) setEditing(false);
  };

  const handleCancel = () => {
    setTempValue(value || '');
    setEditing(false);
  };

  const renderEditMode = () => {
    if (type === 'select') {
      return (
        <Select
          value={tempValue}
          onChange={(e) => setTempValue(e.target.value)}
          size="small"
          fullWidth
          autoFocus
          disabled={saving}
        >
          <MenuItem value=""><em>None</em></MenuItem>
          {options.map((opt) => (
            <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
          ))}
        </Select>
      );
    }

    if (type === 'textarea') {
      return (
        <TextField
          value={tempValue}
          onChange={(e) => setTempValue(e.target.value)}
          size="small"
          fullWidth
          multiline
          rows={3}
          autoFocus
          disabled={saving}
        />
      );
    }

    return (
      <TextField
        value={tempValue}
        onChange={(e) => setTempValue(e.target.value)}
        size="small"
        fullWidth
        autoFocus
        disabled={saving}
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleSave();
          if (e.key === 'Escape') handleCancel();
        }}
      />
    );
  };

  return (
    <Box>
      {label && (
        <Typography variant="caption" color="text.secondary" gutterBottom display="block">
          {label}
        </Typography>
      )}
      {editing ? (
        <Stack direction="row" spacing={1} alignItems="flex-start">
          <Box flex={1}>{renderEditMode()}</Box>
          <IconButton size="small" onClick={handleSave} disabled={saving} color="success">
            <CheckOutlined />
          </IconButton>
          <IconButton size="small" onClick={handleCancel} disabled={saving} color="error">
            <CloseOutlined />
          </IconButton>
        </Stack>
      ) : (
        <Stack direction="row" spacing={1} alignItems="center">
          <Box component="span" sx={{ typography: 'body1' }}>
            {displayValue || value || <span style={{ color: '#999' }}>-</span>}
          </Box>
          <IconButton size="small" onClick={() => setEditing(true)}>
            <EditOutlined />
          </IconButton>
        </Stack>
      )}
    </Box>
  );
}

EditableField.propTypes = {
  label: PropTypes.string,
  value: PropTypes.any,
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired,
  type: PropTypes.oneOf(['text', 'select', 'textarea']),
  options: PropTypes.array,
  displayValue: PropTypes.node
};

// ==============================|| EDITABLE DATE FIELD ||============================== //

function EditableDateField({ label, value, fieldKey, onSave }) {
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value ? dayjs(value) : null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTempValue(value ? dayjs(value) : null);
  }, [value]);

  const handleSave = async () => {
    setSaving(true);
    const formattedDate = tempValue ? tempValue.format('YYYY-MM-DD') : null;
    const success = await onSave(fieldKey, formattedDate);
    setSaving(false);
    if (success) setEditing(false);
  };

  const handleCancel = () => {
    setTempValue(value ? dayjs(value) : null);
    setEditing(false);
  };

  const displayValue = value ? dayjs(value).format('MMM D, YYYY') : '-';

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <Box>
        {label && (
          <Typography variant="caption" color="text.secondary" gutterBottom display="block">
            {label}
          </Typography>
        )}
        {editing ? (
          <Stack direction="row" spacing={1} alignItems="center">
            <DatePicker
              value={tempValue}
              onChange={(newValue) => setTempValue(newValue)}
              slotProps={{ textField: { size: 'small', fullWidth: true } }}
              disabled={saving}
            />
            <IconButton size="small" onClick={handleSave} disabled={saving} color="success">
              <CheckOutlined />
            </IconButton>
            <IconButton size="small" onClick={handleCancel} disabled={saving} color="error">
              <CloseOutlined />
            </IconButton>
          </Stack>
        ) : (
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="body1">{displayValue}</Typography>
            <IconButton size="small" onClick={() => setEditing(true)}>
              <EditOutlined />
            </IconButton>
          </Stack>
        )}
      </Box>
    </LocalizationProvider>
  );
}

EditableDateField.propTypes = {
  label: PropTypes.string,
  value: PropTypes.string,
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired
};

// ==============================|| EDITABLE TIME FIELD ||============================== //

function EditableTimeField({ label, value, fieldKey, onSave }) {
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value ? dayjs(`1970-01-01T${value}`) : null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTempValue(value ? dayjs(`1970-01-01T${value}`) : null);
  }, [value]);

  const handleSave = async () => {
    setSaving(true);
    const formattedTime = tempValue ? tempValue.format('HH:mm:ss') : null;
    const success = await onSave(fieldKey, formattedTime);
    setSaving(false);
    if (success) setEditing(false);
  };

  const handleCancel = () => {
    setTempValue(value ? dayjs(`1970-01-01T${value}`) : null);
    setEditing(false);
  };

  const displayValue = value ? dayjs(`1970-01-01T${value}`).format('h:mm A') : '-';

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <Box>
        {label && (
          <Typography variant="caption" color="text.secondary" gutterBottom display="block">
            {label}
          </Typography>
        )}
        {editing ? (
          <Stack direction="row" spacing={1} alignItems="center">
            <TimePicker
              value={tempValue}
              onChange={(newValue) => setTempValue(newValue)}
              slotProps={{ textField: { size: 'small', fullWidth: true } }}
              disabled={saving}
            />
            <IconButton size="small" onClick={handleSave} disabled={saving} color="success">
              <CheckOutlined />
            </IconButton>
            <IconButton size="small" onClick={handleCancel} disabled={saving} color="error">
              <CloseOutlined />
            </IconButton>
          </Stack>
        ) : (
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="body1">{displayValue}</Typography>
            <IconButton size="small" onClick={() => setEditing(true)}>
              <EditOutlined />
            </IconButton>
          </Stack>
        )}
      </Box>
    </LocalizationProvider>
  );
}

EditableTimeField.propTypes = {
  label: PropTypes.string,
  value: PropTypes.string,
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired
};

// ==============================|| INLINE SELECT FIELD ||============================== //

function InlineSelectField({ label, value, fieldKey, onSave, options = [], displayValue, placeholder = 'Select...' }) {
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value || '');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTempValue(value || '');
  }, [value]);

  const handleChange = async (newValue) => {
    if (newValue === value) {
      setEditing(false);
      return;
    }
    setSaving(true);
    const success = await onSave(fieldKey, newValue || null);
    setSaving(false);
    if (success) setEditing(false);
  };

  return (
    <Stack direction="row" spacing={1} alignItems="center">
      {label && (
        <Typography variant="body2" color="text.secondary" sx={{ minWidth: 50 }}>
          {label}:
        </Typography>
      )}
      {editing ? (
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Select
            value={tempValue}
            onChange={(e) => {
              setTempValue(e.target.value);
              handleChange(e.target.value);
            }}
            size="small"
            displayEmpty
            disabled={saving}
            sx={{ minWidth: 150 }}
            autoFocus
          >
            <MenuItem value=""><em>None</em></MenuItem>
            {options.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
            ))}
          </Select>
          <IconButton size="small" onClick={() => setEditing(false)} disabled={saving}>
            <CloseOutlined />
          </IconButton>
        </Stack>
      ) : (
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Typography
            variant="body2"
            sx={{
              cursor: 'pointer',
              color: displayValue ? 'text.primary' : 'text.secondary',
              '&:hover': { color: 'primary.main' }
            }}
            onClick={() => setEditing(true)}
          >
            {displayValue || placeholder}
          </Typography>
          <IconButton size="small" onClick={() => setEditing(true)} sx={{ p: 0.25 }}>
            <EditOutlined style={{ fontSize: 12 }} />
          </IconButton>
        </Stack>
      )}
    </Stack>
  );
}

InlineSelectField.propTypes = {
  label: PropTypes.string,
  value: PropTypes.any,
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired,
  options: PropTypes.array,
  displayValue: PropTypes.string,
  placeholder: PropTypes.string
};

// ==============================|| OWNER SECTION ||============================== //

function OwnerSection({ owner, onSave, clientId }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingOwner, setPendingOwner] = useState(null);

  const handleSelectOwner = (selectedUser) => {
    if (selectedUser && selectedUser.id !== owner?.id) {
      setPendingOwner(selectedUser);
      setConfirmOpen(true);
    } else {
      setEditing(false);
    }
  };

  const handleConfirmChange = async () => {
    setSaving(true);
    setConfirmOpen(false);
    const success = await onSave('owner_id', pendingOwner.id);
    setSaving(false);
    if (success) {
      setEditing(false);
    }
    setPendingOwner(null);
  };

  const handleCancelChange = () => {
    setConfirmOpen(false);
    setPendingOwner(null);
  };

  const ownerName = owner?.full_name || owner?.email || '-';

  return (
    <>
      <Box>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Owner (required)
          </Typography>
        </Stack>
        
        {editing ? (
          <Stack direction="row" spacing={1} alignItems="center">
            <Box flex={1}>
              <AsyncUserSelect
                clientId={clientId}
                value={null}
                onChange={handleSelectOwner}
                placeholder="Search users..."
                excludeIds={owner ? [owner.id] : []}
                disabled={saving}
                autoFocus
              />
            </Box>
            <IconButton size="small" onClick={() => setEditing(false)} disabled={saving}>
              <CloseOutlined />
            </IconButton>
          </Stack>
        ) : (
          <RemovableCard>
            <UserOutlined style={{ fontSize: 20, color: '#1890ff' }} />
            <Box flex={1}>
              <Typography variant="body2" fontWeight={500}>{ownerName}</Typography>
              {owner?.email && (
                <Typography variant="caption" color="text.secondary">{owner.email}</Typography>
              )}
            </Box>
            <Tooltip title="Change owner">
              <IconButton size="small" onClick={() => setEditing(true)}>
                <EditOutlined />
              </IconButton>
            </Tooltip>
          </RemovableCard>
        )}
      </Box>

      <ConfirmDialog
        open={confirmOpen}
        onClose={handleCancelChange}
        onConfirm={handleConfirmChange}
        title="Change Owner"
        message={`Are you sure you want to change the owner to ${pendingOwner?.full_name || pendingOwner?.email}?`}
        confirmLabel="Change"
        confirmColor="primary"
      />
    </>
  );
}

OwnerSection.propTypes = {
  owner: PropTypes.object,
  onSave: PropTypes.func.isRequired,
  clientId: PropTypes.string
};

// ==============================|| CONTACTS SECTION ||============================== //

function ContactsSection({ contacts = [], activityType, accountId, onSave, clientId }) {
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(null);

  // Fetch contacts for this account
  const { contacts: availableContacts = [], isLoading: contactsLoading } = useGetContacts({
    account_id: accountId,
    page_size: 100
  });

  // Filter out already selected contacts
  const contactOptions = availableContacts.filter(
    (c) => !contacts.some((selected) => selected.id === c.id)
  );

  const handleAddContact = async (contactId) => {
    if (!contactId) return;
    setSaving(true);
    const newContactIds = [...contacts.map((c) => c.id), contactId];
    const success = await onSave('contact_ids', newContactIds);
    setSaving(false);
    if (success) setAdding(false);
  };

  const handleRemoveContact = async () => {
    if (!confirmRemove) return;
    
    // Cannot remove if only 1 contact (required)
    if (contacts.length <= 1) {
      displayErrorSnackbar('At least one contact is required');
      setConfirmRemove(null);
      return;
    }
    
    setSaving(true);
    const newContactIds = contacts.filter((c) => c.id !== confirmRemove.id).map((c) => c.id);
    const success = await onSave('contact_ids', newContactIds);
    setSaving(false);
    setConfirmRemove(null);
  };

  // Determine which info to show based on activity type
  const showPhone = ['CALL'].includes(activityType);
  const showEmail = ['EMAIL', 'LINKEDIN'].includes(activityType);

  return (
    <>
      <Box>
        <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Contacts (required, min 1)
          </Typography>
          <IconButton size="small" onClick={() => setAdding(true)} disabled={adding || saving}>
            <PlusOutlined />
          </IconButton>
        </Stack>

        <Stack spacing={1}>
          {contacts.map((contact) => (
            <RemovableCard
              key={contact.id}
              onRemove={contacts.length > 1 ? () => setConfirmRemove(contact) : undefined}
              removeTooltip="Remove contact"
            >
              <TeamOutlined style={{ fontSize: 20, color: '#52c41a' }} />
              <Box flex={1}>
                <Typography variant="body2" fontWeight={500}>
                  {contact.full_name || `${contact.first_name || ''} ${contact.last_name || ''}`.trim()}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {contact.job_title || '-'}
                  {contact.department_name && ` • ${contact.department_name}`}
                </Typography>
                {showPhone && contact.phone_number && (
                  <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.5 }}>
                    <PhoneOutlined style={{ fontSize: 12, color: '#8c8c8c' }} />
                    <Typography variant="caption" color="primary.main">{contact.phone_number}</Typography>
                  </Stack>
                )}
                {showEmail && contact.email && (
                  <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.5 }}>
                    <MailOutlined style={{ fontSize: 12, color: '#8c8c8c' }} />
                    <Typography variant="caption" color="primary.main">{contact.email}</Typography>
                  </Stack>
                )}
              </Box>
            </RemovableCard>
          ))}

          {adding && (
            <Stack direction="row" spacing={1} alignItems="center">
              <Autocomplete
                options={contactOptions}
                getOptionLabel={(option) => option.full_name || `${option.first_name} ${option.last_name}`}
                onChange={(_, newValue) => {
                  if (newValue) handleAddContact(newValue.id);
                }}
                loading={contactsLoading}
                disabled={saving}
                size="small"
                fullWidth
                autoFocus
                openOnFocus
                renderInput={(params) => (
                  <TextField {...params} placeholder="Search contacts..." autoFocus />
                )}
                renderOption={(props, option) => (
                  <li {...props} key={option.id}>
                    <Box>
                      <Typography variant="body2">{option.full_name || `${option.first_name} ${option.last_name}`}</Typography>
                      <Typography variant="caption" color="text.secondary">{option.job_title || option.email}</Typography>
                    </Box>
                  </li>
                )}
              />
              <IconButton size="small" onClick={() => setAdding(false)} disabled={saving}>
                <CloseOutlined />
              </IconButton>
            </Stack>
          )}

          {contacts.length === 0 && !adding && (
            <Typography variant="body2" color="error.main">No contacts (required)</Typography>
          )}
        </Stack>
      </Box>

      <ConfirmDialog
        open={!!confirmRemove}
        onClose={() => setConfirmRemove(null)}
        onConfirm={handleRemoveContact}
        title="Remove Contact"
        message={`Remove ${confirmRemove?.full_name || 'this contact'} from activity?`}
        confirmLabel="Remove"
        confirmColor="error"
      />
    </>
  );
}

ContactsSection.propTypes = {
  contacts: PropTypes.array,
  activityType: PropTypes.string,
  accountId: PropTypes.string,
  onSave: PropTypes.func.isRequired,
  clientId: PropTypes.string
};

// ==============================|| INVITED USERS SECTION ||============================== //

function InvitedUsersSection({ invitedUsers = [], ownerId, onSave, clientId }) {
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(null);

  // Exclude owner and already invited users from selection
  const excludeIds = [
    ...(ownerId ? [ownerId] : []),
    ...invitedUsers.map((u) => u.id)
  ];

  const handleAddUser = async (selectedUser) => {
    if (!selectedUser) return;
    setSaving(true);
    const newUserIds = [...invitedUsers.map((u) => u.id), selectedUser.id];
    const success = await onSave('invited_user_ids', newUserIds);
    setSaving(false);
    if (success) setAdding(false);
  };

  const handleRemoveUser = async () => {
    if (!confirmRemove) return;
    setSaving(true);
    const newUserIds = invitedUsers.filter((u) => u.id !== confirmRemove.id).map((u) => u.id);
    const success = await onSave('invited_user_ids', newUserIds);
    setSaving(false);
    setConfirmRemove(null);
  };

  return (
    <>
      <Box>
        <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Invited Users (optional)
          </Typography>
          <IconButton size="small" onClick={() => setAdding(true)} disabled={adding || saving}>
            <PlusOutlined />
          </IconButton>
        </Stack>

        <Stack spacing={1}>
          {invitedUsers.map((user) => (
            <RemovableCard
              key={user.id}
              onRemove={() => setConfirmRemove(user)}
              removeTooltip="Remove user"
            >
              <UserOutlined style={{ fontSize: 20, color: '#722ed1' }} />
              <Box flex={1}>
                <Typography variant="body2" fontWeight={500}>
                  {user.full_name || user.email}
                </Typography>
                {user.email && user.full_name && (
                  <Typography variant="caption" color="text.secondary">{user.email}</Typography>
                )}
              </Box>
            </RemovableCard>
          ))}

          {adding && (
            <Stack direction="row" spacing={1} alignItems="center">
              <Box flex={1}>
                <AsyncUserSelect
                  clientId={clientId}
                  value={null}
                  onChange={handleAddUser}
                  placeholder="Search users..."
                  excludeIds={excludeIds}
                  disabled={saving}
                  autoFocus
                />
              </Box>
              <IconButton size="small" onClick={() => setAdding(false)} disabled={saving}>
                <CloseOutlined />
              </IconButton>
            </Stack>
          )}

          {invitedUsers.length === 0 && !adding && (
            <Typography variant="body2" color="text.secondary" fontStyle="italic">
              No invited users
            </Typography>
          )}
        </Stack>
      </Box>

      <ConfirmDialog
        open={!!confirmRemove}
        onClose={() => setConfirmRemove(null)}
        onConfirm={handleRemoveUser}
        title="Remove Invited User"
        message={`Remove ${confirmRemove?.full_name || confirmRemove?.email || 'this user'} from activity?`}
        confirmLabel="Remove"
        confirmColor="error"
      />
    </>
  );
}

InvitedUsersSection.propTypes = {
  invitedUsers: PropTypes.array,
  ownerId: PropTypes.string,
  onSave: PropTypes.func.isRequired,
  clientId: PropTypes.string
};

// ==============================|| LINKED ACTIVITY CARD ||============================== //

function LinkedActivityCard({ activity, label, onUnlink, unlinkLabel = 'Unlink' }) {
  const router = useRouter();
  const [confirmUnlink, setConfirmUnlink] = useState(false);

  if (!activity) {
    return (
      <Box>
        <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
          {label}
        </Typography>
        <Typography variant="body2" color="text.secondary" fontStyle="italic">None</Typography>
      </Box>
    );
  }

  const handleNavigate = () => {
    router.push(`/activities/${activity.id}`);
  };

  return (
    <>
      <Box>
        <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
          {label}
        </Typography>
        <RemovableCard onRemove={onUnlink ? () => setConfirmUnlink(true) : undefined} removeTooltip={unlinkLabel}>
          <LinkOutlined style={{ fontSize: 18, color: '#faad14' }} />
          <Box flex={1} sx={{ cursor: 'pointer' }} onClick={handleNavigate}>
            <Typography variant="body2" fontWeight={500} color="primary.main">
              {activity.title}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {ACTIVITY_TYPE_LABELS[activity.activity_type] || activity.activity_type}
              {' • '}
              {ACTIVITY_STATUS_LABELS[activity.status] || activity.status}
            </Typography>
          </Box>
        </RemovableCard>
      </Box>

      <ConfirmDialog
        open={confirmUnlink}
        onClose={() => setConfirmUnlink(false)}
        onConfirm={() => {
          setConfirmUnlink(false);
          onUnlink?.();
        }}
        title="Unlink Activity"
        message={`Unlink "${activity.title}" from this activity?`}
        confirmLabel="Unlink"
        confirmColor="warning"
      />
    </>
  );
}

LinkedActivityCard.propTypes = {
  activity: PropTypes.object,
  label: PropTypes.string.isRequired,
  onUnlink: PropTypes.func,
  unlinkLabel: PropTypes.string
};

// ==============================|| STATUS & RESULT SECTION ||============================== //

function StatusResultSection({ activity, onSave, onStatusChange }) {
  const [saving, setSaving] = useState(false);
  const [confirmReopen, setConfirmReopen] = useState(false);

  const status = activity?.status;
  const isCompleted = status === ACTIVITY_STATUSES.COMPLETED;
  const isCancelled = status === ACTIVITY_STATUSES.CANCELLED;
  const canComplete = !isCompleted && !isCancelled;
  const canCancel = !isCompleted && !isCancelled;
  const canReopen = isCompleted || isCancelled;

  const handleComplete = async () => {
    setSaving(true);
    try {
      const result = await completeActivity(activity.id, {});
      if (result.success) {
        displaySuccessSnackbar('Activity completed');
        onStatusChange?.();
      } else {
        displayErrorSnackbar(result.error || 'Failed to complete activity');
      }
    } catch (error) {
      displayErrorSnackbar(error.message || 'An error occurred');
    }
    setSaving(false);
  };

  const handleCancel = async () => {
    setSaving(true);
    try {
      const result = await cancelActivity(activity.id, {});
      if (result.success) {
        displaySuccessSnackbar('Activity cancelled');
        onStatusChange?.();
      } else {
        displayErrorSnackbar(result.error || 'Failed to cancel activity');
      }
    } catch (error) {
      displayErrorSnackbar(error.message || 'An error occurred');
    }
    setSaving(false);
  };

  const handleReopen = async () => {
    setConfirmReopen(false);
    setSaving(true);
    try {
      const result = await reopenActivity(activity.id, { status: ACTIVITY_STATUSES.PLANNED });
      if (result.success) {
        displaySuccessSnackbar('Activity reopened');
        onStatusChange?.();
      } else {
        displayErrorSnackbar(result.error || 'Failed to reopen activity');
      }
    } catch (error) {
      displayErrorSnackbar(error.message || 'An error occurred');
    }
    setSaving(false);
  };

  const handleOutcomeSave = async (fieldKey, value) => {
    // Use completeActivity to update outcome on completed activity
    if (isCompleted) {
      setSaving(true);
      try {
        const payload = fieldKey === 'outcome' 
          ? { outcome: value, outcome_notes: activity.outcome_notes }
          : { outcome: activity.outcome, outcome_notes: value };
        
        const result = await completeActivity(activity.id, payload);
        if (result.success) {
          displaySuccessSnackbar('Outcome updated');
          onStatusChange?.();
          setSaving(false);
          return true;
        } else {
          displayErrorSnackbar(result.error || 'Failed to update outcome');
        }
      } catch (error) {
        displayErrorSnackbar(error.message || 'An error occurred');
      }
      setSaving(false);
      return false;
    }
    // If not completed, use regular save
    return onSave(fieldKey, value);
  };

  const outcomeOptions = Object.entries(ACTIVITY_OUTCOME_LABELS).map(([value, label]) => ({
    value,
    label
  }));

  return (
    <>
      <Box>
        {/* Current Status */}
        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
          <Typography variant="caption" color="text.secondary">Status:</Typography>
          <Chip
            label={ACTIVITY_STATUS_LABELS[status] || status}
            color={ACTIVITY_STATUS_COLORS[status] || 'default'}
            size="small"
          />
        </Stack>

        {/* Action Buttons */}
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          {canComplete && (
            <Button
              variant="contained"
              color="success"
              size="small"
              startIcon={<CheckCircleOutlined />}
              onClick={handleComplete}
              disabled={saving}
            >
              Complete
            </Button>
          )}
          {canCancel && (
            <Button
              variant="outlined"
              color="error"
              size="small"
              startIcon={<StopOutlined />}
              onClick={handleCancel}
              disabled={saving}
            >
              Cancel
            </Button>
          )}
          {canReopen && (
            <Button
              variant="outlined"
              color="primary"
              size="small"
              startIcon={<ReloadOutlined />}
              onClick={() => setConfirmReopen(true)}
              disabled={saving}
            >
              Reopen
            </Button>
          )}
        </Stack>

        {/* Outcome Section (only if completed) */}
        {isCompleted && (
          <Box sx={{ p: 2, bgcolor: 'success.lighter', borderRadius: 1, border: '1px solid', borderColor: 'success.light' }}>
            <Typography variant="subtitle2" color="success.dark" sx={{ mb: 1.5 }}>
              Result
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <EditableField
                  label="Outcome"
                  value={activity.outcome}
                  fieldKey="outcome"
                  onSave={handleOutcomeSave}
                  type="select"
                  options={outcomeOptions}
                  displayValue={
                    activity.outcome ? (
                      <Chip
                        label={ACTIVITY_OUTCOME_LABELS[activity.outcome] || activity.outcome}
                        color={ACTIVITY_OUTCOME_COLORS[activity.outcome] || 'default'}
                        size="small"
                      />
                    ) : null
                  }
                />
              </Grid>
              <Grid item xs={12}>
                <EditableField
                  label="Outcome Notes"
                  value={activity.outcome_notes}
                  fieldKey="outcome_notes"
                  onSave={handleOutcomeSave}
                  type="textarea"
                />
              </Grid>
            </Grid>
          </Box>
        )}

        {/* Cancelled message */}
        {isCancelled && (
          <Box sx={{ p: 2, bgcolor: 'error.lighter', borderRadius: 1, border: '1px solid', borderColor: 'error.light' }}>
            <Typography variant="body2" color="error.dark">
              This activity was cancelled.
            </Typography>
          </Box>
        )}
      </Box>

      <ConfirmDialog
        open={confirmReopen}
        onClose={() => setConfirmReopen(false)}
        onConfirm={handleReopen}
        title="Reopen Activity"
        message="Reopening this activity will clear the outcome and result. Are you sure?"
        confirmLabel="Reopen"
        confirmColor="primary"
      />
    </>
  );
}

StatusResultSection.propTypes = {
  activity: PropTypes.object.isRequired,
  onSave: PropTypes.func.isRequired,
  onStatusChange: PropTypes.func
};

// ==============================|| MAIN COMPONENT ||============================== //

export default function ActivityOverviewTab({ activity, onUpdate, mutate }) {
  const router = useRouter();
  const { user } = useAuth();
  const clientId = user?.client_id;

  // Get account ID from activity
  const accountId = activity?.account_detail?.id || activity?.account;

  // Fetch decision cycles for this account
  const { cycles = [] } = useGetDecisionCyclesByAccount(accountId);

  // Get current cycle ID
  const currentCycleId = activity?.decision_cycle_detail?.id || activity?.decision_cycle;

  // Fetch steps for current cycle
  const { steps = [] } = useGetDecisionStepsByCycle(currentCycleId);

  // Build options for cycle/step selects
  const cycleOptions = cycles.map((c) => ({ value: c.id, label: c.name }));
  const stepOptions = steps.map((s) => ({ value: s.id, label: `${s.stage_display || s.stage}: ${s.name}` }));

  // ==============================|| SAVE HANDLER ||============================== //

  const handleSave = async (fieldKey, value) => {
    try {
      const payload = { [fieldKey]: value };
      
      // Special case: clearing cycle should also clear step
      if (fieldKey === 'decision_cycle_id' && !value) {
        payload.decision_step_id = null;
      }

      const result = await onUpdate(payload);
      if (result?.success !== false) {
        displaySuccessSnackbar('Updated successfully');
        mutate?.();
        return true;
      } else {
        displayErrorSnackbar(result?.error || 'Update failed');
        return false;
      }
    } catch (error) {
      displayErrorSnackbar(error.message || 'An error occurred');
      return false;
    }
  };

  const handleStatusChange = () => {
    mutate?.();
  };

  // Extract data from activity
  const contacts = activity?.contacts_detail || [];
  const owner = activity?.owner_detail;
  const invitedUsers = activity?.invited_users_detail || [];
  const previousActivity = activity?.previous_activity_info;
  const nextActivity = activity?.next_activity_info;

  // Type options
  const typeOptions = Object.entries(ACTIVITY_TYPE_LABELS).map(([value, label]) => ({
    value,
    label
  }));

  // Navigate to account
  const handleAccountClick = () => {
    if (accountId) {
      router.push(`/accounts/${accountId}`);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* ================================================================== */}
      {/* SECTION 1: DETAILS */}
      {/* ================================================================== */}
      <SectionHeader icon={FileTextOutlined} title="Details" />
      
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6}>
          <EditableField
            label="Type"
            value={activity?.activity_type}
            fieldKey="activity_type"
            onSave={handleSave}
            type="select"
            options={typeOptions}
            displayValue={ACTIVITY_TYPE_LABELS[activity?.activity_type] || activity?.activity_type}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <Box>
            <Typography variant="caption" color="text.secondary" gutterBottom display="block">
              Account
            </Typography>
            <Typography
              variant="body1"
              color="primary.main"
              sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
              onClick={handleAccountClick}
            >
              {activity?.account_detail?.company_name || '-'}
            </Typography>
          </Box>
        </Grid>
        <Grid item xs={12}>
          <EditableField
            label="Description"
            value={activity?.description}
            fieldKey="description"
            onSave={handleSave}
            type="textarea"
          />
        </Grid>
        <Grid item xs={12}>
          <EditableField
            label="Call to Action"
            value={activity?.call_to_action}
            fieldKey="call_to_action"
            onSave={handleSave}
            type="textarea"
          />
        </Grid>
      </Grid>

      <Divider sx={{ my: 3 }} />

      {/* ================================================================== */}
      {/* SECTION 2: PEOPLE */}
      {/* ================================================================== */}
      <SectionHeader icon={TeamOutlined} title="People" />
      
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={4}>
          <OwnerSection
            owner={owner}
            onSave={handleSave}
            clientId={clientId}
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <ContactsSection
            contacts={contacts}
            activityType={activity?.activity_type}
            accountId={accountId}
            onSave={handleSave}
            clientId={clientId}
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <InvitedUsersSection
            invitedUsers={invitedUsers}
            ownerId={owner?.id}
            onSave={handleSave}
            clientId={clientId}
          />
        </Grid>
      </Grid>

      <Divider sx={{ my: 3 }} />

      {/* ================================================================== */}
      {/* SECTION 3: SCHEDULE */}
      {/* ================================================================== */}
      <SectionHeader icon={CalendarOutlined} title="Schedule" />
      
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={4}>
          <EditableDateField
            label="Scheduled Date"
            value={activity?.scheduled_date}
            fieldKey="scheduled_date"
            onSave={handleSave}
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <EditableTimeField
            label="Scheduled Time"
            value={activity?.scheduled_time}
            fieldKey="scheduled_time"
            onSave={handleSave}
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <EditableDateField
            label="Due Date"
            value={activity?.due_date}
            fieldKey="due_date"
            onSave={handleSave}
          />
        </Grid>
      </Grid>

      <Divider sx={{ my: 3 }} />

      {/* ================================================================== */}
      {/* SECTION 4: STATUS & RESULT */}
      {/* ================================================================== */}
      <SectionHeader icon={CheckCircleOutlined} title="Status & Result" />
      
      <Box sx={{ mb: 3 }}>
        <StatusResultSection
          activity={activity}
          onSave={handleSave}
          onStatusChange={handleStatusChange}
        />
      </Box>

      <Divider sx={{ my: 3 }} />

      {/* ================================================================== */}
      {/* SECTION 5: LINKED ACTIVITIES */}
      {/* ================================================================== */}
      <SectionHeader icon={LinkOutlined} title="Linked Activities" />
      
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {/* Cycle & Step - Inline */}
        <Grid item xs={12}>
          <Stack direction="row" spacing={3} flexWrap="wrap" sx={{ mb: 2 }}>
            <InlineSelectField
              label="Cycle"
              value={currentCycleId}
              fieldKey="decision_cycle_id"
              onSave={handleSave}
              options={cycleOptions}
              displayValue={activity?.decision_cycle_detail?.name}
              placeholder="No cycle"
            />
            {currentCycleId && (
              <InlineSelectField
                label="Step"
                value={activity?.decision_step_detail?.id || activity?.decision_step}
                fieldKey="decision_step_id"
                onSave={handleSave}
                options={stepOptions}
                displayValue={activity?.decision_step_detail?.name}
                placeholder="No step"
              />
            )}
          </Stack>
        </Grid>

        {/* Previous & Next Activity */}
        <Grid item xs={12} sm={6}>
          <LinkedActivityCard
            activity={previousActivity}
            label="Previous Activity"
            onUnlink={() => handleSave('previous_activity_id', null)}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <LinkedActivityCard
            activity={nextActivity}
            label="Next Activity"
            onUnlink={() => handleSave('next_activity_id', null)}
          />
        </Grid>
      </Grid>

      <Divider sx={{ my: 3 }} />

      {/* ================================================================== */}
      {/* SECTION 6: COMING SOON */}
      {/* ================================================================== */}
      <SectionHeader icon={RocketOutlined} title="Coming Soon" />
      
      <Box
        sx={{
          p: 3,
          bgcolor: 'grey.50',
          borderRadius: 1,
          border: '1px dashed',
          borderColor: 'grey.300',
          textAlign: 'center'
        }}
      >
        <Typography variant="body2" color="text.secondary">
          AI-powered features coming soon: Meeting preparation, Email drafts, Call insights, and more.
        </Typography>
      </Box>
    </Box>
  );
}

ActivityOverviewTab.propTypes = {
  activity: PropTypes.object.isRequired,
  onUpdate: PropTypes.func.isRequired,
  mutate: PropTypes.func
};

