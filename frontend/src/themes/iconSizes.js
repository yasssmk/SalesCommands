// ==============================|| DEFAULT THEME - ICON SIZES ||============================== //

/**
 * Centralized icon sizes for consistency across the application.
 * 
 * Usage in components:
 *   const theme = useTheme();
 *   <Icon style={{ fontSize: theme.iconSizes.md }} />
 * 
 * Or with 'inherit' for parent-controlled sizing:
 *   <Icon style={{ fontSize: 'inherit' }} />
 * 
 * Size mapping (aligned with typography):
 *   xs: 12px  → matches caption/body2 (0.75rem)
 *   sm: 14px  → matches body1/h6 (0.875rem)
 *   md: 16px  → matches h5 (1rem) - DEFAULT
 *   lg: 18px  → between h5 and h4
 *   xl: 20px  → matches h4 (1.25rem)
 *   xxl: 24px → matches h3 (1.5rem)
 */
export default function IconSizes() {
  return {
    xs: 12,
    sm: 14,
    md: 16,
    lg: 18,
    xl: 20,
    xxl: 24,
    // Semantic aliases
    inline: 'inherit',    // For icons inside text/buttons
    caption: 12,          // Aligned with typography.caption
    body: 14,             // Aligned with typography.body1
    title: 16,            // Aligned with typography.h5
    header: 20,           // Aligned with typography.h4
  };
}