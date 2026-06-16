// frontend/src/sections/accounts/dc-workspace/PeopleTab.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useMemo } from "react";

// MUI
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import {
  InboxOutlined,
  TeamOutlined,
  UserOutlined,
  WarningOutlined,
} from "@ant-design/icons";

// Project imports
import { useGetDCPeople } from "api/accounts/decisionCycles";

// ==============================|| CONSTANTS ||============================== //

const ROLE_FILTERS = [
  { value: "all", label: "All" },
  { value: "CHAMPION", label: "Champion" },
  { value: "ECONOMIC_BUYER", label: "Economic Buyer" },
  { value: "DECISION_MAKER", label: "Decision Maker" },
  { value: "INFLUENCER", label: "Influencer" },
  { value: "BLOCKER", label: "Blocker" },
  { value: "END_USER", label: "End User" },
  { value: "PROCUREMENT", label: "Procurement" },
];

const CRITICAL_ROLES = ["CHAMPION", "ECONOMIC_BUYER", "DECISION_MAKER"];

const INFLUENCE_COLORS = {
  HIGH: "error",
  MEDIUM: "warning",
  LOW: "default",
};

// ==============================|| ROLE FILTER BAR ||============================== //

function RoleFilterBar({ activeRole, onChange, qualified }) {
  const roleCounts = useMemo(() => {
    const counts = { all: qualified.length };
    for (const q of qualified) {
      counts[q.role] = (counts[q.role] || 0) + 1;
    }
    return counts;
  }, [qualified]);

  return (
    <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap">
      <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
        Role:
      </Typography>
      {ROLE_FILTERS.map((f) => (
        <Chip
          key={f.value}
          label={`${f.label} (${roleCounts[f.value] || 0})`}
          size="small"
          variant={activeRole === f.value ? "filled" : "outlined"}
          color={activeRole === f.value ? "primary" : "default"}
          onClick={() => onChange(f.value)}
          clickable
        />
      ))}
    </Stack>
  );
}

RoleFilterBar.propTypes = {
  activeRole: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
  qualified: PropTypes.array.isRequired,
};

// ==============================|| COVERAGE ALERT ||============================== //

function CoverageAlert({ qualified }) {
  const missingRoles = useMemo(() => {
    const presentRoles = new Set(qualified.map((q) => q.role));
    return CRITICAL_ROLES.filter((r) => !presentRoles.has(r));
  }, [qualified]);

  if (missingRoles.length === 0) return null;

  const labels = missingRoles.map((r) => {
    const filter = ROLE_FILTERS.find((f) => f.value === r);
    return filter ? filter.label : r;
  });

  return (
    <Alert
      severity="warning"
      icon={<WarningOutlined style={{ fontSize: 16 }} />}
      sx={{ mb: 2 }}
    >
      Missing critical roles: <strong>{labels.join(", ")}</strong>
    </Alert>
  );
}

CoverageAlert.propTypes = {
  qualified: PropTypes.array.isRequired,
};

// ==============================|| CONTACT NAME HELPER ||============================== //

function contactDisplayName(contact) {
  if (!contact) return "Unknown";
  const parts = [contact.first_name, contact.last_name].filter(Boolean);
  return parts.length > 0 ? parts.join(" ") : "Unknown";
}

// ==============================|| QUALIFIED PERSON CARD ||============================== //

function QualifiedPersonCard({ person }) {
  const contactName = contactDisplayName(person.target_contact);
  const jobTitle = person.target_contact?.job_title;

  return (
    <Box
      sx={{
        p: 1.5,
        border: 1,
        borderColor: "divider",
        borderRadius: 1.5,
      }}
    >
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
        <Stack spacing={0.5}>
          <Stack direction="row" spacing={1} alignItems="center">
            <UserOutlined style={{ fontSize: 14, color: "#8c8c8c" }} />
            <Typography variant="body2" fontWeight={600}>
              {contactName}
            </Typography>
          </Stack>
          {jobTitle && (
            <Typography variant="caption" color="text.secondary" sx={{ pl: 2.75 }}>
              {jobTitle}
            </Typography>
          )}
        </Stack>
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Chip
            label={person.role_display}
            size="small"
            color="primary"
            variant="outlined"
          />
          {person.influence_display && (
            <Chip
              label={person.influence_display}
              size="small"
              color={INFLUENCE_COLORS[person.influence] || "default"}
              variant="outlined"
            />
          )}
        </Stack>
      </Stack>
      {person.notes && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{
            mt: 1,
            display: "block",
            pl: 2.75,
            maxWidth: 500,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {person.notes}
        </Typography>
      )}
    </Box>
  );
}

QualifiedPersonCard.propTypes = {
  person: PropTypes.shape({
    signal_id: PropTypes.string,
    role: PropTypes.string,
    role_display: PropTypes.string,
    influence: PropTypes.string,
    influence_display: PropTypes.string,
    target_contact: PropTypes.shape({
      id: PropTypes.string,
      first_name: PropTypes.string,
      last_name: PropTypes.string,
      job_title: PropTypes.string,
    }),
    target_department: PropTypes.shape({
      id: PropTypes.string,
      name: PropTypes.string,
    }),
    notes: PropTypes.string,
    status: PropTypes.string,
  }).isRequired,
};

// ==============================|| UNQUALIFIED CONTACT ROW ||============================== //

function UnqualifiedContactRow({ entry }) {
  const contactName = contactDisplayName(entry.contact);
  const jobTitle = entry.contact?.job_title;
  const deptName = entry.department?.name;

  return (
    <Box
      sx={{
        p: 1.5,
        border: 1,
        borderColor: "divider",
        borderRadius: 1.5,
        borderStyle: "dashed",
      }}
    >
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Stack direction="row" spacing={1} alignItems="center">
          <UserOutlined style={{ fontSize: 14, color: "#8c8c8c" }} />
          <Box>
            <Typography variant="body2" fontWeight={500}>
              {contactName}
            </Typography>
            {(jobTitle || deptName) && (
              <Typography variant="caption" color="text.secondary">
                {[jobTitle, deptName].filter(Boolean).join(" · ")}
              </Typography>
            )}
          </Box>
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="caption" color="text.secondary">
            {entry.activity_count} activit{entry.activity_count === 1 ? "y" : "ies"}
          </Typography>
          <Chip label="Unqualified" size="small" variant="outlined" />
        </Stack>
      </Stack>
    </Box>
  );
}

UnqualifiedContactRow.propTypes = {
  entry: PropTypes.shape({
    contact: PropTypes.shape({
      id: PropTypes.string,
      first_name: PropTypes.string,
      last_name: PropTypes.string,
      job_title: PropTypes.string,
    }),
    department: PropTypes.shape({
      id: PropTypes.string,
      name: PropTypes.string,
    }),
    activity_count: PropTypes.number,
  }).isRequired,
};

// ==============================|| PEOPLE TAB ||============================== //

export default function PeopleTab({ cycleId, accountId }) {
  const { people, peopleLoading, peopleError, mutatePeople } =
    useGetDCPeople(cycleId);

  const [roleFilter, setRoleFilter] = useState("all");

  const qualified = people?.qualified || [];
  const unqualified = people?.unqualified || [];

  // Filter qualified by role
  const filteredQualified = useMemo(() => {
    if (roleFilter === "all") return qualified;
    return qualified.filter((q) => q.role === roleFilter);
  }, [qualified, roleFilter]);

  // Group qualified by department
  const groupedByDept = useMemo(() => {
    const groups = {};
    for (const person of filteredQualified) {
      const deptName = person.target_department?.name || "Unassigned";
      if (!groups[deptName]) groups[deptName] = [];
      groups[deptName].push(person);
    }
    const sorted = Object.entries(groups).sort(([a], [b]) => {
      if (a === "Unassigned") return 1;
      if (b === "Unassigned") return -1;
      return a.localeCompare(b);
    });
    return sorted;
  }, [filteredQualified]);

  // Loading
  if (peopleLoading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
      >
        <CircularProgress />
      </Box>
    );
  }

  // Error
  if (peopleError) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
      >
        <Typography color="error">Failed to load people</Typography>
      </Box>
    );
  }

  // Empty
  if (qualified.length === 0 && unqualified.length === 0) {
    return (
      <Box
        display="flex"
        flexDirection="column"
        justifyContent="center"
        alignItems="center"
        minHeight="300px"
        gap={1}
      >
        <InboxOutlined style={{ fontSize: 36, color: "#8c8c8c" }} />
        <Typography color="text.secondary">
          No people identified in this cycle yet.
        </Typography>
        <Typography variant="caption" color="text.secondary">
          People are extracted from activity transcripts or qualified manually.
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Coverage alert */}
      <CoverageAlert qualified={qualified} />

      {/* Role filter bar */}
      <RoleFilterBar
        activeRole={roleFilter}
        onChange={setRoleFilter}
        qualified={qualified}
      />

      {/* Qualified section */}
      {qualified.length > 0 && (
        <Box sx={{ mt: 2.5 }}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
            <TeamOutlined style={{ fontSize: 16 }} />
            <Typography variant="subtitle2" fontWeight={600}>
              Qualified ({filteredQualified.length})
            </Typography>
          </Stack>

          {filteredQualified.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: "center" }}>
              No people match this role filter.
            </Typography>
          ) : (
            <Stack spacing={2}>
              {groupedByDept.map(([deptName, persons]) => (
                <Box key={deptName}>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    fontWeight={600}
                    sx={{ mb: 0.75, display: "block", textTransform: "uppercase", letterSpacing: 0.5 }}
                  >
                    {deptName}
                  </Typography>
                  <Stack spacing={1}>
                    {persons.map((person) => (
                      <QualifiedPersonCard key={person.signal_id} person={person} />
                    ))}
                  </Stack>
                </Box>
              ))}
            </Stack>
          )}
        </Box>
      )}

      {/* Divider between sections */}
      {qualified.length > 0 && unqualified.length > 0 && (
        <Divider sx={{ my: 3 }} />
      )}

      {/* Unqualified section */}
      {unqualified.length > 0 && (
        <Box>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
            <UserOutlined style={{ fontSize: 16 }} />
            <Typography variant="subtitle2" fontWeight={600}>
              Unqualified ({unqualified.length})
            </Typography>
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1.5, display: "block" }}>
            Contacts found in cycle activities without a people signal. Role qualification requires linking to a source activity (coming soon).
          </Typography>
          <Stack spacing={1}>
            {unqualified.map((entry) => (
              <UnqualifiedContactRow
                key={entry.contact?.id || Math.random()}
                entry={entry}
              />
            ))}
          </Stack>
        </Box>
      )}
    </Box>
  );
}

PeopleTab.propTypes = {
  cycleId: PropTypes.string.isRequired,
  accountId: PropTypes.string.isRequired,
};
