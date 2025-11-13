// frontend/src/layout/DashboardLayout/Drawer/DrawerContent/Navigation/NavItem.jsx

import PropTypes from 'prop-types';
import { useEffect } from 'react';

// next
import Link from 'next/link';
import { usePathname } from 'next/navigation';

// material-ui
import { useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// third-party - AJOUT pour i18n
import { FormattedMessage } from 'react-intl';

// project import
import Dot from 'components/@extended/Dot';
import IconButton from 'components/@extended/IconButton';

import { MenuOrientation, ThemeMode, NavActionType } from 'config';
import useConfig from 'hooks/useConfig';
import { useMenuState } from 'hooks/useMenuState';

export default function NavItem({ item, level, isParents = false }) {
  const theme = useTheme();

  // Debug log to check item properties
  if (process.env.NODE_ENV === 'development' && item.disabled !== undefined) {
    console.log('[NavItem Debug]', {
      title: item.title,
      disabled: item.disabled,
      url: item.url,
      tooltip: item.tooltip
    });
  }

  const {
    menuMaster,
    handlerActiveItem,
    handlerHorizontalActiveItem,
    handlerDrawerOpen
  } = useMenuState();
  const drawerOpen = menuMaster.isDashboardDrawerOpened;
  const openItem = menuMaster.openedItem;

  const downLG = useMediaQuery(theme.breakpoints.down('lg'));

  const { mode, menuOrientation } = useConfig();
  let itemTarget = '_self';
  if (item.target) {
    itemTarget = '_blank';
  }

  const Icon = item.icon;
  const itemIcon = item.icon ? (
    <Icon
      style={{
        fontSize: drawerOpen ? '1rem' : '1.25rem',
        ...(menuOrientation === MenuOrientation.HORIZONTAL && isParents && { fontSize: 20, stroke: '1.5' })
      }}
    />
  ) : (
    false
  );

  const isSelected = openItem === item.id;

  const pathname = usePathname();

  // active menu item on page load
  useEffect(() => {
    if (pathname === item.url) handlerActiveItem(item.id);
    // eslint-disable-next-line
  }, [pathname]);

  const textColor = mode === ThemeMode.DARK ? 'grey.400' : 'text.primary';
  const iconSelectedColor = mode === ThemeMode.DARK && drawerOpen ? 'text.primary' : 'primary.main';

  // Helper pour obtenir le titre traduit ou le titre brut comme fallback
  const getItemTitle = () => {
    // Si le titre contient des espaces ou caractères spéciaux, c'est probablement déjà du texte
    // et non une clé i18n, donc on l'affiche directement
    if (item.title && (item.title.includes(' ') || item.title.includes('&'))) {
      return item.title;
    }
    
    // Sinon, on considère que c'est une clé i18n
    return <FormattedMessage id={item.title} defaultMessage={item.title} />;
  };

  // Helper pour obtenir le tooltip traduit
  const getTooltipTitle = () => {
    if (!item.tooltip) return '';
    
    // Si le tooltip contient des espaces, c'est du texte direct
    if (item.tooltip.includes(' ')) {
      return item.tooltip;
    }
    
    // Sinon c'est une clé i18n
    return <FormattedMessage id={item.tooltip} defaultMessage={item.tooltip} />;
  };

  // Build the ListItemButton
  const listItemButton = (
    <ListItemButton
      {...(!item.disabled && { 
        component: Link,
        href: item.url,
        target: itemTarget 
      })}
      disabled={item.disabled}
      selected={isSelected}
      onClick={(e) => {
        if (item.disabled) {
          e.preventDefault();
          e.stopPropagation();
          // Log in development
          if (process.env.NODE_ENV === 'development') {
            console.log('[WIP Menu Click]', { 
              item: item.title, 
              id: item.id,
              tooltip: item.tooltip 
            });
          }
          return;
        }
        // Handle drawer close on mobile
        if (downLG) {
          handlerDrawerOpen(false);
        }
      }}
      sx={{
        zIndex: 1201,
        pl: drawerOpen ? `${level * 28}px` : 1.5,
        py: !drawerOpen && level === 1 ? 1.25 : 1,
        ...(drawerOpen && {
          '&:hover': {
            bgcolor: mode === ThemeMode.DARK ? 'divider' : 'primary.lighter'
          },
          '&.Mui-selected': {
            bgcolor: mode === ThemeMode.DARK ? 'divider' : 'primary.lighter',
            borderRight: '2px solid',
            borderRightColor: 'primary.main',
            color: iconSelectedColor,
            '&:hover': {
              color: iconSelectedColor,
              bgcolor: mode === ThemeMode.DARK ? 'divider' : 'primary.lighter'
            }
          }
        }),
        ...(!drawerOpen && {
          '&:hover': {
            bgcolor: 'transparent'
          },
          '&.Mui-selected': {
            '&:hover': {
              bgcolor: 'transparent'
            },
            bgcolor: 'transparent'
          }
        })
      }}
    >
    
      {itemIcon && (
        <ListItemIcon
          sx={{
            minWidth: 28,
            color: isSelected ? iconSelectedColor : textColor,
            ...(!drawerOpen && {
              borderRadius: 1.5,
              width: 36,
              height: 36,
              alignItems: 'center',
              justifyContent: 'center',
              mr: 1,
              '&:hover': {
                bgcolor: mode === ThemeMode.DARK ? 'secondary.light' : 'secondary.lighter'
              }
            }),
            ...(!drawerOpen &&
              isSelected && {
                bgcolor: mode === ThemeMode.DARK ? 'primary.900' : 'primary.lighter',
                '&:hover': {
                  bgcolor: mode === ThemeMode.DARK ? 'primary.darker' : 'primary.lighter'
                }
              })
          }}
        >
          {itemIcon}
        </ListItemIcon>
      )}
      {(drawerOpen || (!drawerOpen && level !== 1)) && (
        <ListItemText
          primary={
            <Typography variant="h6" sx={{ color: isSelected ? iconSelectedColor : textColor }}>
              {getItemTitle()}
            </Typography>
          }
        />
      )}
      
      {/* WIP Badge - Added for disabled items */}
      {(drawerOpen || (!drawerOpen && level !== 1)) && item.disabled && item.tooltip && (
        <Chip
          color="warning"
          variant="outlined"
          size="small"
          label={item.tooltip}
          sx={{ 
            height: 20,
            fontSize: '0.625rem',
            ml: 1
          }}
        />
      )}
      
      {/* Original chip */}
      {(drawerOpen || (!drawerOpen && level !== 1)) && !item.disabled && item.chip && (
        <Chip
          color={item.chip.color}
          variant={item.chip.variant}
          size={item.chip.size}
          label={item.chip.label}
          avatar={item.chip.avatar && <Avatar>{item.chip.avatar}</Avatar>}
        />
      )}
    </ListItemButton>
  );

  return (
    <>
      {menuOrientation === MenuOrientation.VERTICAL || downLG ? (
        <Box sx={{ position: 'relative' }}>
          {/* Add tooltip wrapper only for disabled items */}
          {item.disabled && item.tooltip ? (
            <Tooltip title={item.tooltip} placement="right" arrow>
              <span>{listItemButton}</span>
            </Tooltip>
          ) : (
            listItemButton
          )}
          
          {(drawerOpen || (!drawerOpen && level !== 1)) &&
            item?.actions &&
            item?.actions.map((action, index) => {
              const ActionIcon = action.icon;
              const callAction = action?.function;
              return (
                <IconButton
                  key={index}
                  {...(action.type === NavActionType.FUNCTION && {
                    onClick: (event) => {
                      event.stopPropagation();
                      callAction();
                    }
                  })}
                  {...(action.type === NavActionType.LINK && {
                    component: Link,
                    href: action.url,
                    target: action.target ? '_blank' : '_self'
                  })}
                  color="secondary"
                  variant="outlined"
                  sx={{
                    position: 'absolute',
                    top: 12,
                    right: 20,
                    zIndex: 1202,
                    width: 20,
                    height: 20,
                    mr: -1,
                    ml: 1,
                    color: 'secondary.dark',
                    borderColor: isSelected ? 'primary.light' : 'secondary.light',
                    '&:hover': { borderColor: isSelected ? 'primary.main' : 'secondary.main' }
                  }}
                >
                  <ActionIcon style={{ fontSize: '0.625rem' }} />
                </IconButton>
              );
            })}
        </Box>
      ) : (
        <ListItemButton
          {...(!item.disabled && {
            component: Link,
            href: item.url,
            target: itemTarget
          })}
          disabled={item.disabled}
          selected={isSelected}
          onClick={(e) => {
            if (item.disabled) {
              e.preventDefault();
              e.stopPropagation();
              if (process.env.NODE_ENV === 'development') {
                console.log('[WIP Menu Click]', { 
                  item: item.title, 
                  id: item.id,
                  tooltip: item.tooltip 
                });
              }
              return;
            }
            if (isParents) {
              handlerHorizontalActiveItem(item.id);
            }
          }}
          sx={{
            zIndex: 1201,
            ...(isParents && {
              p: 1,
              mr: 1
            })
          }}
        >
          {itemIcon && (
            <ListItemIcon
              sx={{
                minWidth: 28,
                ...(!drawerOpen && {
                  borderRadius: 1.5,
                  width: 28,
                  height: 28,
                  alignItems: 'center',
                  justifyContent: 'flex-start',
                  '&:hover': {
                    bgcolor: 'transparent'
                  }
                }),
                ...(!drawerOpen &&
                  isSelected && {
                    bgcolor: 'transparent',
                    '&:hover': {
                      bgcolor: 'transparent'
                    }
                  })
              }}
            >
              {itemIcon}
            </ListItemIcon>
          )}

          {!itemIcon && (
            <ListItemIcon
              sx={{
                color: isSelected ? 'primary.main' : 'secondary.dark',
                ...(!drawerOpen && {
                  borderRadius: 1.5,
                  alignItems: 'center',
                  justifyContent: 'flex-start',
                  '&:hover': {
                    bgcolor: 'transparent'
                  }
                }),
                ...(!drawerOpen &&
                  isSelected && {
                    bgcolor: 'transparent',
                    '&:hover': {
                      bgcolor: 'transparent'
                    }
                  })
              }}
            >
              <Dot size={4} color={isSelected ? 'primary' : 'secondary'} />
            </ListItemIcon>
          )}
          <ListItemText
            primary={
              <Typography variant="h6" color={isSelected ? 'primary.main' : 'secondary.dark'}>
                {getItemTitle()}
              </Typography>
            }
          />
          {(drawerOpen || (!drawerOpen && level !== 1)) && item.chip && (
            <Chip
              color={item.chip.color}
              variant={item.chip.variant}
              size={item.chip.size}
              label={item.chip.label}
              avatar={item.chip.avatar && <Avatar>{item.chip.avatar}</Avatar>}
            />
          )}
        </ListItemButton>
      )}
    </>
  );
}

NavItem.propTypes = { item: PropTypes.any, level: PropTypes.number, isParents: PropTypes.bool };