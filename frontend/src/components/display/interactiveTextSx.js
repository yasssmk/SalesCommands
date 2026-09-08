// frontend/src/components/display/interactiveTextSx.js
//
// Shared "clickable text" affordance (P4a). Doctrine: important text is bold
// and NEUTRAL at rest (the caller sets color:"text.primary" + a bold weight on
// the text element); the link cue appears only on hover — the text recolours to
// primary and underlines, with a pointer cursor. One source of truth so the
// Context people names (PersonRow) and the Activity header account / DC links
// read identically. Palette tokens only — no hardcoded hex/px.

const interactiveTextSx = {
  cursor: "pointer",
  "&:hover": { color: "primary.main", textDecoration: "underline" },
};

export default interactiveTextSx;
