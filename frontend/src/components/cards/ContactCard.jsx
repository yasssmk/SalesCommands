// frontend/src/components/cards/ContactCard.jsx
/**
 * ContactCard Component
 * 
 * Displays an external contact with name, job title, department,
 * and optional contact information (phone/email).
 * 
 * Used in:
 * - Activity Overview (External Contacts)
 * - Decision Step (Contacts)
 * - Account Contacts list
 */

'use client';

import PropTypes from 'prop-types';

// MUI
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// Project imports
import RemovableCard from './RemovableCard';

// Icons
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import MailOutlined from '@ant-design/icons/MailOutlined';
import LinkedinOutlined from '@ant-design/icons/LinkedinOutlined';

// ==============================|| HELPERS ||============================== //

/**
 * Get initials from contact name
 */
function getContactInitials(contact) {
  if (!contact) return '?';
  
  const firstName = contact.first_name || '';
  const lastName = contact.last_name || '';
  
  if (firstName && lastName) {
    return `${firstName[0]}${lastName[0]}`.toUpperCase();
  }
  
  const fullName = contact.full_name || '';
  if (fullName) {
    const parts = fullName.trim().split(/\s+/);
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return fullName.substring(0, 2).toUpperCase();
  }
  
  return '?';
}

/**
 * Get display name from contact object
 */
function getContactDisplayName(contact) {
  if (!contact) return 'Unknown';
  
  if (contact.full_name) return contact.full_name;
  
  const firstName = contact.first_name || '';
  const lastName = contact.last_name || '';
  
  return `${firstName} ${lastName}`.trim() || contact.email || 'Unknown';
}

// ==============================|| CONTACT INFO LINE ||============================== //

function ContactInfoLine({ icon: Icon, value, type = 'text' }) {
  if (!value) return null;

  const handleClick = () => {
    if (type === 'phone') {
      window.location.href = `tel:${value}`;
    } else if (type === 'email') {
      window.location.href = `mailto:${value}`;
    } else if (type === 'linkedin') {
      window.open(value, '_blank');
    }
  };

  return (
    <Stack 
      direction="row" 
      spacing={0.5} 
      alignItems="center" 
      sx={{ 
        cursor: type !== 'text' ? 'pointer' : 'default',
        '&:hover': type !== 'text' ? { 
          '& .contact-value': { textDecoration: 'underline' } 
        } : {}
      }}
      onClick={type !== 'text' ? handleClick : undefined}
    >
      <Icon style={{ fontSize: 12, color: '#8c8c8c' }} />
      <Typography 
        variant="caption" 
        color={type !== 'text' ? 'primary.main' : 'text.secondary'}
        className="contact-value"
      >
        {value}
      </Typography>
    </Stack>
  );
}

ContactInfoLine.propTypes = {
  icon: PropTypes.elementType.isRequired,
  value: PropTypes.string,
  type: PropTypes.oneOf(['text', 'phone', 'email', 'linkedin'])
};

// ==============================|| CONTACT CARD ||============================== //

export default function ContactCard({
  contact,
  onRemove,
  showPhone = false,
  showEmail = false,
  showLinkedin = false,
  showAvatar = true,
  size = 'medium',
  variant = 'default',
  onClick,
  sx = {}
}) {
  if (!contact) {
    return (
      <Typography variant="body2" color="text.disabled" fontStyle="italic" sx={sx}>
        No contact
      </Typography>
    );
  }

  // Size configurations
  const sizeConfig = {
    small: {
      avatarSize: 28,
      iconSize: 16,
      nameVariant: 'body2',
      infoVariant: 'caption',
      padding: 1,
      spacing: 0
    },
    medium: {
      avatarSize: 36,
      iconSize: 20,
      nameVariant: 'body2',
      infoVariant: 'caption',
      padding: 1.5,
      spacing: 0.25
    },
    large: {
      avatarSize: 44,
      iconSize: 24,
      nameVariant: 'subtitle1',
      infoVariant: 'body2',
      padding: 2,
      spacing: 0.5
    }
  };

  const config = sizeConfig[size];
  const displayName = getContactDisplayName(contact);
  const initials = getContactInitials(contact);

  // Build job info line
  const jobInfo = [
    contact.job_title,
    contact.department_name || contact.department
  ].filter(Boolean).join(' • ');

  return (
    <RemovableCard
      onRemove={onRemove}
      removeTooltip="Remove contact"
      variant={variant}
      onClick={onClick}
      sx={{ p: config.padding, ...sx }}
    >
      {/* Avatar or Icon */}
      {showAvatar ? (
        <Avatar
          src={contact.avatar}
          alt={displayName}
          sx={{
            width: config.avatarSize,
            height: config.avatarSize,
            bgcolor: 'success.main',
            fontSize: config.avatarSize * 0.4
          }}
        >
          {initials}
        </Avatar>
      ) : (
        <TeamOutlined style={{ fontSize: config.iconSize, color: '#52c41a' }} />
      )}

      {/* Contact info */}
      <Box flex={1} minWidth={0}>
        <Stack spacing={config.spacing}>
          {/* Name */}
          <Typography 
            variant={config.nameVariant} 
            fontWeight={500} 
            noWrap
          >
            {displayName}
          </Typography>
          
          {/* Job title & Department */}
          {jobInfo && (
            <Typography 
              variant={config.infoVariant} 
              color="text.secondary" 
              noWrap
            >
              {jobInfo}
            </Typography>
          )}
          
          {/* Contact details */}
          {(showPhone || showEmail || showLinkedin) && (
            <Stack spacing={0.25}>
              {showPhone && contact.phone_number && (
                <ContactInfoLine 
                  icon={PhoneOutlined} 
                  value={contact.phone_number} 
                  type="phone" 
                />
              )}
              {showEmail && contact.email && (
                <ContactInfoLine 
                  icon={MailOutlined} 
                  value={contact.email} 
                  type="email" 
                />
              )}
              {showLinkedin && contact.linkedin && (
                <ContactInfoLine 
                  icon={LinkedinOutlined} 
                  value="LinkedIn Profile" 
                  type="linkedin" 
                />
              )}
            </Stack>
          )}
        </Stack>
      </Box>
    </RemovableCard>
  );
}

ContactCard.propTypes = {
  /** Contact object */
  contact: PropTypes.shape({
    id: PropTypes.string,
    full_name: PropTypes.string,
    first_name: PropTypes.string,
    last_name: PropTypes.string,
    job_title: PropTypes.string,
    department: PropTypes.string,
    department_name: PropTypes.string,
    phone_number: PropTypes.string,
    email: PropTypes.string,
    linkedin: PropTypes.string,
    avatar: PropTypes.string
  }),
  /** Callback when remove button is clicked */
  onRemove: PropTypes.func,
  /** Show phone number */
  showPhone: PropTypes.bool,
  /** Show email */
  showEmail: PropTypes.bool,
  /** Show LinkedIn link */
  showLinkedin: PropTypes.bool,
  /** Show avatar (vs icon) */
  showAvatar: PropTypes.bool,
  /** Size variant */
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  /** Visual variant */
  variant: PropTypes.oneOf(['default', 'outlined', 'filled']),
  /** Click handler */
  onClick: PropTypes.func,
  /** Additional styles */
  sx: PropTypes.object
};