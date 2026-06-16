// frontend/src/sections/accounts/dc-workspace/PeopleTab.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// MUI
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// Icons
import {
  InboxOutlined,
  PlusOutlined,
  TeamOutlined,
  UserOutlined,
  WarningOutlined,
} from "@ant-design/icons";

// Project imports
import { useGetDCPeople } from "api/accounts/decisionCycles";
import { createSignal } from "api/signals/signals";
import AsyncContactSelect from "components/AsyncSelection/AsyncContactSelect";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

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

const ROLE_OPTIONS = ROLE_FILTERS.filter((f) => f.value !== "all");

const INFLUENCE_OPTIONS = [
  { value: "HIGH", label: "High" },
  { value: "MEDIUM", label: "Medium" },
  { value: "LOW", label: "Low" },
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

// ==============================|| QUALIFY DIALOG ||============================== //

function QualifyDialog({
  open,
  onClose,
  onSubmit,
  loading,
  prefilledContact,
  accountId,
  showContactPicker,
}) {
  const [contact, setContact] = useState(prefilledContact || null);
  const [role, setRole] = useState("");
  const [influence, setInfluence] = useState("");
  const [notes, setNotes] = useState("");

  const contactFilters = useMemo(() => ({ account_id: accountId }), [accountId]);

  const handleSubmit = () => {
    const payload = {
      role,
      target_contact: contact?.id || null,
      notes: notes.trim(),
    };
    if (influence) {
      payload.influence = influence;
    }
    onSubmit(payload);
  };

  const canSubmit = Boolean(role) && Boolean(contact);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>
        {showContactPicker ? "Add Stakeholder" : "Qualify Role"}
      </DialogTitle>
      <DialogContent sx={{ pt: 2, display: "flex", flexDirection: "column", gap: 2 }}>
        {showContactPicker ? (
          <AsyncContactSelect
            value={contact}
            onChange={(_, val) => setContact(val)}
            filters={contactFilters}
            label="Contact"
            placeholder="Search account contacts..."
          />
        ) : (
          <TextField
            label="Contact"
            size="small"
            value={contactDisplayName(contact)}
            disabled
            sx={{ mt: 1 }}
          />
        )}
        <TextField
          label="Role"
          size="small"
          select
          required
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
          {ROLE_OPTIONS.map((o) => (
            <MenuItem key={o.value} value={o.value}>
              {o.label}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label="Influence"
          size="small"
          select
          value={influence}
          onChange={(e) => setInfluence(e.target.value)}
        >
          <MenuItem value="">—</MenuItem>
          {INFLUENCE_OPTIONS.map((o) => (
            <MenuItem key={o.value} value={o.value}>
              {o.label}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label="Notes"
          size="small"
          multiline
          minRows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} size="small">
          Cancel
        </Button>
        <Button
          variant="contained"
          size="small"
          onClick={handleSubmit}
          disabled={!canSubmit || loading}
          startIcon={loading ? <CircularProgress size={14} /> : null}
        >
          Qualify
        </Button>
      </DialogActions>
    </Dialog>
  );
}

QualifyDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSubmit: PropTypes.func.isRequired,
  loading: PropTypes.bool,
  prefilledContact: PropTypes.object,
  accountId: PropTypes.string.isRequired,
  showContactPicker: PropTypes.bool,
};

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

function UnqualifiedContactRow({ entry, onQualify }) {
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
          <Button
            size="small"
            variant="outlined"
            onClick={() => onQualify(entry)}
          >
            Qualify Role
          </Button>
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
  onQualify: PropTypes.func.isRequired,
};

// ==============================|| PEOPLE TAB ||============================== //

export default function PeopleTab({ cycleId, accountId }) {
  const { people, peopleLoading, peopleError, mutatePeople } =
    useGetDCPeople(cycleId);

  const [roleFilter, setRoleFilter] = useState("all");

  // Qualify dialog state
  const [qualifyOpen, setQualifyOpen] = useState(false);
  const [qualifyLoading, setQualifyLoading] = useState(false);
  const [qualifyContact, setQualifyContact] = useState(null);
  const [qualifyDept, setQualifyDept] = useState(null);
  const [showContactPicker, setShowContactPicker] = useState(false);

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

  // Open qualify dialog for an unqualified contact
  const handleOpenQualify = useCallback((entry) => {
    setQualifyContact(entry.contact);
    setQualifyDept(entry.department);
    setShowContactPicker(false);
    setQualifyOpen(true);
  }, []);

  // Open qualify dialog with contact picker (Add Stakeholder)
  const handleOpenAddStakeholder = useCallback(() => {
    setQualifyContact(null);
    setQualifyDept(null);
    setShowContactPicker(true);
    setQualifyOpen(true);
  }, []);

  const handleCloseQualify = useCallback(() => {
    setQualifyOpen(false);
    setQualifyContact(null);
    setQualifyDept(null);
  }, []);

  // Submit qualification
  const handleQualify = useCallback(
    async (formPayload) => {
      setQualifyLoading(true);
      const payload = {
        ...formPayload,
        account: accountId,
        source: "MANUAL",
        decision_cycle: cycleId,
      };
      if (qualifyDept?.id && !showContactPicker) {
        payload.target_department = qualifyDept.id;
      }
      const result = await createSignal("people", payload);
      if (result.success) {
        displaySuccessSnackbar("Stakeholder qualified");
        mutatePeople();
        handleCloseQualify();
      } else {
        displayErrorSnackbar(result);
      }
      setQualifyLoading(false);
    },
    [accountId, cycleId, qualifyDept, showContactPicker, mutatePeople, handleCloseQualify],
  );

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
        <Button
          size="small"
          startIcon={<PlusOutlined style={{ fontSize: 12 }} />}
          onClick={handleOpenAddStakeholder}
        >
          Add a stakeholder
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 2 }}
      >
        <Typography variant="subtitle1" fontWeight={600}>
          People Map
        </Typography>
        <Button
          variant="contained"
          size="small"
          startIcon={<PlusOutlined style={{ fontSize: 14 }} />}
          onClick={handleOpenAddStakeholder}
        >
          Add Stakeholder
        </Button>
      </Stack>

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
            Contacts found in cycle activities without a people signal.
          </Typography>
          <Stack spacing={1}>
            {unqualified.map((entry) => (
              <UnqualifiedContactRow
                key={entry.contact?.id || Math.random()}
                entry={entry}
                onQualify={handleOpenQualify}
              />
            ))}
          </Stack>
        </Box>
      )}

      {/* Qualify Dialog */}
      {qualifyOpen && (
        <QualifyDialog
          open={qualifyOpen}
          onClose={handleCloseQualify}
          onSubmit={handleQualify}
          loading={qualifyLoading}
          prefilledContact={qualifyContact}
          accountId={accountId}
          showContactPicker={showContactPicker}
        />
      )}
    </Box>
  );
}

PeopleTab.propTypes = {
  cycleId: PropTypes.string.isRequired,
  accountId: PropTypes.string.isRequired,
};
