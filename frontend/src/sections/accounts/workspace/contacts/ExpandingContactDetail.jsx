// src/sections/accounts/workspace/contacts/ExpandingContactDetail.jsx

'use client';

import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import Link from '@mui/material/Link';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';

// assets
import MailOutlined from '@ant-design/icons/MailOutlined';
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import LinkedinOutlined from '@ant-design/icons/LinkedinOutlined';
import EnvironmentOutlined from '@ant-design/icons/EnvironmentOutlined';
import GlobalOutlined from '@ant-design/icons/GlobalOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';

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

// ==============================|| STAT ITEM ||============================== //

function StatItem({ label, value }) {
  return (
    <Stack spacing={0.5} alignItems="center">
      <Typography variant="h5">{value ?? 0}</Typography>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Stack>
  );
}

StatItem.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.number
};

// ==============================|| CONTACT INFO ITEM ||============================== //

function ContactInfoItem({ icon, label, value, isLink = false, href = '' }) {
  if (!value) return null;

  return (
    <ListItem sx={{ px: 0, py: 0.5 }}>
      <ListItemIcon sx={{ minWidth: 32 }}>
        {icon}
      </ListItemIcon>
      <ListItemText
        primary={
          <Typography variant="caption" color="text.secondary">
            {label}
          </Typography>
        }
        secondary={
          isLink ? (
            <Link
              href={href || value}
              target="_blank"
              rel="noopener noreferrer"
              underline="hover"
              sx={{ wordBreak: 'break-all' }}
            >
              {value}
            </Link>
          ) : (
            <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
              {value}
            </Typography>
          )
        }
        sx={{ my: 0 }}
      />
    </ListItem>
  );
}

ContactInfoItem.propTypes = {
  icon: PropTypes.node.isRequired,
  label: PropTypes.string.isRequired,
  value: PropTypes.string,
  isLink: PropTypes.bool,
  href: PropTypes.string
};

// ==============================|| EXPANDING CONTACT DETAIL ||============================== //

/**
 * ExpandingContactDetail Component
 * 
 * Displays contact details in an expanded table row.
 * Used with ReusableTable's expandedRowContent prop.
 * 
 * Layout:
 * - Left card: Contact profile (name, position, contact details, stats)
 * - Right section: Placeholder for future Activities & Signals
 * 
 * @param {Object} props
 * @param {Object} props.data - Contact data from table row
 */
export default function ExpandingContactDetail({ data }) {
  if (!data) return null;

  // Build full name
  const fullName = data.full_name || `${data.first_name || ''} ${data.last_name || ''}`.trim();

  // Build LinkedIn URL (normalize if needed)
  const linkedinUrl = data.linkedin?.startsWith('http')
    ? data.linkedin
    : data.linkedin
      ? `https://${data.linkedin}`
      : null;

  return (
    <Grid container spacing={2.5} sx={{ pl: { xs: 0, sm: 5, md: 6, lg: 10, xl: 12 }, py: 2 }}>
      {/* ==================== LEFT CARD - CONTACT PROFILE ==================== */}
      <Grid item xs={12} sm={5} md={4} xl={3.5}>
        <MainCard>
          {/* Influence Level Badge */}
          {data.influence_level && data.influence_level !== 'UNKNOWN' && (
            <Chip
              label={data.influence_level_display || data.influence_level}
              size="small"
              color={INFLUENCE_COLORS[data.influence_level] || 'default'}
              sx={{
                position: 'absolute',
                right: 8,
                top: 8,
                borderRadius: '4px'
              }}
            />
          )}

          <Grid container spacing={2}>
            {/* ==================== IDENTITY SECTION ==================== */}
            <Grid item xs={12}>
              <Stack spacing={0.5} alignItems="center" sx={{ pt: 1 }}>
                {/* Full Name */}
                <Typography variant="h5" textAlign="center">
                  {fullName || 'No Name'}
                </Typography>
                
                {/* Position (Job Title) */}
                {data.job_title && (
                  <Typography variant="body2" color="text.secondary" textAlign="center">
                    {data.job_title}
                  </Typography>
                )}
              </Stack>
            </Grid>

            <Grid item xs={12}>
              <Divider />
            </Grid>

            {/* ==================== STATS SECTION ==================== */}
            <Grid item xs={12}>
              <Stack
                direction="row"
                justifyContent="space-around"
                alignItems="center"
                sx={{ py: 1 }}
              >
                <StatItem label="Territories" value={data.territories_count || 0} />
                <Divider orientation="vertical" flexItem />
                <StatItem label="Campaigns" value={data.campaigns_count || 0} />
                <Divider orientation="vertical" flexItem />
                <StatItem label="Activities" value={data.activities_count || 0} />
              </Stack>
            </Grid>

            <Grid item xs={12}>
              <Divider />
            </Grid>

            {/* ==================== CONTACT DETAILS SECTION ==================== */}
            <Grid item xs={12}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Contact Details
              </Typography>
              <List disablePadding>
                <ContactInfoItem
                  icon={<PhoneOutlined />}
                  label="Phone"
                  value={data.phone_number}
                  isLink
                  href={`tel:${data.phone_number}`}
                />
                <ContactInfoItem
                  icon={<MailOutlined />}
                  label="Email"
                  value={data.email}
                  isLink
                  href={`mailto:${data.email}`}
                />
                <ContactInfoItem
                  icon={<EnvironmentOutlined />}
                  label="City"
                  value={data.city}
                />
                <ContactInfoItem
                  icon={<LinkedinOutlined />}
                  label="LinkedIn"
                  value={data.linkedin ? 'View Profile' : null}
                  isLink
                  href={linkedinUrl}
                />
              </List>
            </Grid>

            {/* ==================== BUYING AUTHORITY BADGE ==================== */}
            {data.has_buying_authority && (
              <>
                <Grid item xs={12}>
                  <Divider />
                </Grid>
                <Grid item xs={12}>
                  <Box sx={{ textAlign: 'center', py: 1 }}>
                    <Chip
                      label="Has Buying Authority"
                      size="small"
                      color="success"
                      variant="outlined"
                    />
                  </Box>
                </Grid>
              </>
            )}
          </Grid>
        </MainCard>
      </Grid>

      {/* ==================== RIGHT SECTION - ACTIVITIES & SIGNALS ==================== */}
      <Grid item xs={12} sm={7} md={8} xl={8.5}>
        <Stack spacing={2.5}>
          {/* Activities Placeholder */}
          <MainCard title="Activities">
            <Stack spacing={2} alignItems="center" py={4}>
              <GlobalOutlined style={{ fontSize: '2rem', color: '#8c8c8c' }} />
              <Typography variant="body1" color="text.secondary" textAlign="center">
                Contact activities will be displayed here.
              </Typography>
              <Chip label="Coming Soon" size="small" variant="outlined" />
            </Stack>
          </MainCard>

          {/* Signals Placeholder */}
          <MainCard title="Signals">
            <Stack spacing={2} alignItems="center" py={4}>
              <TeamOutlined style={{ fontSize: '2rem', color: '#8c8c8c' }} />
              <Typography variant="body1" color="text.secondary" textAlign="center">
                Contact signals and alerts will be displayed here.
              </Typography>
              <Chip label="Coming Soon" size="small" variant="outlined" />
            </Stack>
          </MainCard>
        </Stack>
      </Grid>
    </Grid>
  );
}

ExpandingContactDetail.propTypes = {
  data: PropTypes.shape({
    id: PropTypes.string,
    first_name: PropTypes.string,
    last_name: PropTypes.string,
    full_name: PropTypes.string,
    email: PropTypes.string,
    phone_number: PropTypes.string,
    job_title: PropTypes.string,
    linkedin: PropTypes.string,
    city: PropTypes.string,
    influence_level: PropTypes.string,
    influence_level_display: PropTypes.string,
    department_name: PropTypes.string,
    has_buying_authority: PropTypes.bool,
    territories_count: PropTypes.number,
    campaigns_count: PropTypes.number,
    activities_count: PropTypes.number
  })
};