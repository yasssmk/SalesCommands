// frontend/src/components/signals/ContactInline.jsx
//
// SIG-5f — a contact identity rendered inline as "Full Name · job · department",
// with the full name EMPHASISED (bold, text.primary) and the job title +
// department in RETREAT (muted, text.secondary), separators included. So the
// name reads first, the rest recedes.
//
// Shared by the signal detail drawer (ORIGIN / Source contact) and the signal
// line meta (SignalLine, also reused on DC/Account) so the treatment is
// identical everywhere. Theme tokens only, no hex.

"use client";

import PropTypes from "prop-types";

import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";

// The shared inline identity rendering: a name in bold text.primary, then the
// meta parts muted (text.secondary) joined with " · ". ContactInline builds it
// from a contact; People S4 reuses it for the People line identity
// (name · department · role). Empty meta parts are dropped — no orphan separator.
export function IdentityInline({ name, meta = [], variant = "body2", ...rest }) {
  const parts = meta.filter(Boolean);
  if (!name && parts.length === 0) return null;

  return (
    <Typography variant={variant} component="span" {...rest}>
      {name && (
        <Box component="span" sx={{ fontWeight: 600, color: "text.primary" }}>
          {name}
        </Box>
      )}
      {parts.length > 0 && (
        <Box component="span" sx={{ color: "text.secondary" }}>
          {name ? " · " : ""}
          {parts.join(" · ")}
        </Box>
      )}
    </Typography>
  );
}

IdentityInline.propTypes = {
  /** The bold, primary part. */
  name: PropTypes.string,
  /** The muted parts, joined with " · " (falsy entries dropped). */
  meta: PropTypes.arrayOf(PropTypes.string),
  /** Typography variant for the whole inline (default body2). */
  variant: PropTypes.string,
};

export default function ContactInline({ contact, variant = "body2", ...rest }) {
  if (!contact) return null;
  const name = `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  const meta = [contact.job_title || null, contact.department?.name || null];
  return <IdentityInline name={name} meta={meta} variant={variant} {...rest} />;
}

ContactInline.propTypes = {
  /** A contact: first_name / last_name (name), job_title + department.name (meta). */
  contact: PropTypes.shape({
    first_name: PropTypes.string,
    last_name: PropTypes.string,
    job_title: PropTypes.string,
    department: PropTypes.shape({ name: PropTypes.string }),
  }),
  /** Typography variant for the whole inline (default body2). */
  variant: PropTypes.string,
};
