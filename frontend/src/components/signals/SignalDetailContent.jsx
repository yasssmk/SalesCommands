// frontend/src/components/signals/SignalDetailContent.jsx
//
// The single-signal detail CONTENT — header row (leading/trailing action slots
// + type/status chips), body (summary, validated-by, per-type detail block via
// the shared B1.2 blocks, source quote, origin provenance) and the lifecycle
// actions (validate / reject / edit / reopen).
//
// This is the drawer body extracted from SignalQuickDrawer so it can be reused
// as the "replacement" content inside another themed MUI Drawer shell (the
// cluster drawer's signal view) WITHOUT stacking a second drawer. Both
// SignalQuickDrawer and SignalClusterDetailDrawer render this same content.

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  LinkOutlined,
  ReloadOutlined,
} from "@ant-design/icons";

// Project imports
import SignalTypeChip from "components/chips/SignalTypeChip";
import SignalStatusChip from "components/chips/SignalStatusChip";
import StatusPill from "components/chips/StatusPill";
import { getSignalTypeLabel } from "utils/signalTypes";
import DrawerFieldRow from "components/display/DrawerFieldRow";
import DrawerSection from "components/display/DrawerSection";
import { getMissingFields } from "sections/activities/signals/signalValidationRules";
import SignalIncompleteAlert from "components/signals/SignalIncompleteAlert";
import {
  getTechSummary,
  getContact,
  formatContact,
  getNextStepSummary,
  formatSuggestedContacts,
  formatTargetDepartments,
} from "sections/activities/signals/utils/signalDisplay";

// Shared per-type detail blocks — the single rendering of each type's
// type-specific fields (B1.2).
import ImpactDetailBlock from "components/signals/detail/ImpactDetailBlock";
import ObjectiveDetailBlock from "components/signals/detail/ObjectiveDetailBlock";
import TechDetailBlock from "components/signals/detail/TechDetailBlock";
import PainDetailBlock from "components/signals/detail/PainDetailBlock";

function formatDate(dateStr) {
  if (!dateStr) return null;
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function formatDateTime(dateStr) {
  if (!dateStr) return null;
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

function getSummary(signal, signalType) {
  if (signalType === "tech-stack") return getTechSummary(signal).name;
  if (signalType === "next-steps") return getNextStepSummary(signal);
  return signal.summary || "—";
}

// ==============================|| SOURCE QUOTE BLOCK ||============================== //

function SourceQuoteBlock({ quote }) {
  if (!quote) return null;
  return (
    <Box
      sx={{
        p: 1.5,
        bgcolor: "grey.50",
        borderRadius: 1,
        borderLeft: 3,
        borderColor: "primary.main",
      }}
    >
      <Typography variant="body2" sx={{ fontStyle: "italic" }} color="text.secondary">
        &ldquo;{quote}&rdquo;
      </Typography>
    </Box>
  );
}

SourceQuoteBlock.propTypes = { quote: PropTypes.string };

// ==============================|| TYPE-SPECIFIC DETAIL SECTIONS ||============================== //

function PainDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <>
      <DrawerSection title="CLASSIFICATION">
        <DrawerFieldRow label="Theme" value={
          signal.what_display && signal.dimension_display
            ? `${signal.what_display} × ${signal.dimension_display}`
            : null
        } />
        <DrawerFieldRow label="Scope" value={signal.scope_level_display} />
        {/* Multi-department scope (M2M): all target_departments, joined. */}
        <DrawerFieldRow label="Department" value={formatTargetDepartments(signal)} />
        <DrawerFieldRow label="Category" value={signal.signal_category_display} />
      </DrawerSection>
      <PainDetailBlock signal={signal} />
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Contact" value={contactName} />
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
PainDetails.propTypes = { signal: PropTypes.object.isRequired };

function ObjectiveDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <>
      <DrawerSection title="CLASSIFICATION">
        <DrawerFieldRow label="Theme" value={
          signal.what_display && signal.dimension_display
            ? `${signal.what_display} × ${signal.dimension_display}`
            : null
        } />
        <DrawerFieldRow label="Scope" value={signal.scope_level_display} />
      </DrawerSection>
      <ObjectiveDetailBlock signal={signal} />
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Contact" value={contactName} />
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
ObjectiveDetails.propTypes = { signal: PropTypes.object.isRequired };

function ImpactDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <>
      <DrawerSection title="CLASSIFICATION">
        <DrawerFieldRow label="Theme" value={
          signal.what_display && signal.dimension_display
            ? `${signal.what_display} × ${signal.dimension_display}`
            : null
        } />
        <DrawerFieldRow label="Scope" value={signal.scope_level_display} />
        {/* Multi-department scope (M2M): all target_departments, joined. */}
        <DrawerFieldRow label="Department" value={formatTargetDepartments(signal)} />
      </DrawerSection>
      <ImpactDetailBlock signal={signal} />
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Contact" value={contactName} />
      </DrawerSection>
    </>
  );
}
ImpactDetails.propTypes = { signal: PropTypes.object.isRequired };

function TechStackDetails({ signal }) {
  const techInfo = getTechSummary(signal);
  const contactName = formatContact(getContact(signal));
  return (
    <>
      <DrawerSection title="IDENTITY">
        <DrawerFieldRow label="Tool">
          <Typography variant="body2">{techInfo.name}</Typography>
        </DrawerFieldRow>
        <DrawerFieldRow label="Mentioned by" value={contactName} />
      </DrawerSection>
      <TechDetailBlock signal={signal} />
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
TechStackDetails.propTypes = { signal: PropTypes.object.isRequired };

function BlockerDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <DrawerSection title="CONTEXT">
      <DrawerFieldRow label="Raised by" value={contactName} />
    </DrawerSection>
  );
}
BlockerDetails.propTypes = { signal: PropTypes.object.isRequired };

function NextStepDetails({ signal }) {
  const suggestedContacts = formatSuggestedContacts(signal.suggested_contacts);
  const linked = signal.linked_activity;
  return (
    <>
      <DrawerSection title="SUGGESTION">
        <DrawerFieldRow label="Type" value={signal.suggested_activity_type_display} />
        <DrawerFieldRow label="Due date" value={formatDate(signal.suggested_due_date)} />
        {signal.suggested_objective && (
          <DrawerFieldRow label="Objective" value={signal.suggested_objective} />
        )}
        {suggestedContacts && (
          <DrawerFieldRow label="Contacts" value={suggestedContacts} />
        )}
      </DrawerSection>
      {linked && (
        <DrawerSection title="LINKED ACTIVITY">
          <DrawerFieldRow label="Title" value={linked.title} />
          <DrawerFieldRow label="Type" value={linked.activity_type_display} />
          <DrawerFieldRow label="Status" value={linked.status_display} />
          <DrawerFieldRow label="Date" value={formatDate(linked.scheduled_date)} />
        </DrawerSection>
      )}
    </>
  );
}
NextStepDetails.propTypes = { signal: PropTypes.object.isRequired };

function PeopleDetails({ signal }) {
  const targetContact = signal.target_contact ? formatContact(signal.target_contact) : null;
  const targetDept = signal.target_department?.name;
  return (
    <>
      <DrawerSection title="ROLE">
        <DrawerFieldRow label="Role" value={signal.role_display} />
        <DrawerFieldRow label="Influence" value={signal.influence_display} />
        <DrawerFieldRow label="Contact" value={targetContact} />
        <DrawerFieldRow label="Department" value={targetDept} />
      </DrawerSection>
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
PeopleDetails.propTypes = { signal: PropTypes.object.isRequired };

function ConstraintDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <>
      <DrawerSection title="CLASSIFICATION">
        <DrawerFieldRow label="Theme" value={
          signal.what_display && signal.dimension_display
            ? `${signal.what_display} × ${signal.dimension_display}`
            : null
        } />
        <DrawerFieldRow label="Rigidity" value={signal.rigidity_display} />
        {/* Multi-department scope (M2M): all target_departments, joined —
            the singular target_department FK was dropped for Constraint. */}
        <DrawerFieldRow label="Department" value={formatTargetDepartments(signal)} />
      </DrawerSection>
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Raised by" value={contactName} />
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
ConstraintDetails.propTypes = { signal: PropTypes.object.isRequired };

// Competitor drawer: only the competitor identity is type-specific — summary,
// source quote and provenance are rendered by the type-agnostic sections.
function CompetitorDetails({ signal }) {
  return (
    <DrawerSection title="COMPETITOR">
      <DrawerFieldRow label="Name" value={signal.competitor_name} />
    </DrawerSection>
  );
}
CompetitorDetails.propTypes = { signal: PropTypes.object.isRequired };

function renderDetails(signal, signalType) {
  switch (signalType) {
    case "pain": return <PainDetails signal={signal} />;
    case "objective": return <ObjectiveDetails signal={signal} />;
    case "impact": return <ImpactDetails signal={signal} />;
    case "tech-stack": return <TechStackDetails signal={signal} />;
    case "blockers": return <BlockerDetails signal={signal} />;
    case "next-steps": return <NextStepDetails signal={signal} />;
    case "people": return <PeopleDetails signal={signal} />;
    case "constraints": return <ConstraintDetails signal={signal} />;
    case "competitors": return <CompetitorDetails signal={signal} />;
    default: return null;
  }
}

// ==============================|| PROVENANCE ||============================== //

function formatDrawerContact(contact) {
  const name = `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  const parts = [
    name || null,
    contact.job_title || null,
    contact.department?.name || null,
  ].filter(Boolean);
  return parts.join(" · ") || null;
}

function ProvenanceSection({ signal, onOpenActivity }) {
  const contacts = signal.source_context?.contacts ?? [];
  const activityId = signal.source_context?.activity?.id ?? null;
  if (contacts.length === 0 && !activityId) return null;

  return (
    <DrawerSection title="ORIGIN">
      {contacts.length > 0 && (
        <DrawerFieldRow label={contacts.length > 1 ? "Contacts" : "Contact"}>
          <Stack spacing={0.25}>
            {contacts.map((c) => (
              <Typography key={c.id} variant="body2">
                {formatDrawerContact(c)}
              </Typography>
            ))}
          </Stack>
        </DrawerFieldRow>
      )}
      {activityId && onOpenActivity && (
        <Button
          size="small"
          variant="text"
          startIcon={<LinkOutlined style={{ fontSize: 13 }} />}
          onClick={() => onOpenActivity(activityId)}
          sx={{ mt: 0.5, px: 0 }}
        >
          View origin activity
        </Button>
      )}
    </DrawerSection>
  );
}
ProvenanceSection.propTypes = {
  signal: PropTypes.object.isRequired,
  onOpenActivity: PropTypes.func,
};

// ==============================|| OBJECTIVE DETAIL VIEW (SIG-5e) ||============================== //
//
// The Objective detail is rebuilt as a READ mirror of EditObjectiveContent: the
// same 5 SectionHeaders + subtitles + the Domain × Dimension recap, values shown
// (not editable). No type/status chips — the type is the coque title, the status
// is muted text. Origin (section 5) is detail-only, with a "View origin activity"
// link shown ONLY when the origin activity differs from the current one.

// Status → coloured pill (StatusPill): pending = warning, validated = success,
// rejected = error. role.main text/border on the role.lighter tint.
const STATUS_PILL = {
  PENDING: { label: "Pending", role: "warning" },
  VALIDATED: { label: "Validated", role: "success" },
  REJECTED: { label: "Rejected", role: "error" },
};

// Numbered section badge — info palette role (mirror of EditObjectiveContent).
function SectionHeader({ index, title, subtitle }) {
  return (
    <Stack spacing={0.25} sx={{ mb: 1 }}>
      <Stack direction="row" spacing={1} alignItems="center">
        <Chip
          label={index}
          size="small"
          color="info"
          sx={{ height: 18, width: 18, fontSize: "0.65rem", fontWeight: 700, "& .MuiChip-label": { px: 0 } }}
        />
        <Typography variant="body2" fontWeight={600}>
          {title}
        </Typography>
      </Stack>
      {subtitle && (
        <Typography variant="caption" color="text.secondary" sx={{ pl: 3.25 }}>
          {subtitle}
        </Typography>
      )}
    </Stack>
  );
}
SectionHeader.propTypes = {
  index: PropTypes.number.isRequired,
  title: PropTypes.string.isRequired,
  subtitle: PropTypes.string,
};

// A read-flow field: a discreet muted label ABOVE the value (not a rigid
// label/value column) — reads like a page, not a form.
function ReadField({ label, value }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <Box sx={{ mb: 1.25 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
        {label}
      </Typography>
      <Typography variant="body2" color="text.primary" sx={{ whiteSpace: "pre-line" }}>
        {value}
      </Typography>
    </Box>
  );
}
ReadField.propTypes = { label: PropTypes.string, value: PropTypes.node };

// A label/value ROW: muted label on the LEFT, value on the RIGHT (2-column,
// value right-aligned). Used for scope + metrics, where each field is a short
// scalar read as "Label ………… Value".
function ReadRow({ label, value }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "baseline",
        justifyContent: "space-between",
        gap: 2,
        mb: 1,
      }}
    >
      <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        color="text.primary"
        sx={{ textAlign: "right", whiteSpace: "pre-line" }}
      >
        {value}
      </Typography>
    </Box>
  );
}
ReadRow.propTypes = { label: PropTypes.string, value: PropTypes.node };

// Read scope as a label/value pair (mirrors the pill's Company / Department).
function objectiveScopeRow(signal) {
  if (signal.scope_level === "DEPARTMENT") {
    return { label: "Department", value: signal.target_department?.name || "—" };
  }
  if (signal.scope_level === "PERSONAL") {
    const c = signal.target_contact;
    const name = c ? `${c.first_name ?? ""} ${c.last_name ?? ""}`.trim() : "";
    return { label: "Contact", value: name || "—" };
  }
  return { label: "Scope", value: "Company" };
}

function ObjectiveDetailView({
  signal,
  onValidate,
  onReject,
  onEdit,
  onReopen,
  onOpenActivity,
  isLocked,
  currentActivityId,
}) {
  const isPending = signal.status === "PENDING";
  const isRejected = signal.status === "REJECTED";
  const missingFields = isPending ? getMissingFields(signal, "objective") : [];
  const validateDisabled = missingFields.length > 0;

  const axisPreview =
    signal.what_display && signal.dimension_display
      ? `${signal.what_display} × ${signal.dimension_display}`
      : null;
  const canonicalPreview =
    signal.what && signal.dimension ? `objective:${signal.what}:${signal.dimension}` : null;

  const contacts = signal.source_context?.contacts ?? [];
  const originActivityId = signal.source_context?.activity?.id ?? null;
  // View-origin link only when the origin activity is NOT the one we're viewing.
  const showOriginLink = Boolean(
    originActivityId && onOpenActivity && originActivityId !== currentActivityId,
  );
  const statusPill = STATUS_PILL[signal.status] ?? { label: signal.status, role: "warning" };
  const hasMetrics = Boolean(signal.success_criteria || signal.target_date || signal.notes);

  return (
    <>
      <Box sx={{ px: 2.5, py: 2, flex: 1, overflow: "auto" }}>
        {/* Title (left) + status pill (right) on one line. The type lives here,
            not in the coque header, so the pill can sit beside it. */}
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 1,
            mb: 2,
          }}
        >
          <Typography variant="h3" fontWeight="bold" data-testid="objective-detail-title">
            {getSignalTypeLabel("objective")}
          </Typography>
          <StatusPill
            label={statusPill.label}
            colorText={`${statusPill.role}.main`}
            colorBg={`${statusPill.role}.lighter`}
          />
        </Box>

        <SignalIncompleteAlert missingFields={missingFields} />

        {signal.validated_by && (
          <ReadField
            label="Validated by"
            value={`${signal.validated_by.first_name || ""} ${signal.validated_by.last_name || ""}`.trim()}
          />
        )}
        {signal.validated_at && (
          <ReadField label="Validated at" value={formatDateTime(signal.validated_at)} />
        )}

        {/* Section 1 — Goal. The summary is the headline (prominent, no label);
            the Domain × Dimension are conveyed by the recap only. Detail exposes
            values — no instruction subtitles (those live in the edit). */}
        <SectionHeader index={1} title="Goal" />
        {signal.summary && (
          <Box
            data-testid="objective-summary-box"
            sx={{
              my: 1,
              px: 1.5,
              py: 1.25,
              bgcolor: "action.hover",
              borderRadius: 1,
            }}
          >
            <Typography
              variant="body1"
              fontWeight={500}
              color="text.primary"
              sx={{ whiteSpace: "pre-line" }}
            >
              {signal.summary}
            </Typography>
          </Box>
        )}
        {axisPreview && (
          <Box
            sx={{
              mt: 1,
              px: 1.5,
              py: 1,
              bgcolor: "action.hover",
              borderRadius: 1,
              borderLeftStyle: "solid",
              borderLeftWidth: 3,
              borderLeftColor: "info.main",
            }}
          >
            <Typography variant="caption" color="text.secondary">
              This is a{" "}
              <Box component="span" sx={{ fontWeight: 600, color: "text.primary" }}>
                {axisPreview}
              </Box>{" "}
              goal
            </Typography>
            <Typography
              variant="caption"
              color="text.disabled"
              display="block"
              sx={{ fontFamily: "monospace", fontSize: "0.7rem", mt: 0.25 }}
            >
              canonical_key: {canonicalPreview}
            </Typography>
          </Box>
        )}

        <Divider sx={{ my: 2 }} />

        {/* Section 2 — Scope, as a label/value row (value right). */}
        <SectionHeader index={2} title="Scope" />
        <ReadRow {...objectiveScopeRow(signal)} />

        <Divider sx={{ my: 2 }} />

        {/* Section 3 — Metrics (one discreet line when empty). */}
        <SectionHeader index={3} title="Metrics" />
        {hasMetrics ? (
          <>
            <ReadRow label="Success criteria" value={signal.success_criteria} />
            <ReadRow label="Target date" value={formatDate(signal.target_date)} />
            <ReadRow label="Notes" value={signal.notes} />
          </>
        ) : (
          <Typography variant="body2" color="text.disabled" sx={{ fontStyle: "italic", my: 1 }}>
            No metrics defined
          </Typography>
        )}

        <Divider sx={{ my: 2 }} />

        {/* Section 4 — Source: the quote, who said it, and (conditionally) a link
            to the origin activity. Merges the former Source quote + Origin. */}
        <SectionHeader index={4} title="Source" />
        {signal.source_quote ? (
          <SourceQuoteBlock quote={signal.source_quote} />
        ) : (
          <Typography variant="body2" color="text.disabled" sx={{ fontStyle: "italic" }}>
            No source quote
          </Typography>
        )}
        {contacts.length > 0 && (
          <Box sx={{ mt: 1.25 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
              {contacts.length > 1 ? "Contacts" : "Contact"}
            </Typography>
            <Stack spacing={0.25}>
              {contacts.map((c) => (
                <Typography key={c.id} variant="body2" color="text.primary">
                  {formatDrawerContact(c)}
                </Typography>
              ))}
            </Stack>
          </Box>
        )}
        {showOriginLink && (
          <Button
            size="small"
            variant="text"
            startIcon={<LinkOutlined style={{ fontSize: 13 }} />}
            onClick={() => onOpenActivity(originActivityId)}
            sx={{ mt: 0.5, px: 0 }}
          >
            View origin activity
          </Button>
        )}
      </Box>

      <Divider />

      {/* Actions — unchanged (Edit ✎ · Reject · Validate · Reopen). */}
      <Box sx={{ px: 2.5, py: 2 }}>
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          {!isLocked && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<EditOutlined style={{ fontSize: 14 }} />}
              onClick={() => onEdit?.(signal, "objective")}
            >
              Edit
            </Button>
          )}
          {isPending && !isLocked && (
            <>
              <Button
                variant="outlined"
                size="small"
                color="error"
                startIcon={<CloseCircleOutlined style={{ fontSize: 14 }} />}
                onClick={() => onReject?.(signal, "objective")}
              >
                Reject
              </Button>
              <Tooltip title={validateDisabled ? "Complete missing fields before validating" : ""}>
                <span>
                  <Button
                    variant="contained"
                    size="small"
                    color="success"
                    disabled={validateDisabled}
                    startIcon={<CheckCircleOutlined style={{ fontSize: 14 }} />}
                    onClick={() => onValidate?.(signal, "objective")}
                  >
                    Validate
                  </Button>
                </span>
              </Tooltip>
            </>
          )}
          {isRejected && !isLocked && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<ReloadOutlined style={{ fontSize: 14 }} />}
              onClick={() => onReopen?.(signal, "objective")}
            >
              Reopen
            </Button>
          )}
        </Stack>
      </Box>
    </>
  );
}
ObjectiveDetailView.propTypes = {
  signal: PropTypes.object.isRequired,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  onReopen: PropTypes.func,
  onOpenActivity: PropTypes.func,
  isLocked: PropTypes.bool,
  currentActivityId: PropTypes.string,
};

// ==============================|| SIGNAL DETAIL CONTENT ||============================== //

/**
 * @param {node} leadingAction   Rendered before the chips (e.g. a Back button).
 * @param {node} trailingAction  Rendered at the far right (e.g. a Close button).
 */
export default function SignalDetailContent({
  signal,
  signalType,
  onValidate,
  onReject,
  onEdit,
  onReopen,
  onOpenActivity,
  isLocked,
  currentActivityId,
  leadingAction,
  trailingAction,
}) {
  if (!signal) return null;

  // SIG-5e — Objective gets the new read-mirror layout (other types unchanged).
  if (signalType === "objective") {
    return (
      <ObjectiveDetailView
        signal={signal}
        onValidate={onValidate}
        onReject={onReject}
        onEdit={onEdit}
        onReopen={onReopen}
        onOpenActivity={onOpenActivity}
        isLocked={isLocked}
        currentActivityId={currentActivityId}
      />
    );
  }

  const isPending = signal.status === "PENDING";
  const isRejected = signal.status === "REJECTED";
  const missingFields = isPending ? getMissingFields(signal, signalType) : [];
  const validateDisabled = missingFields.length > 0;

  return (
    <>
      {/* Header — leading action (back) · chips · trailing action (close) */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 2.5,
          py: 2,
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 0 }}>
          {leadingAction}
          <SignalTypeChip signalType={signalType} size="small" />
          <SignalStatusChip status={signal.status} size="small" />
        </Stack>
        {trailingAction}
      </Box>

      <Divider />

      {/* Body */}
      <Box sx={{ px: 2.5, py: 2, flex: 1, overflow: "auto" }}>
        <SignalIncompleteAlert missingFields={missingFields} />

        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
          {getSummary(signal, signalType)}
        </Typography>

        {signal.validated_by && (
          <DrawerFieldRow
            label="Validated by"
            value={`${signal.validated_by.first_name || ""} ${signal.validated_by.last_name || ""}`.trim()}
          />
        )}
        {signal.validated_at && (
          <DrawerFieldRow label="Validated at" value={formatDateTime(signal.validated_at)} />
        )}
        {(signal.validated_by || signal.validated_at) && <Box sx={{ mb: 1.5 }} />}

        {renderDetails(signal, signalType)}

        {signal.source_quote && (
          <DrawerSection title="SOURCE QUOTE">
            <SourceQuoteBlock quote={signal.source_quote} />
          </DrawerSection>
        )}

        <ProvenanceSection signal={signal} onOpenActivity={onOpenActivity} />
      </Box>

      <Divider />

      {/* Actions */}
      <Box sx={{ px: 2.5, py: 2 }}>
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          {!isLocked && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<EditOutlined style={{ fontSize: 14 }} />}
              onClick={() => onEdit?.(signal, signalType)}
            >
              Edit
            </Button>
          )}
          {isPending && !isLocked && (
            <>
              <Button
                variant="outlined"
                size="small"
                color="error"
                startIcon={<CloseCircleOutlined style={{ fontSize: 14 }} />}
                onClick={() => onReject?.(signal, signalType)}
              >
                Reject
              </Button>
              <Tooltip title={validateDisabled ? "Complete missing fields before validating" : ""}>
                <span>
                  <Button
                    variant="contained"
                    size="small"
                    color="success"
                    disabled={validateDisabled}
                    startIcon={<CheckCircleOutlined style={{ fontSize: 14 }} />}
                    onClick={() => onValidate?.(signal, signalType)}
                  >
                    Validate
                  </Button>
                </span>
              </Tooltip>
            </>
          )}
          {isRejected && !isLocked && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<ReloadOutlined style={{ fontSize: 14 }} />}
              onClick={() => onReopen?.(signal, signalType)}
            >
              Reopen
            </Button>
          )}
        </Stack>
      </Box>
    </>
  );
}

SignalDetailContent.propTypes = {
  signal: PropTypes.object,
  signalType: PropTypes.string,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  onReopen: PropTypes.func,
  onOpenActivity: PropTypes.func,
  isLocked: PropTypes.bool,
  /** The activity currently being viewed — used to hide the "View origin
      activity" link when the signal's origin IS that activity. Optional;
      absent on DC/Account surfaces (link always shown there). */
  currentActivityId: PropTypes.string,
  leadingAction: PropTypes.node,
  trailingAction: PropTypes.node,
};
