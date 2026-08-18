// frontend/src/components/cards/signals/PainCard.jsx
/**
 * PainCard — display card for a single PainSignal with its nested impacts.
 *
 * Used by SignalList when signalType === 'pain', in place of the generic
 * SignalCard (which is kept for People / Objective / TechStack).
 *
 * Responsibilities:
 *   - Render Pain header (type chip, status chip, creation date, actions)
 *   - Render Pain body (canonical chip, summary, source provenance line)
 *   - Render nested impacts list with add / edit / delete controls
 *   - Surface lifecycle actions (validate, reject) same as SignalCard
 *   - Confirm destructive actions (delete pain, delete impact)
 *
 * Contract — the parent (AccountSignalsTab / ActivitySignalsTab) owns:
 *   - SignalEditDialog opening for Pain edit (reuses existing flow)
 *   - AddPainImpactDialog opening for impact create / edit
 *   - API calls for validate / reject / delete pain + CRUD impacts
 *
 * PainCard only emits callbacks; it never calls the API directly.
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
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import CloseCircleOutlined from "@ant-design/icons/CloseCircleOutlined";
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import EditOutlined from "@ant-design/icons/EditOutlined";
import MoreOutlined from "@ant-design/icons/MoreOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";

// project imports
import { resolveImpactLevel } from "sections/accounts/signals/signalClusters";

// ==============================|| STATUS CONFIG ||============================== //

const STATUS_CONFIG = {
  PENDING: { color: "warning", label: "Pending" },
  VALIDATED: { color: "success", label: "Validated" },
  REJECTED: { color: "error", label: "Rejected" },
};

// ==============================|| HELPERS ||============================== //

function formatContact(contact) {
  if (!contact) return null;
  const name = `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  return name || null;
}

/**
 * Truncate a string to max length, append ellipsis if needed.
 */
function truncate(str, max = 80) {
  if (!str) return null;
  return str.length > max ? `${str.slice(0, max)}…` : str;
}

/**
 * Resolve a choices-array label by value.
 */
function resolveLabel(options, value) {
  if (!value || !options) return null;
  return options.find((o) => o.value === value)?.label ?? value;
}

/**
 * Format an impact into a single readable line.
 *
 * BUSINESS   → "120k$/year lost productivity"
 * DEPARTMENT → "Sales · 15h/week lost"
 * PERSONAL   → "Marie Durand (OVERLOAD) · 3h/week overtime"
 *
 * Missing optional parts are skipped silently — no "N/A" filler.
 */
function formatImpactLine(impact, choices) {
  if (!impact) return "";

  const parts = [];

  // Scope
  if (impact.level === "DEPARTMENT") {
    const deptName = impact.impacted_department?.name;
    if (deptName) parts.push(deptName);
  } else if (impact.level === "PERSONAL") {
    const contactName = formatContact(impact.impacted_contact);
    const humanLabel = resolveLabel(
      choices?.human_impacts,
      impact.human_impact,
    );
    if (contactName && humanLabel) {
      parts.push(`${contactName} (${humanLabel})`);
    } else if (contactName) {
      parts.push(contactName);
    }
  }
  // BUSINESS has no scope detail — the level chip says it all.

  // Metric — truncated for list view
  if (impact.metric) {
    parts.push(truncate(impact.metric, 60));
  }

  const line = parts.join(" · ");
  return line || "(no details)";
}

// ==============================|| IMPACT ROW ||============================== //

/**
 * Single impact line: colored bullet · level chip · free-text · actions.
 *
 * Click-to-edit is deliberately NOT wired on the row body — the rep uses
 * the edit icon. This avoids accidental triggers when reading dense lists.
 */
function ImpactRow({ impact, choices, onEdit, onDelete }) {
  const levelCfg = resolveImpactLevel(impact.level);

  const line = formatImpactLine(impact, choices);

  return (
    <Stack
      direction="row"
      spacing={1}
      alignItems="center"
      sx={{
        py: 0.5,
        px: 0.5,
        borderRadius: 0.75,
        "&:hover": {
          bgcolor: "action.hover",
          "& .impact-actions": { opacity: 1 },
        },
      }}
    >
      {/* Colored bullet — visual anchor for scope */}
      <Box
        sx={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          bgcolor: `${levelCfg.color}.main`,
          flexShrink: 0,
        }}
      />

      {/* Level chip */}
      <Chip
        label={levelCfg.label}
        size="small"
        color={levelCfg.color}
        variant="outlined"
        sx={{ fontSize: "0.65rem", height: 18, flexShrink: 0 }}
      />

      {/* Content line — truncates on narrow widths */}
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{
          flex: 1,
          minWidth: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
        title={line}
      >
        {line}
      </Typography>

      {/* Actions — fade in on hover to keep list calm */}
      <Stack
        className="impact-actions"
        direction="row"
        spacing={0.25}
        sx={{
          opacity: { xs: 1, sm: 0 },
          transition: "opacity 0.15s",
          flexShrink: 0,
        }}
      >
        <Tooltip title="Edit impact">
          <IconButton
            size="small"
            onClick={() => onEdit(impact)}
            aria-label="Edit impact"
            sx={{
              color: "text.disabled",
              "&:hover": { color: "primary.main" },
            }}
          >
            <EditOutlined style={{ fontSize: 12 }} />
          </IconButton>
        </Tooltip>
        <Tooltip title="Delete impact">
          <IconButton
            size="small"
            onClick={() => onDelete(impact)}
            aria-label="Delete impact"
            sx={{ color: "text.disabled", "&:hover": { color: "error.main" } }}
          >
            <DeleteOutlined style={{ fontSize: 12 }} />
          </IconButton>
        </Tooltip>
      </Stack>
    </Stack>
  );
}

ImpactRow.propTypes = {
  impact: PropTypes.shape({
    id: PropTypes.string.isRequired,
    level: PropTypes.string,
    metric: PropTypes.string,
    human_impact: PropTypes.string,
    impacted_department: PropTypes.object,
    impacted_contact: PropTypes.object,
  }).isRequired,
  choices: PropTypes.object,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
};

// ==============================|| CONFIRM DIALOG ||============================== //

/**
 * Minimal inline confirm dialog — one pattern reused for Pain delete
 * and Impact delete to avoid spinning up two nearly-identical components.
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

// ==============================|| PAIN CARD ||============================== //

/**
 * PainCard
 *
 * @param {Object}   pain             - PainSignal with nested .impacts[]
 * @param {Object}   choices          - From useGetSignalChoices()
 * @param {Function} onValidate       - (pain, 'pain') => void
 * @param {Function} onReject         - (pain, 'pain') => void
 * @param {Function} onEdit           - (pain, 'pain') => void — opens SignalEditDialog
 * @param {Function} onDelete         - (pain, 'pain') => void — parent handles API + cascade
 * @param {Function} onAddImpact      - (painId) => void — opens AddPainImpactDialog in create mode
 * @param {Function} onEditImpact     - (impact) => void — opens AddPainImpactDialog in edit mode
 * @param {Function} onDeleteImpact   - (impact) => void — parent handles API
 */
export default function PainCard({
  pain,
  choices,
  onValidate,
  onReject,
  onEdit,
  onDelete,
  onAddImpact,
  onEditImpact,
  onDeleteImpact,
}) {
  // ==============================|| LOCAL STATE ||============================== //

  const [menuAnchor, setMenuAnchor] = useState(null);
  const [confirmDeletePainOpen, setConfirmDeletePainOpen] = useState(false);
  const [confirmDeleteImpact, setConfirmDeleteImpact] = useState(null);

  // ==============================|| DERIVED ||============================== //

  const status = pain.status ?? "PENDING";
  const statusCfg = STATUS_CONFIG[status] ?? {
    color: "default",
    label: status,
  };

  const isPending = status === "PENDING";

  const createdDate = pain.created_at
    ? new Date(pain.created_at).toLocaleDateString(undefined, {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : null;

  /** Canonical axes chip text — "Operations × Time" */
  // choices.signal_whats / signal_dimensions expose the shared
  // canonical-axis enums. Pain's `what` and `dimension`
  // model fields are unchanged — only the source of display labels
  // differs. Same applies when a Pain is rendered inside a cluster.
  const canonicalText = useMemo(() => {
    const whatLabel = resolveLabel(choices?.signal_whats, pain.what);
    const dimensionLabel = resolveLabel(
      choices?.signal_dimensions,
      pain.dimension,
    );
    if (!whatLabel || !dimensionLabel) return null;
    return `${whatLabel} × ${dimensionLabel}`;
  }, [choices, pain.what, pain.dimension]);

  /** Source line */
  const sourceLine = useMemo(() => {
    const contactName = formatContact(pain.source_contact);
    const activity = pain.source_activity;
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
      return `Reported by ${contactName} · ${dateStr}`;
    }
    if (contactName) return `Reported by ${contactName}`;
    if (dateStr) return dateStr;
    return null;
  }, [pain.source_contact, pain.source_activity]);

  /**
   * Cross-reference — TechStack
   *
   * Two independent fields on the backend; the UI prefers the structured
   * FK and falls back to the textual mention. Both can co-exist in a
   * progressive-enrichment scenario; we still show only one chip in
   * that case (FK wins) to avoid visual redundancy.
   *
   * Returns null when neither field is set so the section is suppressed
   * entirely rather than rendered with a placeholder.
   */
  const relatedTech = useMemo(
    () => pain.related_techstack_mention?.trim() || null,
    [pain.related_techstack_mention],
  );

  /** Nested impacts — always an array, default empty */
  const impacts = useMemo(
    () => (Array.isArray(pain.impacts) ? pain.impacts : []),
    [pain.impacts],
  );

  // ==============================|| MENU HANDLERS ||============================== //

  const handleMenuOpen = useCallback((e) => {
    e.stopPropagation();
    setMenuAnchor(e.currentTarget);
  }, []);

  const handleMenuClose = useCallback(() => setMenuAnchor(null), []);

  const handleEditPain = useCallback(() => {
    handleMenuClose();
    onEdit(pain, "pain");
  }, [handleMenuClose, onEdit, pain]);

  const handleDeletePainRequest = useCallback(() => {
    handleMenuClose();
    setConfirmDeletePainOpen(true);
  }, [handleMenuClose]);

  const handleDeletePainConfirm = useCallback(() => {
    setConfirmDeletePainOpen(false);
    onDelete(pain, "pain");
  }, [onDelete, pain]);

  const handleValidate = useCallback(() => {
    onValidate(pain, "pain");
  }, [onValidate, pain]);

  const handleReject = useCallback(() => {
    onReject(pain, "pain");
  }, [onReject, pain]);

  // ==============================|| IMPACT HANDLERS ||============================== //

  const handleAddImpact = useCallback(() => {
    onAddImpact(pain.id);
  }, [onAddImpact, pain.id]);

  const handleEditImpact = useCallback(
    (impact) => {
      onEditImpact(impact);
    },
    [onEditImpact],
  );

  const handleDeleteImpactRequest = useCallback((impact) => {
    setConfirmDeleteImpact(impact);
  }, []);

  const handleDeleteImpactConfirm = useCallback(() => {
    if (confirmDeleteImpact) {
      onDeleteImpact(confirmDeleteImpact);
    }
    setConfirmDeleteImpact(null);
  }, [confirmDeleteImpact, onDeleteImpact]);

  const handleDeleteImpactCancel = useCallback(() => {
    setConfirmDeleteImpact(null);
  }, []);

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
        {/* Left: type chip + status chip + canonical + date */}
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ flex: 1, minWidth: 0 }}
        >
          <Chip
            label="Pain"
            color="error"
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
              color="error"
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
            <Tooltip title="Validate pain">
              <IconButton
                size="small"
                color="success"
                onClick={handleValidate}
                aria-label="Validate pain"
              >
                <CheckCircleOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}

          {isPending && (
            <Tooltip title="Reject pain">
              <IconButton
                size="small"
                color="error"
                onClick={handleReject}
                aria-label="Reject pain"
              >
                <CloseCircleOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}

          <IconButton
            size="small"
            onClick={handleMenuOpen}
            aria-label="Pain actions"
            aria-controls={menuAnchor ? "pain-action-menu" : undefined}
            aria-haspopup="true"
            aria-expanded={Boolean(menuAnchor)}
          >
            <MoreOutlined style={{ fontSize: 16 }} />
          </IconButton>

          <Menu
            id="pain-action-menu"
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={handleMenuClose}
            anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
            transformOrigin={{ vertical: "top", horizontal: "right" }}
          >
            {status !== "REJECTED" && (
              <MenuItem onClick={handleEditPain} dense>
                <Stack direction="row" spacing={1} alignItems="center">
                  <EditOutlined style={{ fontSize: 14 }} />
                  <span>Edit pain</span>
                </Stack>
              </MenuItem>
            )}
            <MenuItem
              onClick={handleDeletePainRequest}
              dense
              sx={{ color: "error.main" }}
            >
              <Stack direction="row" spacing={1} alignItems="center">
                <DeleteOutlined style={{ fontSize: 14 }} />
                <span>Delete pain</span>
              </Stack>
            </MenuItem>
          </Menu>
        </Stack>
      </Stack>

      {/* ==================== BODY: Summary ==================== */}
      {pain.summary && (
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
          {pain.summary}
        </Typography>
      )}

      {/* ==================== RELATED TOOL  ==================== */}
      {/*
        Optional free-text cross-reference (related_techstack_mention).
        S10 removed the structured `related_techstack` FK along with the
        tech catalogue, so there is one representation left and one chip
        style to render it.

        Visible regardless of `pain.what` — the model is permissive
        (a non-TECH pain may legitimately reference a tool); the
        InlinePainForm UI only restricts the capture surface.
      */}
      {relatedTech && (
        <Stack
          direction="row"
          spacing={0.5}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ mt: 1 }}
        >
          <Typography variant="caption" color="text.disabled">
            Related tool:
          </Typography>
          <Chip
            label={relatedTech}
            size="small"
            variant="outlined"
            sx={{
              fontSize: "0.65rem",
              height: 20,
              fontStyle: "italic",
              color: "text.secondary",
            }}
          />
        </Stack>
      )}

      {/* ==================== SOURCE LINE ==================== */}
      {sourceLine && (
        <Typography
          variant="caption"
          color="text.disabled"
          display="block"
          sx={{ mt: 0.75 }}
        >
          {sourceLine}
        </Typography>
      )}

      {/* ==================== IMPACTS SECTION ==================== */}
      <Divider sx={{ mt: 1.75, mb: 1.25 }} />

      {/* Impacts header — always shows the "+ Add Impact" button */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 0.5 }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="caption" color="text.secondary" fontWeight={600}>
            Impacts
          </Typography>
          {impacts.length > 0 && (
            <Chip
              label={impacts.length}
              size="small"
              variant="outlined"
              sx={{ height: 16, fontSize: "0.62rem" }}
            />
          )}
        </Stack>

        <Button
          size="small"
          variant="text"
          color="primary"
          startIcon={<PlusOutlined style={{ fontSize: 11 }} />}
          onClick={handleAddImpact}
          sx={{ fontSize: "0.7rem", py: 0.25, minWidth: 0 }}
        >
          Add Impact
        </Button>
      </Stack>

      {/* Impacts list or empty state */}
      {impacts.length === 0 ? (
        <Typography
          variant="caption"
          color="text.disabled"
          sx={{ display: "block", fontStyle: "italic", py: 0.5 }}
        >
          No impacts yet — start adding evidence to make this pain attackable.
        </Typography>
      ) : (
        <Stack spacing={0.25}>
          {impacts.map((impact) => (
            <ImpactRow
              key={impact.id}
              impact={impact}
              choices={choices}
              onEdit={handleEditImpact}
              onDelete={handleDeleteImpactRequest}
            />
          ))}
        </Stack>
      )}

      {/* ==================== CONFIRM: Delete Pain ==================== */}
      <ConfirmDialog
        open={confirmDeletePainOpen}
        title="Delete this pain?"
        message={
          impacts.length > 0
            ? `This pain has ${impacts.length} impact${
                impacts.length === 1 ? "" : "s"
              }. Deleting the pain will also delete all its impacts permanently.`
            : "This pain will be deleted permanently."
        }
        confirmLabel="Delete pain"
        onConfirm={handleDeletePainConfirm}
        onClose={() => setConfirmDeletePainOpen(false)}
      />

      {/* ==================== CONFIRM: Delete Impact ==================== */}
      <ConfirmDialog
        open={Boolean(confirmDeleteImpact)}
        title="Delete this impact?"
        message="This impact will be deleted permanently. The parent pain will remain."
        confirmLabel="Delete impact"
        onConfirm={handleDeleteImpactConfirm}
        onClose={handleDeleteImpactCancel}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

PainCard.propTypes = {
  pain: PropTypes.shape({
    id: PropTypes.string.isRequired,
    status: PropTypes.string,
    what: PropTypes.string,
    dimension: PropTypes.string,
    summary: PropTypes.string,
    source_contact: PropTypes.object,
    source_activity: PropTypes.object,
    created_at: PropTypes.string,
    /** Nested impacts from PainSignalListSerializer / DetailSerializer */
    impacts: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.string.isRequired,
        level: PropTypes.string,
        metric: PropTypes.string,
        human_impact: PropTypes.string,
        impacted_department: PropTypes.object,
        impacted_contact: PropTypes.object,
      }),
    ),
    /** Optional free-text tool cross-reference. */
    related_techstack_mention: PropTypes.string,
  }).isRequired,
  choices: PropTypes.object,

  /** Lifecycle actions — signature matches SignalCard for AccountSignalsTab compatibility */
  onValidate: PropTypes.func.isRequired,
  onReject: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,

  /** Impact actions — specific to Pain */
  onAddImpact: PropTypes.func.isRequired,
  onEditImpact: PropTypes.func.isRequired,
  onDeleteImpact: PropTypes.func.isRequired,
};
