// frontend/src/sections/campaigns/create/StepObjectiveMembers.jsx
/**
 * Campaign Create Wizard
 *
 * Fields:
 * - Name (auto-generated but editable)
 * - Description (optional)
 * - Sequence type (Outbound only)
 * - Start / End dates
 * - Objective: type + target value
 * - Members: owner (auto = current user) + executors
 */

"use client";

import PropTypes from "prop-types";
import { useEffect } from "react";

// material-ui
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import FormControl from "@mui/material/FormControl";
import FormHelperText from "@mui/material/FormHelperText";
import Grid from "@mui/material/Grid";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// date pickers
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";

// project imports
import AsyncUserSelect from "components/AsyncSelection/AsyncUserSelect";
import {
  CAMPAIGN_FAMILIES,
  SEQUENCE_TYPES,
  SEQUENCE_TYPE_LABELS,
  OBJECTIVE_TYPES,
  OBJECTIVE_TYPE_LABELS,
} from "api/campaigns/campaigns";
import { useAuth } from "hooks/useAuth";

// ==============================|| SECTION TITLE ||============================== //

const SectionTitle = ({ children }) => (
  <Grid item xs={12}>
    <Typography
      variant="subtitle2"
      color="text.secondary"
      sx={{
        mt: 2,
        mb: 1,
        textTransform: "uppercase",
        fontSize: "0.75rem",
        fontWeight: 600,
        letterSpacing: "0.5px",
      }}
    >
      {children}
    </Typography>
  </Grid>
);

SectionTitle.propTypes = { children: PropTypes.node };

// ==============================|| STEP OBJECTIVE MEMBERS ||============================== //

export default function StepObjectiveMembers({ data, onUpdate }) {
  const theme = useTheme();
  const { user } = useAuth();

  const isOutbound = data.family === CAMPAIGN_FAMILIES.OUTBOUND;

  // ==============================|| AUTO-GENERATE NAME ||============================== //

  useEffect(() => {
    // Only auto-generate if name is empty
    if (!data.name) {
      let autoName = "";
      if (isOutbound && data.territory_name) {
        autoName = `Outbound — ${data.territory_name}`;
      } else if (!isOutbound && data.selectedAccounts?.length > 0) {
        const count = data.selectedAccounts.length;
        autoName = `Targeted — ${count} account${count > 1 ? "s" : ""}`;
      }
      if (autoName) {
        onUpdate({ name: autoName });
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ==============================|| HANDLERS ||============================== //

  const handleFieldChange = (field) => (event) => {
    onUpdate({ [field]: event.target.value });
  };

  const handleDateChange = (field) => (newValue) => {
    onUpdate({
      [field]: newValue ? dayjs(newValue).format("YYYY-MM-DD") : null,
    });
  };

  const handleExecutorChange = (event, newValue) => {
    // newValue is a single user object from AsyncUserSelect
    if (newValue && !data.member_ids.includes(newValue.id)) {
      onUpdate({
        member_ids: [...data.member_ids, newValue.id],
        selectedExecutors: [...(data.selectedExecutors || []), newValue],
      });
    }
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 1 }}>
        Campaign details
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Configure the campaign name, schedule, objective and team.
      </Typography>

      <Grid container spacing={2.5}>
        {/* ==================== IDENTITY ==================== */}
        <SectionTitle>Identity</SectionTitle>

        <Grid item xs={12}>
          <Stack spacing={1}>
            <InputLabel htmlFor="campaign-name">Campaign Name *</InputLabel>
            <TextField
              fullWidth
              id="campaign-name"
              placeholder="Enter campaign name"
              value={data.name || ""}
              onChange={handleFieldChange("name")}
            />
          </Stack>
        </Grid>

        <Grid item xs={12}>
          <Stack spacing={1}>
            <InputLabel htmlFor="campaign-description">Description</InputLabel>
            <TextField
              fullWidth
              id="campaign-description"
              placeholder="Brief description of the campaign"
              multiline
              rows={2}
              value={data.description || ""}
              onChange={handleFieldChange("description")}
            />
          </Stack>
        </Grid>

        {/* ==================== SEQUENCE TYPE (Prospection only) ==================== */}
        {isOutbound && (
          <Grid item xs={12}>
            <Stack spacing={1}>
              <InputLabel htmlFor="sequence-type">Sequence Type</InputLabel>
              <FormControl fullWidth>
                <Select
                  id="sequence-type"
                  value={data.sequence_type || ""}
                  onChange={handleFieldChange("sequence_type")}
                  displayEmpty
                >
                  <MenuItem value="">
                    <em>Select a sequence type</em>
                  </MenuItem>
                  {Object.entries(SEQUENCE_TYPE_LABELS).map(
                    ([value, label]) => (
                      <MenuItem key={value} value={value}>
                        {label}
                      </MenuItem>
                    ),
                  )}
                </Select>
              </FormControl>
              <FormHelperText>
                Defines the automated activity sequence generated for each
                account.
              </FormHelperText>
            </Stack>
          </Grid>
        )}

        {/* ==================== SCHEDULE ==================== */}
        <SectionTitle>Schedule</SectionTitle>

        <Grid item xs={12} sm={6}>
          <Stack spacing={1}>
            <InputLabel>Start Date</InputLabel>
            <LocalizationProvider dateAdapter={AdapterDayjs}>
              <DatePicker
                value={data.start_date ? dayjs(data.start_date) : null}
                onChange={handleDateChange("start_date")}
                slotProps={{
                  textField: {
                    fullWidth: true,
                    placeholder: "Select start date",
                  },
                }}
              />
            </LocalizationProvider>
          </Stack>
        </Grid>

        <Grid item xs={12} sm={6}>
          <Stack spacing={1}>
            <InputLabel>End Date</InputLabel>
            <LocalizationProvider dateAdapter={AdapterDayjs}>
              <DatePicker
                value={data.end_date ? dayjs(data.end_date) : null}
                onChange={handleDateChange("end_date")}
                minDate={data.start_date ? dayjs(data.start_date) : undefined}
                slotProps={{
                  textField: {
                    fullWidth: true,
                    placeholder: "Select end date",
                  },
                }}
              />
            </LocalizationProvider>
          </Stack>
        </Grid>

        {/* ==================== OBJECTIVE ==================== */}
        <SectionTitle>Objective</SectionTitle>

        <Grid item xs={12} sm={6}>
          <Stack spacing={1}>
            <InputLabel htmlFor="objective-type">Objective Type</InputLabel>
            <FormControl fullWidth>
              <Select
                id="objective-type"
                value={data.objective_type || ""}
                onChange={handleFieldChange("objective_type")}
                displayEmpty
              >
                <MenuItem value="">
                  <em>Select an objective</em>
                </MenuItem>
                {Object.entries(OBJECTIVE_TYPE_LABELS).map(([value, label]) => (
                  <MenuItem key={value} value={value}>
                    {label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
        </Grid>

        <Grid item xs={12} sm={6}>
          <Stack spacing={1}>
            <InputLabel htmlFor="objective-target">Target Value</InputLabel>
            <TextField
              fullWidth
              id="objective-target"
              type="number"
              placeholder="e.g. 20"
              value={data.objective_target || ""}
              onChange={handleFieldChange("objective_target")}
              inputProps={{ min: 0 }}
              disabled={!data.objective_type}
            />
          </Stack>
        </Grid>

        {/* ==================== TEAM ==================== */}
        <SectionTitle>Team</SectionTitle>

        <Grid item xs={12} sm={6}>
          <Stack spacing={1}>
            <InputLabel>Owner</InputLabel>
            <TextField
              fullWidth
              value={
                user
                  ? `${user.first_name || ""} ${user.last_name || ""}`.trim() ||
                    user.email
                  : "Current user"
              }
              disabled
              InputProps={{
                readOnly: true,
                sx: { bgcolor: "action.hover" },
              }}
            />
            <FormHelperText>
              You are automatically set as the campaign owner.
            </FormHelperText>
          </Stack>
        </Grid>

        <Grid item xs={12} sm={6}>
          <Stack spacing={1}>
            <InputLabel>Add Executors</InputLabel>
            <AsyncUserSelect
              value={null}
              onChange={handleExecutorChange}
              label=""
              placeholder="Search team members..."
            />
            {(data.selectedExecutors || []).length > 0 && (
              <Typography variant="caption" color="text.secondary">
                {data.selectedExecutors.length} executor
                {data.selectedExecutors.length > 1 ? "s" : ""} added
              </Typography>
            )}
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

StepObjectiveMembers.propTypes = {
  /** Full wizard data object */
  data: PropTypes.object.isRequired,
  /** Callback to update wizard data: (updates) => void */
  onUpdate: PropTypes.func.isRequired,
};
