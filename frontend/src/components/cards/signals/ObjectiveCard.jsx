// frontend/src/components/cards/signals/ObjectiveCard.jsx
/**
 * ObjectiveCard — display card for a single ObjectiveSignal.
 *
 * Used by SignalList when signalType === 'objective', in place of the
 * generic SignalCard (which is kept for People / TechStack).
 *
 * Responsibilities:
 *   - Render Objective header (type chip, status chip, canonical axes,
 *     scope chip, creation date, actions)
 *   - Render Objective body (summary, target date if present, success
 *     criteria if present, source provenance line)
 *   - Surface lifecycle actions (validate, reject, edit, delete) aligned
 *     with PainCard / SignalCard conventions
 *   - Confirm destructive delete via inline dialog
 *
 * Contract — the parent (AccountSignalsTab / ActivitySignalsTab) owns:
 *   - SignalEditDialog opening for Objective edit
 *   - API calls for validate / reject / delete
 *
 * ObjectiveCard only emits callbacks; it never calls the API directly.
 *
 * Design notes:
 *   - Uses `info` color palette (blue) as the Objective visual identity,
 *     distinct from Pain's `error` (red).
 *   - No nested list of children — unlike PainCard which renders
 *     PainImpacts, Objective has no sub-resource.
 *   - target_date is formatted with an "urgency" chip when within
 *     90 days — mirrors the backend `has_target_date_soon` signal.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// ant-design icons
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import CloseCircleOutlined from "@ant-design/icons/CloseCircleOutlined";
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import EditOutlined from "@ant-design/icons/EditOutlined";
import MoreOutlined from "@ant-design/icons/MoreOutlined";

// ==============================|| STATUS CONFIG ||============================== //

const STATUS_CONFIG = {
  PENDING: { color: "warning", label: "Pending" },
  VALIDATED: { color: "success", label: "Validated" },
  REJECTED: { color: "error", label: "Rejected" },
};

// ==============================|| SCOPE LEVEL CONFIG ||============================== //

/**
 * Visual tag per ScopeLevel — drives chip color.
 *
 * Colors chosen to match the Pain module's impact level palette
 * (BUSINESS → warning, DEPARTMENT → info, PERSONAL → error) so the
 * scope concept reads the same way across signal types.
 */
const SCOPE_LEVEL_CONFIG = {
  BUSINESS: { color: "warning", label: "Business" },
  DEPARTMENT: { color: "info", label: "Department" },
  PERSONAL: { color: "error", label: "Personal" },
};

// ==============================|| TARGET DATE URGENCY ||============================== //

/** Days threshold — matches backend OBJECTIVE_TARGET_DATE_SOON_DAYS */
const TARGET_DATE_SOON_DAYS = 90;

/**
 * Classify a target_date into an urgency bucket.
 *
 * Returns { label, color, tone } where tone is a descriptive word used
 * in the tooltip.
 */
function classifyTargetDate(isoDate) {
  if (!isoDate) return null;

  const target = new Date(isoDate);
  if (Number.isNaN(target.getTime())) return null;

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  target.setHours(0, 0, 0, 0);

  const diffDays = Math.round(
    (target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24),
  );

  if (diffDays < 0) {
    return { label: "Overdue", color: "error", tone: "overdue" };
  }
  if (diffDays === 0) {
    return { label: "Due today", color: "error", tone: "today" };
  }
  if (diffDays <= TARGET_DATE_SOON_DAYS) {
    return {
      label: `In ${diffDays}d`,
      color: "warning",
      tone: `due in ${diffDays} day${diffDays === 1 ? "" : "s"}`,
    };
  }
  return {
    label: `In ${diffDays}d`,
    color: "default",
    tone: `due in ${diffDays} days`,
  };
}

// ==============================|| HELPERS ||============================== //

function formatContact(contact) {
  if (!contact) return null;
  const name = `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  return name || null;
}

function formatShortDate(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return null;
  }
}

function resolveLabel(options, value) {
  if (!value || !options) return null;
  return options.find((o) => o.value === value)?.label ?? value;
}

function truncate(str, max = 120) {
  if (!str) return null;
  return str.length > max ? `${str.slice(0, max)}…` : str;
}

// ==============================|| CONFIRM DIALOG ||============================== //

/**
 * Minimal inline confirm dialog for destructive actions.
 * Same shape as the one in PainCard — kept local to avoid cross-file
 * coupling while the component library stabilises.
 */
function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  onConfirm,
  onClose,
}) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary">
          {message}
        </Typography>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} color="inherit" size="small">
          Cancel
        </Button>
        <Button
          onClick={onConfirm}
          color="error"
          variant="contained"
          size="small"
        >
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

ConfirmDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  title: PropTypes.string.isRequired,
  message: PropTypes.string.isRequired,
  confirmLabel: PropTypes.string.isRequired,
  onConfirm: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
};

// ==============================|| OBJECTIVE CARD ||============================== //

/**
 * ObjectiveCard
 *
 * @param {Object}   objective   - ObjectiveSignal read payload
 * @param {Object}   choices     - From useGetSignalChoices()
 * @param {Function} onValidate  - (objective, 'objective') => void
 * @param {Function} onReject    - (objective, 'objective') => void
 * @param {Function} onEdit      - (objective, 'objective') => void — opens SignalEditDialog
 * @param {Function} onDelete    - (objective, 'objective') => void — parent handles API
 */
export default function ObjectiveCard({
  objective,
  choices,
  onValidate,
  onReject,
  onEdit,
  onDelete,
}) {
  // ==============================|| LOCAL STATE ||============================== //

  const [menuAnchor, setMenuAnchor] = useState(null);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  // ==============================|| DERIVED ||============================== //

  const status = objective.status ?? "PENDING";
  const statusCfg = STATUS_CONFIG[status] ?? {
    color: "default",
    label: status,
  };

  const isPending = status === "PENDING";

  const createdDate = formatShortDate(objective.created_at);

  /** Canonical axes chip text — "Growth / Revenue × Cost / Budget" */
  const canonicalText = useMemo(() => {
    const whatLabel = resolveLabel(choices?.signal_whats, objective.what);
    const dimensionLabel = resolveLabel(
      choices?.signal_dimensions,
      objective.dimension,
    );
    if (!whatLabel || !dimensionLabel) return null;
    return `${whatLabel} × ${dimensionLabel}`;
  }, [choices, objective.what, objective.dimension]);

  /** Scope chip config */
  const scopeCfg = useMemo(() => {
    const cfg = SCOPE_LEVEL_CONFIG[objective.scope_level];
    if (!cfg) return null;
    return cfg;
  }, [objective.scope_level]);

  /** Target-date classification (null, overdue, soon, later) */
  const targetDateClass = useMemo(
    () => classifyTargetDate(objective.target_date),
    [objective.target_date],
  );

  /** Target-date human label — "2026-06-30" */
  const targetDateLabel = useMemo(
    () => formatShortDate(objective.target_date),
    [objective.target_date],
  );

  /**
   * Target line — "Owned by Marie Durand" (PERSONAL) or
   * "Department: Sales" (DEPARTMENT). BUSINESS has no owner line.
   */
  const ownerLine = useMemo(() => {
    if (objective.scope_level === "PERSONAL") {
      const name = formatContact(objective.target_contact);
      return name ? `Owned by ${name}` : null;
    }
    if (objective.scope_level === "DEPARTMENT") {
      const deptName = objective.target_department?.name;
      return deptName ? `Department: ${deptName}` : null;
    }
    return null;
  }, [
    objective.scope_level,
    objective.target_contact,
    objective.target_department,
  ]);

  /** Source line — "Set by Nicky Larson · 2026-04-15" */
  const sourceLine = useMemo(() => {
    const contactName = formatContact(objective.source_contact);
    const activity = objective.source_activity;
    const rawDate = activity?.scheduled_date || activity?.completed_at;
    let dateStr = "";
    if (rawDate) {
      try {
        dateStr = new Date(rawDate).toISOString().slice(0, 10);
      } catch {
        dateStr = String(rawDate).slice(0, 10);
      }
    }

    if (contactName && dateStr) {
      return `Set by ${contactName} · ${dateStr}`;
    }
    if (contactName) return `Set by ${contactName}`;
    if (dateStr) return dateStr;
    return null;
  }, [objective.source_contact, objective.source_activity]);

  // ==============================|| MENU HANDLERS ||============================== //

  const handleMenuOpen = useCallback((e) => {
    e.stopPropagation();
    setMenuAnchor(e.currentTarget);
  }, []);

  const handleMenuClose = useCallback(() => setMenuAnchor(null), []);

  const handleEdit = useCallback(() => {
    handleMenuClose();
    onEdit(objective, "objective");
  }, [handleMenuClose, onEdit, objective]);

  const handleDeleteRequest = useCallback(() => {
    handleMenuClose();
    setConfirmDeleteOpen(true);
  }, [handleMenuClose]);

  const handleDeleteConfirm = useCallback(() => {
    setConfirmDeleteOpen(false);
    onDelete(objective, "objective");
  }, [onDelete, objective]);

  const handleValidate = useCallback(() => {
    onValidate(objective, "objective");
  }, [onValidate, objective]);

  const handleReject = useCallback(() => {
    onReject(objective, "objective");
  }, [onReject, objective]);

  // ==============================|| RENDER ||============================== //

  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: isPending ? "warning.light" : "divider",
        borderRadius: 1.5,
        p: 2,
        bgcolor: "background.paper",
        transition: "border-color 0.15s",
        "&:hover": { borderColor: "primary.light" },
      }}
    >
      {/* ==================== HEADER ==================== */}
      <Stack direction="row" spacing={1} alignItems="flex-start">
        {/* Left: type chip + status chip + canonical + scope + date */}
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ flex: 1, minWidth: 0 }}
        >
          <Chip
            label="Objective"
            color="info"
            size="small"
            variant="outlined"
            sx={{ fontSize: "0.68rem", height: 20 }}
          />
          <Chip
            label={statusCfg.label}
            color={statusCfg.color}
            size="small"
            sx={{ fontSize: "0.68rem", height: 20 }}
          />
          {canonicalText && (
            <Chip
              label={canonicalText}
              size="small"
              color="info"
              variant="outlined"
              sx={{ fontSize: "0.68rem", height: 20 }}
            />
          )}
          {scopeCfg && (
            <Chip
              label={scopeCfg.label}
              size="small"
              color={scopeCfg.color}
              variant="outlined"
              sx={{ fontSize: "0.68rem", height: 20 }}
            />
          )}
          {createdDate && (
            <Typography variant="caption" color="text.disabled">
              {createdDate}
            </Typography>
          )}
        </Stack>

        {/* Right: quick actions + overflow menu */}
        <Stack direction="row" spacing={0.5} alignItems="center" flexShrink={0}>
          {isPending && (
            <Tooltip title="Validate objective">
              <IconButton
                size="small"
                color="success"
                onClick={handleValidate}
                aria-label="Validate objective"
              >
                <CheckCircleOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}

          {isPending && (
            <Tooltip title="Reject objective">
              <IconButton
                size="small"
                color="error"
                onClick={handleReject}
                aria-label="Reject objective"
              >
                <CloseCircleOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}

          <IconButton
            size="small"
            onClick={handleMenuOpen}
            aria-label="Objective actions"
            aria-controls={menuAnchor ? "objective-action-menu" : undefined}
            aria-haspopup="true"
            aria-expanded={Boolean(menuAnchor)}
          >
            <MoreOutlined style={{ fontSize: 16 }} />
          </IconButton>

          <Menu
            id="objective-action-menu"
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={handleMenuClose}
            anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
            transformOrigin={{ vertical: "top", horizontal: "right" }}
          >
            {status !== "REJECTED" && (
              <MenuItem onClick={handleEdit} dense>
                <Stack direction="row" spacing={1} alignItems="center">
                  <EditOutlined style={{ fontSize: 14 }} />
                  <span>Edit objective</span>
                </Stack>
              </MenuItem>
            )}
            <MenuItem
              onClick={handleDeleteRequest}
              dense
              sx={{ color: "error.main" }}
            >
              <Stack direction="row" spacing={1} alignItems="center">
                <DeleteOutlined style={{ fontSize: 14 }} />
                <span>Delete objective</span>
              </Stack>
            </MenuItem>
          </Menu>
        </Stack>
      </Stack>

      {/* ==================== BODY: Summary ==================== */}
      {objective.summary && (
        <Typography
          variant="body2"
          fontWeight={600}
          sx={{
            mt: 1.25,
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {objective.summary}
        </Typography>
      )}

      {/* ==================== TARGET DATE ==================== */}
      {targetDateLabel && (
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          sx={{ mt: 1.25 }}
          flexWrap="wrap"
          useFlexGap
        >
          <Tooltip title={targetDateClass?.tone ?? "target date"}>
            <Stack direction="row" spacing={0.5} alignItems="center">
              <CalendarOutlined style={{ fontSize: 13, color: "#8c8c8c" }} />
              <Typography variant="caption" color="text.secondary">
                Target: {targetDateLabel}
              </Typography>
            </Stack>
          </Tooltip>
          {targetDateClass && targetDateClass.color !== "default" && (
            <Chip
              label={targetDateClass.label}
              size="small"
              color={targetDateClass.color}
              variant="outlined"
              sx={{ fontSize: "0.62rem", height: 18 }}
            />
          )}
        </Stack>
      )}

      {/* ==================== SUCCESS CRITERIA ==================== */}
      {objective.success_criteria && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{
            display: "block",
            mt: 1,
            fontStyle: "italic",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
          title={objective.success_criteria}
        >
          ✓ {truncate(objective.success_criteria, 140)}
        </Typography>
      )}

      {/* ==================== OWNER LINE ==================== */}
      {ownerLine && (
        <Typography
          variant="caption"
          color="text.secondary"
          display="block"
          sx={{ mt: 0.75, fontWeight: 500 }}
        >
          {ownerLine}
        </Typography>
      )}

      {/* ==================== SOURCE LINE ==================== */}
      {sourceLine && (
        <>
          <Divider sx={{ mt: 1.5, mb: 1 }} />
          <Typography variant="caption" color="text.disabled">
            {sourceLine}
          </Typography>
        </>
      )}

      {/* ==================== CONFIRM: Delete Objective ==================== */}
      <ConfirmDialog
        open={confirmDeleteOpen}
        title="Delete this objective?"
        message="This objective will be deleted permanently."
        confirmLabel="Delete objective"
        onConfirm={handleDeleteConfirm}
        onClose={() => setConfirmDeleteOpen(false)}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

ObjectiveCard.propTypes = {
  objective: PropTypes.shape({
    id: PropTypes.string.isRequired,
    status: PropTypes.string,
    // Canonical axes
    what: PropTypes.string,
    dimension: PropTypes.string,
    // Scope
    scope_level: PropTypes.oneOf(["BUSINESS", "DEPARTMENT", "PERSONAL"]),
    // Descriptive
    summary: PropTypes.string,
    success_criteria: PropTypes.string,
    target_date: PropTypes.string, // ISO yyyy-mm-dd
    notes: PropTypes.string,
    // Target (conditional)
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
    // Source
    source_contact: PropTypes.object,
    source_activity: PropTypes.object,
    // Audit
    created_at: PropTypes.string,
  }).isRequired,
  choices: PropTypes.object,

  /** Lifecycle actions — signature matches SignalCard / PainCard */
  onValidate: PropTypes.func.isRequired,
  onReject: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
};
