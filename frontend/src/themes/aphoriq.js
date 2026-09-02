// ==============================|| APHORIQ THEME NAMESPACE — BASE TOKENS ||============================== //

/**
 * aphoriQ — the project's own token namespace, attached to the MUI theme
 * alongside the template's existing tokens (palette, iconSizes, customShadows).
 *
 * WHY a namespace (not a second theme / second ThemeProvider):
 *   Pages migrate to aphoriQ one at a time. Untouched pages keep consuming the
 *   template tokens; migrated pages read `theme.aphoriQ.*`. When the whole app
 *   consumes aphoriQ, the legacy tokens are removed and aphoriQ becomes the
 *   theme (final pass — out of scope here).
 *
 * MECHANISM (cloned from customShadows/iconSizes in themes/index.jsx):
 *   A factory attached to createTheme and read via `theme.aphoriQ.*`.
 *   customShadows is the precise pattern cloned here: a factory that TAKES the
 *   assembled theme so every color is a REFERENCE to a palette token — never a
 *   frozen hex. Because `theme` already reflects the active mode (light/dark),
 *   the referenced greys/text invert automatically; aphoriQ needs no per-mode
 *   branching of its own.
 *
 * Usage in a component:
 *   const theme = useTheme();
 *   <Box sx={{
 *     bgcolor: theme.aphoriQ.surface.level2,
 *     borderRadius: `${theme.aphoriQ.radius.lg}px`,
 *     border: `${theme.aphoriQ.border.width.hairline}px solid ${theme.aphoriQ.border.color}`,
 *   }} />
 *
 * Values are calibrated on what the Activity pages fabricate by hand today
 * (e.g. ActivityOverviewTab.jsx:1158-1161 `bgcolor:'grey.50'` + `border:'1px
 * solid'` + `borderColor:'grey.200'` + `borderRadius:1` = 4px) plus the MD
 * targets (surface-2, 0.5px border, 12px radius).
 */
export default function AphoriQ(theme) {
  const { palette } = theme;

  return {
    // --- Radius scale (px) — sm(4) matches the current borderRadius:1;
    //     lg(12) is the MD target. Dimensionless design scale, not a color. ---
    radius: {
      none: 0,
      sm: 4,
      md: 8,
      lg: 12, // MD target
      xl: 16,
      pill: 999,
    },

    // --- Border scale — hairline(0.5) is the MD target; thin(1) matches the
    //     current `border:'1px solid'`. `color` REFERENCES the palette. ---
    border: {
      width: {
        hairline: 0.5, // MD target
        thin: 1,
        thick: 2,
      },
      color: palette.divider, // = grey.200 in light; inverts by mode
      colorStrong: palette.grey[300],
    },

    // --- Surfaces — level2 is the "2nd surface" the pages fake with grey.50.
    //     All reference palette tokens (mode-correct), never a frozen hex. ---
    surface: {
      level1: palette.background.paper, // grey.0
      level2: palette.grey[50], // the fabricated 2nd surface
      level3: palette.grey[100],
    },

    // --- References into the existing palette so components have ONE aphoriQ
    //     access point for these too. ---
    text: {
      muted: palette.text.secondary,
      subtle: palette.text.disabled,
    },
    accent: palette.primary.main,
    warningTint: palette.warning.lighter,
  };
}
