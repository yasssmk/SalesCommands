// ==============================|| OVERRIDES - LIST ITEM ICON ||============================== //

export default function ListItemButton(theme) {
  return {
    MuiListItemButton: {
      styleOverrides: {
        root: {
          // Existing selected styles
          '&.Mui-selected': {
            color: theme.palette.primary.main,
            '& .MuiListItemIcon-root': {
              color: theme.palette.primary.main
            }
          },
          
          // New disabled styles matching the project's design system
          '&.Mui-disabled': {
            opacity: 0.5,
            cursor: 'not-allowed',
            pointerEvents: 'auto', // Allow cursor change on hover
            
            '& .MuiListItemText-primary': {
              color: theme.palette.text.disabled
            },
            
            '& .MuiListItemIcon-root': {
              opacity: 0.6,
              color: theme.palette.text.disabled
            },
            
            // Prevent hover effects on disabled items
            '&:hover': {
              backgroundColor: 'transparent'
            }
          }
        }
      }
    }
  };
}
