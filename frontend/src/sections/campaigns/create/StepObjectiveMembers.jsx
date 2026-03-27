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
import FormControlLabel from "@mui/material/FormControlLabel";
import FormHelperText from "@mui/material/FormHelperText";
import Grid from "@mui/material/Grid";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
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
  CAMPAIGN_TYPES,
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

export default function StepObjectiveMembers({
  data,
  onUpdate,
  errors = {},
  touched = {},
}) {
  const theme = useTheme();
  const { user } = useAuth();

  const isOutbound = data.family === CAMPAIGN_TYPES.OUTBOUND;

  // ==============================|| AUTO-GENERATE NAME ||============================== //

  useEffect(() => {
    // Only auto-generate if name is empty
    if (!data.name) {
      let autoName = "";
      if (isOutbound && data.selectedTerritories?.length > 0) {
        const names = data.selectedTerritories.map((t) => t.name).join(", ");
        autoName = `Outbound — ${names}`;
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
    // Single executor — store id + full object for display
    onUpdate({
      executor_id: newValue?.id || null,
      selectedExecutor: newValue || null,
    });
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
              error={Boolean(touched.name && errors.name)}
              helperText={touched.name && errors.name}
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
                    error: Boolean(touched.start_date && errors.start_date),
                    helperText: touched.start_date && errors.start_date,
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
                    error: Boolean(touched.end_date && errors.end_date),
                    helperText: touched.end_date && errors.end_date,
                  },
                }}
              />
            </LocalizationProvider>
          </Stack>
        </Grid>

        {/* ==================== CHANNEL STRATEGY (Outbound only) ==================== */}
        {isOutbound && (
          <>
            <SectionTitle>Channel Strategy</SectionTitle>
            <Grid item xs={12}>
              <FormControl>
                <RadioGroup
                  row
                  value={data.channel_override || "AUTO"}
                  onChange={(e) =>
                    onUpdate({ channel_override: e.target.value })
                  }
                >
                  <FormControlLabel
                    value="AUTO"
                    control={<Radio size="small" />}
                    label={
                      <Stack spacing={0}>
                        <Typography variant="body2" fontWeight={500}>
                          Auto
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Channel selected per contact data
                        </Typography>
                      </Stack>
                    }
                    sx={{ mr: 4, alignItems: "flex-start" }}
                  />
                  <FormControlLabel
                    value="EMAIL_ONLY"
                    control={<Radio size="small" />}
                    label={
                      <Stack spacing={0}>
                        <Typography variant="body2" fontWeight={500}>
                          Email only
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Force email sequence for all contacts
                        </Typography>
                      </Stack>
                    }
                    sx={{ alignItems: "flex-start" }}
                  />
                </RadioGroup>
              </FormControl>
            </Grid>
          </>
        )}

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
            <InputLabel>Executor (optional)</InputLabel>
            <AsyncUserSelect
              value={data.selectedExecutor || null}
              onChange={handleExecutorChange}
              label=""
              placeholder="Search team members..."
              filters={{ is_active: true }}
            />
            <FormHelperText>
              If not set, you will execute the activities as owner.
            </FormHelperText>
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

StepObjectiveMembers.propTypes = {
  data: PropTypes.object.isRequired,
  onUpdate: PropTypes.func.isRequired,
  errors: PropTypes.object,
  touched: PropTypes.object,
};
