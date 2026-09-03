// frontend/src/components/display/EmptyState.jsx
//
// Centralized themed empty-state primitive. Replaces the pattern duplicated
// ~8 times across the Activity area (a centered icon with a hardcoded grey hex
// and a raw fontSize, a title and a sub-text). Consumes ONLY theme tokens:
// icon size from theme.iconSizes.*, muted colour from theme.aphoriQ.text.muted,
// spacing from the MUI scale. No hardcoded hex or px.

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// ==============================|| EMPTY STATE ||============================== //

export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  iconSize = "xxl",
  titleVariant = "h6",
  descriptionVariant = "body2",
  maxWidth,
  py = 6,
}) {
  const theme = useTheme();

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        textAlign: "center",
        py,
      }}
    >
      <Stack spacing={1.5} alignItems="center">
        {Icon && (
          <Icon
            style={{
              fontSize: theme.iconSizes[iconSize],
              color: theme.aphoriQ.text.muted,
            }}
          />
        )}

        {title && (
          <Typography variant={titleVariant} color="text.primary">
            {title}
          </Typography>
        )}

        {description && (
          <Typography
            variant={descriptionVariant}
            sx={{
              color: theme.aphoriQ.text.muted,
              ...(maxWidth != null && { maxWidth: theme.spacing(maxWidth) }),
            }}
          >
            {description}
          </Typography>
        )}

        {action && <Box sx={{ mt: 0.5 }}>{action}</Box>}
      </Stack>
    </Box>
  );
}

EmptyState.propTypes = {
  /** Icon component (e.g. an ant-design icon). Sized via theme.iconSizes. */
  icon: PropTypes.elementType,
  title: PropTypes.node,
  description: PropTypes.node,
  /** Optional action node (button, link…). */
  action: PropTypes.node,
  /** Key into theme.iconSizes (xs/sm/md/lg/xl/xxl…). */
  iconSize: PropTypes.string,
  titleVariant: PropTypes.string,
  descriptionVariant: PropTypes.string,
  /** Optional max width for the description, in MUI spacing units. */
  maxWidth: PropTypes.number,
  /** Vertical padding, in MUI spacing units. */
  py: PropTypes.number,
};
