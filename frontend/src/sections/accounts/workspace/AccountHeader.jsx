// src/sections/accounts/workspace/AccountHeader.jsx

"use client";

import PropTypes from "prop-types";

import { useState } from "react";

// material-ui
import { useTheme } from "@mui/material/styles";
import IconButton from "@mui/material/IconButton";
import Avatar from "@mui/material/Avatar";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import ListItemIcon from "@mui/material/ListItemIcon";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Typography from "@mui/material/Typography";

// project imports
import EditableField from "./EditableField";
import EditableChip from "./EditableChip";
import AddToCampaignModal from "sections/campaigns/AddToCampaignModal";

// assets
import AimOutlined from "@ant-design/icons/AimOutlined";
import EnvironmentOutlined from "@ant-design/icons/EnvironmentOutlined";
import GlobalOutlined from "@ant-design/icons/GlobalOutlined";
import MoreOutlined from "@ant-design/icons/MoreOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import UserOutlined from "@ant-design/icons/UserOutlined";

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
    if (!urlString.startsWith("http://") && !urlString.startsWith("https://")) {
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
  if (!name) return "?";

  const words = name.trim().split(/\s+/);
  if (words.length === 1) {
    return words[0].substring(0, 2).toUpperCase();
  }
  return (words[0][0] + words[1][0]).toUpperCase();
}

// ==============================|| TYPE/CLASSIFICATION OPTIONS ||============================== //

const TYPE_OPTIONS = [
  { value: "CLIENT", label: "Client" },
  { value: "PROSPECT", label: "Prospect" },
  { value: "PARTNER", label: "Partner" },
  { value: "VENDOR", label: "Vendor" },
  { value: "OTHER", label: "Other" },
];

const CLASSIFICATION_OPTIONS = [
  { value: "SMB", label: "SMB" },
  { value: "MIDMARKET", label: "Mid-Market" },
  { value: "ENTERPRISE", label: "Enterprise" },
  { value: "STARTUP", label: "Startup" },
  { value: "NONPROFIT", label: "Non-Profit" },
];

const TYPE_COLORS = {
  CLIENT: "success",
  PROSPECT: "warning",
  PARTNER: "info",
  VENDOR: "secondary",
  OTHER: "default",
};

const CLASSIFICATION_COLORS = {
  ENTERPRISE: "primary",
  MIDMARKET: "info",
  SMB: "success",
  STARTUP: "warning",
  NONPROFIT: "secondary",
};

// ==============================|| ACCOUNT HEADER PROPS HOOK ||============================== //

/**
 * Hook that builds WorkspaceLayout-compatible header props from Account data.
 *
 * Maps Account header rows to WorkspaceLayout slots:
 *   Row 1 → avatar, title (onTitleSave), headerActions (Website button)
 *   Row 2 → chips (EditableChip: type, classification, industry)
 *   Row 3 → infoItems (location, website, owner, team)
 *   Stats → headerFooter (with own borderTop via WorkspaceLayout)
 *
 * @param {Object} params
 * @param {Object} params.account - Account data
 * @param {Object} params.stats - Stats data { contacts_count, activities_count, ... }
 * @param {Function} params.onSave - (fieldKey, newValue) => Promise<boolean>
 * @param {Array} params.industryOptions - [{ value, label }]
 * @returns {Object} Props object spread into <WorkspaceLayout {...props} />
 */
export default function useAccountHeaderProps({
  account,
  stats,
  onSave,
  industryOptions = [],
}) {
  const theme = useTheme();

  const [menuAnchor, setMenuAnchor] = useState(null);
  const [addToCampaignOpen, setAddToCampaignOpen] = useState(false);

  if (!account) {
    return {
      avatar: null,
      title: "",
      chips: [],
      infoItems: [],
      headerFooter: null,
    };
  }

  // ==============================|| ROW 1: Avatar + Title + Actions ||============================== //

  const avatar = (
    <Avatar
      src={getCompanyLogoUrl(account.website)}
      alt={account.company_name}
      sx={{
        width: 56,
        height: 56,
        bgcolor: "primary.main",
        fontSize: "1.25rem",
        fontWeight: 600,
      }}
    >
      {getCompanyInitials(account.company_name)}
    </Avatar>
  );

  const title = account.company_name || "";

  const onTitleSave = onSave
    ? (fieldKey, value) => onSave("company_name", value)
    : undefined;

  const headerActions = (
    <>
      {account.website && (
        <Button
          size="small"
          variant="outlined"
          color="secondary"
          startIcon={<GlobalOutlined />}
          href={
            account.website.startsWith("http")
              ? account.website
              : `https://${account.website}`
          }
          target="_blank"
          rel="noopener noreferrer"
          sx={{ flexShrink: 0 }}
        >
          Website
        </Button>
      )}
      <IconButton onClick={(e) => setMenuAnchor(e.currentTarget)}>
        <MoreOutlined />
      </IconButton>
      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={() => setMenuAnchor(null)}
      >
        <MenuItem
          onClick={() => {
            setMenuAnchor(null);
            setAddToCampaignOpen(true);
          }}
        >
          <ListItemIcon>
            <AimOutlined />
          </ListItemIcon>
          <Typography>Add to Campaign</Typography>
        </MenuItem>
      </Menu>
      <AddToCampaignModal
        open={addToCampaignOpen}
        onClose={() => setAddToCampaignOpen(false)}
        accountId={account.id}
        accountName={account.company_name}
      />
    </>
  );

  // ==============================|| ROW 2: Chips ||============================== //

  const chips = [
    <EditableChip
      key="type"
      value={account.type}
      fieldKey="type"
      options={TYPE_OPTIONS}
      onSave={onSave}
      placeholder="Add type..."
      color={TYPE_COLORS[account.type] || "default"}
      variant="filled"
    />,
    <EditableChip
      key="classification"
      value={account.classification}
      fieldKey="classification"
      options={CLASSIFICATION_OPTIONS}
      onSave={onSave}
      placeholder="Add classification..."
      color={CLASSIFICATION_COLORS[account.classification] || "default"}
      variant="outlined"
    />,
    <EditableChip
      key="industry"
      value={account.industry}
      fieldKey="industry"
      options={industryOptions}
      onSave={onSave}
      placeholder="Add industry..."
      color="default"
      variant="outlined"
    />,
  ];

  // ==============================|| EXTRA ROWS (before divider) ||============================== //

  const extraRows = [
    <Stack
      key="info-row"
      direction={{ xs: "column", sm: "row" }}
      spacing={{ xs: 1, sm: 3 }}
      flexWrap="wrap"
      useFlexGap
    >
      <EditableField
        value={[account.city, account.country].filter(Boolean).join(", ") || ""}
        fieldKey="location"
        onSave={async (key, value) => {
          const parts = value.split(",").map((s) => s.trim());
          const city = parts[0] || "";
          const country = parts[1] || "";
          if (onSave) {
            await onSave("city", city);
            if (country) await onSave("country", country);
          }
        }}
        placeholder="Add location..."
        variant="body2"
        typographyProps={{ color: "text.secondary" }}
        startIcon={
          <EnvironmentOutlined style={{ fontSize: theme.iconSizes.sm }} />
        }
      />
      <EditableField
        value={account.website}
        fieldKey="website"
        onSave={onSave}
        placeholder="Add website..."
        variant="body2"
        typographyProps={{ color: "text.secondary" }}
        startIcon={<GlobalOutlined style={{ fontSize: theme.iconSizes.sm }} />}
      />
      {account.account_owner && (
        <Stack direction="row" spacing={0.5} alignItems="center">
          <UserOutlined
            style={{ fontSize: theme.iconSizes.sm, color: "inherit" }}
          />
          <Typography variant="body2" color="text.secondary">
            {account.account_owner.full_name}
          </Typography>
        </Stack>
      )}
      {account.team && (
        <Stack direction="row" spacing={0.5} alignItems="center">
          <TeamOutlined
            style={{ fontSize: theme.iconSizes.sm, color: "inherit" }}
          />
          <Typography variant="body2" color="text.secondary">
            {account.team.name}
          </Typography>
        </Stack>
      )}
    </Stack>,
  ];

  // ==============================|| INFO ITEMS (after divider — stats) ||============================== //

  const infoItems = stats
    ? [
        <StatItem
          key="contacts"
          label="Contacts"
          value={stats.contacts_count}
        />,
        <StatItem
          key="activities"
          label="Activities"
          value={stats.activities_count}
        />,
        <StatItem
          key="opportunities"
          label="Opportunities"
          value={stats.opportunities_count}
        />,
        <StatItem key="signals" label="Signals" value={stats.signals_count} />,
      ]
    : [];

  return {
    avatar,
    title,
    onTitleSave,
    headerActions,
    chips,
    extraRows,
    infoItems,
  };
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
