// src/sections/accounts/workspace/AccountHeader.jsx

'use client';

import PropTypes from 'prop-types';

// material-ui
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';
import EditableField from './EditableField';
import EditableChip from './EditableChip';

// assets
import EnvironmentOutlined from '@ant-design/icons/EnvironmentOutlined';
import GlobalOutlined from '@ant-design/icons/GlobalOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';

// ==============================|| COMPANY LOGO HELPER ||============================== //

/**
 * Get company logo URL from website domain using Google Favicon API
 * @param {string} website - Company website URL
 * @param {number} size - Icon size (16, 32, 64, 128, 256)
 * @returns {string|null} Logo URL or null
 */
function getCompanyLogoUrl(website, size = 64) {
  if (!website) return null;

  try {
    // Handle URLs with or without protocol
    let urlString = website;
    if (!urlString.startsWith('http://') && !urlString.startsWith('https://')) {
      urlString = `https://${urlString}`;
    }
    const url = new URL(urlString);
    return `https://www.google.com/s2/favicons?domain=${url.hostname}&sz=${size}`;
  } catch {
    return null;
  }
}

/**
 * Get initials from company name for fallback avatar
 * @param {string} name - Company name
 * @returns {string} Initials (max 2 characters)
 */
function getCompanyInitials(name) {
  if (!name) return '?';

  const words = name.trim().split(/\s+/);
  if (words.length === 1) {
    return words[0].substring(0, 2).toUpperCase();
  }
  return (words[0][0] + words[1][0]).toUpperCase();
}

// ==============================|| TYPE/CLASSIFICATION OPTIONS ||============================== //

const TYPE_OPTIONS = [
  { value: 'CLIENT', label: 'Client' },
  { value: 'PROSPECT', label: 'Prospect' },
  { value: 'PARTNER', label: 'Partner' },
  { value: 'VENDOR', label: 'Vendor' },
  { value: 'OTHER', label: 'Other' }
];

const CLASSIFICATION_OPTIONS = [
  { value: 'SMB', label: 'SMB' },
  { value: 'MIDMARKET', label: 'Mid-Market' },
  { value: 'ENTERPRISE', label: 'Enterprise' },
  { value: 'STARTUP', label: 'Startup' },
  { value: 'NONPROFIT', label: 'Non-Profit' }
];

const TYPE_COLORS = {
  CLIENT: 'success',
  PROSPECT: 'warning',
  PARTNER: 'info',
  VENDOR: 'secondary',
  OTHER: 'default'
};

const CLASSIFICATION_COLORS = {
  ENTERPRISE: 'primary',
  MIDMARKET: 'info',
  SMB: 'success',
  STARTUP: 'warning',
  NONPROFIT: 'secondary'
};

// ==============================|| ACCOUNT HEADER - LOADING ||============================== //

function AccountHeaderSkeleton() {
  return (
    <MainCard sx={{ mb: 2 }}>
      <Stack spacing={2}>
        {/* Company name skeleton */}
        <Stack direction="row" alignItems="center" spacing={2}>
          <Skeleton variant="circular" width={56} height={56} />
          <Skeleton variant="text" width={280} height={40} />
          <Skeleton variant="rectangular" width={80} height={32} sx={{ borderRadius: 1 }} />
        </Stack>

        {/* Chips skeleton */}
        <Stack direction="row" spacing={1}>
          <Skeleton variant="rectangular" width={70} height={24} sx={{ borderRadius: 4 }} />
          <Skeleton variant="rectangular" width={90} height={24} sx={{ borderRadius: 4 }} />
          <Skeleton variant="rectangular" width={100} height={24} sx={{ borderRadius: 4 }} />
        </Stack>

        {/* Info row skeleton */}
        <Stack direction="row" spacing={3}>
          <Skeleton variant="text" width={120} height={20} />
          <Skeleton variant="text" width={140} height={20} />
          <Skeleton variant="text" width={100} height={20} />
        </Stack>

        {/* Stats skeleton */}
        <Stack direction="row" spacing={3} pt={1}>
          <Skeleton variant="text" width={80} height={20} />
          <Skeleton variant="text" width={80} height={20} />
          <Skeleton variant="text" width={90} height={20} />
          <Skeleton variant="text" width={70} height={20} />
        </Stack>
      </Stack>
    </MainCard>
  );
}

// ==============================|| ACCOUNT HEADER ||============================== //

/**
 * Account Header Component
 * 
 * Displays account information in the workspace header with inline editing:
 * - Company logo (from Google Favicon) with fallback initials
 * - Company name (editable)
 * - Type, Classification, Industry badges (editable)
 * - Location, Owner, Team info (editable)
 * - Stats summary
 * 
 * @param {Object} props
 * @param {Object} props.account - Account data from workspace endpoint
 * @param {Object} props.stats - Stats data from workspace endpoint
 * @param {boolean} props.loading - Loading state
 * @param {Function} props.onSave - Callback when a field is saved (fieldKey, newValue) => Promise
 * @param {Array} props.industryOptions - Industry options for dropdown
 */
export default function AccountHeader({ 
  account, 
  stats, 
  loading, 
  onSave,
  industryOptions = []
}) {
  // ==============================|| LOADING STATE ||============================== //

  if (loading) {
    return <AccountHeaderSkeleton />;
  }

  // ==============================|| NO DATA STATE ||============================== //

  if (!account) {
    return null;
  }

  // ==============================|| RENDER ||============================== //

  return (
    <MainCard sx={{ mb: 2 }}>
      <Stack spacing={2}>
        {/* Row 1: Logo, Company Name, Website */}
        <Stack
          direction="row"
          alignItems="center"
          spacing={2}
          sx={{ flexWrap: 'wrap' }}
        >
          {/* Company Logo/Avatar */}
          <Avatar
            src={getCompanyLogoUrl(account.website)}
            alt={account.company_name}
            sx={{
              width: 56,
              height: 56,
              bgcolor: 'primary.main',
              fontSize: '1.25rem',
              fontWeight: 600
            }}
          >
            {getCompanyInitials(account.company_name)}
          </Avatar>

          {/* Company Name - Editable */}
          <Box sx={{ flexGrow: 1 }}>
            <EditableField
              value={account.company_name}
              fieldKey="company_name"
              onSave={onSave}
              placeholder="Company name..."
              variant="h3"
              typographyProps={{ component: 'h1' }}
            />
          </Box>

          {/* Website Button */}
          {account.website && (
            <Button
              size="small"
              variant="outlined"
              color="secondary"
              startIcon={<GlobalOutlined />}
              href={account.website.startsWith('http') ? account.website : `https://${account.website}`}
              target="_blank"
              rel="noopener noreferrer"
              sx={{ flexShrink: 0 }}
            >
              Website
            </Button>
          )}
        </Stack>

        {/* Row 2: Type, Classification, Industry Badges - Editable */}
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
          <EditableChip
            value={account.type}
            fieldKey="type"
            options={TYPE_OPTIONS}
            onSave={onSave}
            placeholder="Add type..."
            color={TYPE_COLORS[account.type] || 'default'}
            variant="filled"
          />

          <EditableChip
            value={account.classification}
            fieldKey="classification"
            options={CLASSIFICATION_OPTIONS}
            onSave={onSave}
            placeholder="Add classification..."
            color={CLASSIFICATION_COLORS[account.classification] || 'default'}
            variant="outlined"
          />

          <EditableChip
            value={account.industry}
            fieldKey="industry"
            options={industryOptions}
            onSave={onSave}
            placeholder="Add industry..."
            color="default"
            variant="outlined"
          />
        </Stack>

        {/* Row 3: Location, Website URL, Owner, Team - Editable */}
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={{ xs: 1, sm: 3 }}
          flexWrap="wrap"
          useFlexGap
        >
          {/* Location - City, Country */}
          <EditableField
            value={[account.city, account.country].filter(Boolean).join(', ') || ''}
            fieldKey="location"
            onSave={async (key, value) => {
              // Parse city, country from combined value
              const parts = value.split(',').map(s => s.trim());
              const city = parts[0] || '';
              const country = parts[1] || '';
              // Save both fields
              if (onSave) {
                await onSave('city', city);
                if (country) {
                  await onSave('country', country);
                }
              }
            }}
            placeholder="Add location..."
            variant="body2"
            typographyProps={{ color: 'text.secondary' }}
            startIcon={<EnvironmentOutlined style={{ fontSize: 14 }} />}
          />

          {/* Website URL - Editable */}
          <EditableField
            value={account.website}
            fieldKey="website"
            onSave={onSave}
            placeholder="Add website..."
            variant="body2"
            typographyProps={{ color: 'text.secondary' }}
            startIcon={<GlobalOutlined style={{ fontSize: 14 }} />}
          />

          {/* Owner - Read only for now (would need user picker) */}
          {account.account_owner && (
            <Stack direction="row" spacing={0.5} alignItems="center">
              <UserOutlined style={{ fontSize: 14, color: 'inherit' }} />
              <Typography variant="body2" color="text.secondary">
                {account.account_owner.full_name}
              </Typography>
            </Stack>
          )}

          {/* Team - Read only (derived from owner) */}
          {account.team && (
            <Stack direction="row" spacing={0.5} alignItems="center">
              <TeamOutlined style={{ fontSize: 14, color: 'inherit' }} />
              <Typography variant="body2" color="text.secondary">
                {account.team.name}
              </Typography>
            </Stack>
          )}
        </Stack>

        {/* Row 4: Stats Summary */}
        {stats && (
          <Box
            sx={{
              pt: 1,
              borderTop: 1,
              borderColor: 'divider'
            }}
          >
            <Stack
              direction="row"
              spacing={{ xs: 2, sm: 4 }}
              flexWrap="wrap"
              useFlexGap
            >
              <StatItem label="Contacts" value={stats.contacts_count} />
              <StatItem label="Activities" value={stats.activities_count} />
              <StatItem label="Opportunities" value={stats.opportunities_count} />
              <StatItem label="Signals" value={stats.signals_count} />
            </Stack>
          </Box>
        )}
      </Stack>
    </MainCard>
  );
}

// ==============================|| STAT ITEM ||============================== //

function StatItem({ label, value }) {
  return (
    <Stack direction="row" spacing={0.5} alignItems="baseline">
      <Typography variant="h6" component="span">
        {value ?? 0}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </Stack>
  );
}

// ==============================|| PROP TYPES ||============================== //

AccountHeader.propTypes = {
  account: PropTypes.shape({
    id: PropTypes.string,
    company_name: PropTypes.string,
    industry: PropTypes.string,
    type: PropTypes.string,
    classification: PropTypes.string,
    website: PropTypes.string,
    city: PropTypes.string,
    country: PropTypes.string,
    account_owner: PropTypes.shape({
      id: PropTypes.string,
      full_name: PropTypes.string,
      email: PropTypes.string
    }),
    team: PropTypes.shape({
      id: PropTypes.string,
      name: PropTypes.string
    })
  }),
  stats: PropTypes.shape({
    contacts_count: PropTypes.number,
    activities_count: PropTypes.number,
    opportunities_count: PropTypes.number,
    signals_count: PropTypes.number
  }),
  loading: PropTypes.bool,
  onSave: PropTypes.func,
  industryOptions: PropTypes.arrayOf(
    PropTypes.shape({
      value: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired
    })
  )
};

StatItem.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.number
};