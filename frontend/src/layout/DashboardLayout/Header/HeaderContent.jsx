// frontend/src/layout/DashboardLayout/Header/HeaderContent.jsx

'use client';
import { useState, useRef } from 'react';

// material-ui
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import ButtonBase from '@mui/material/ButtonBase';
import ClickAwayListener from '@mui/material/ClickAwayListener';
import Paper from '@mui/material/Paper';
import Popper from '@mui/material/Popper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Divider from '@mui/material/Divider';
import MenuList from '@mui/material/MenuList';
import MenuItem from '@mui/material/MenuItem';
import ListItemText from '@mui/material/ListItemText';
import ListItemIcon from '@mui/material/ListItemIcon';

// project import
import Avatar from '@mui/material/Avatar';
import Fade from '@mui/material/Fade';
import { useAuth } from 'hooks/useAuth';
import { ThemeMode } from 'config';

// assets
import LogoutOutlined from '@ant-design/icons/LogoutOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';

// ==============================|| HEADER CONTENT - MVP ||============================== //

export default function HeaderContent() {
  const theme = useTheme();
  const { user, logout } = useAuth();
  
  // Profile dropdown state
  const anchorRef = useRef(null);
  const [open, setOpen] = useState(false);

  const handleToggle = () => {
    setOpen((prevOpen) => !prevOpen);
  };

  const handleClose = (event) => {
    if (anchorRef.current && anchorRef.current.contains(event.target)) {
      return;
    }
    setOpen(false);
  };

  const handleLogout = async () => {
    setOpen(false);
    await logout();
  };

  // Styles
  const iconBackColorOpen = theme.palette.mode === ThemeMode.DARK ? 'background.default' : 'grey.100';

  return (
    <Box sx={{ width: '100%', ml: 1 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ width: '100%' }}>
        
        {/* ==============================|| APP LOGO / TITLE ||============================== */}
        <Box sx={{ display: { xs: 'none', md: 'block' } }}>
          <Typography variant="h4" color="primary" sx={{ fontWeight: 'bold' }}>
            SalesCommands
          </Typography>
        </Box>

        {/* ==============================|| USER PROFILE ||============================== */}
        {user && (
          <Box sx={{ flexShrink: 0 }}>
            <ButtonBase
              sx={{
                p: 0.25,
                bgcolor: open ? iconBackColorOpen : 'transparent',
                borderRadius: 1,
                '&:hover': { 
                  bgcolor: theme.palette.mode === ThemeMode.DARK ? 'secondary.light' : 'secondary.lighter' 
                },
                '&:focus-visible': {
                  outline: `2px solid ${theme.palette.secondary.dark}`,
                  outlineOffset: 2
                }
              }}
              aria-label="open profile"
              ref={anchorRef}
              aria-controls={open ? 'profile-grow' : undefined}
              aria-haspopup="true"
              onClick={handleToggle}
            >
              <Stack direction="row" spacing={1.25} alignItems="center" sx={{ p: 0.5 }}>
                {/* Avatar simple avec initiales */}
                <Avatar 
                  sx={{ 
                    bgcolor: 'primary.main', 
                    color: 'primary.contrastText',
                    width: 32, 
                    height: 32 
                  }}
                >
                  {user.name ? user.name.charAt(0).toUpperCase() : 'U'}
                </Avatar>
                
                {/* Nom utilisateur - masqué sur mobile */}
                <Typography 
                  variant="subtitle1" 
                  sx={{ 
                    display: { xs: 'none', sm: 'block' },
                    textTransform: 'capitalize',
                    fontWeight: 500
                  }}
                >
                  {user.name || 'User'}
                </Typography>
              </Stack>
            </ButtonBase>

            {/* ==============================|| PROFILE DROPDOWN ||============================== */}
            <Popper
              placement="bottom-end"
              open={open}
              anchorEl={anchorRef.current}
              role={undefined}
              transition
              disablePortal
              popperOptions={{
                modifiers: [
                  {
                    name: 'offset',
                    options: {
                      offset: [0, 9]
                    }
                  }
                ]
              }}
            >
              {({ TransitionProps }) => (
                <Fade in={open} {...TransitionProps}>
                  <Paper
                    sx={{
                      boxShadow: theme.customShadows?.z1 || theme.shadows[1],
                      width: 240,
                      minWidth: 200,
                      maxWidth: 290,
                      [theme.breakpoints.down('md')]: {
                        maxWidth: 250
                      }
                    }}
                  >
                    <ClickAwayListener onClickAway={handleClose}>
                      <Box sx={{ py: 1 }}>
                        
                        {/* User Info Header */}
                        <Box sx={{ px: 2, py: 1.5 }}>
                          <Stack spacing={0.5}>
                            <Typography variant="h6">{user.name || 'User'}</Typography>
                            <Typography variant="body2" color="text.secondary">
                              {user.email || ''}
                            </Typography>
                            {user.role && (
                              <Typography variant="caption" color="text.secondary">
                                {user.role}
                              </Typography>
                            )}
                          </Stack>
                        </Box>
                        
                        <Divider />
                        
                        {/* Menu Items */}
                        <MenuList sx={{ py: 1 }}>
                          <MenuItem onClick={handleClose} disabled>
                            <ListItemIcon>
                              <UserOutlined />
                            </ListItemIcon>
                            <ListItemText>
                              <Typography variant="body2">Profile Settings</Typography>
                            </ListItemText>
                          </MenuItem>
                          
                          <Divider />
                          
                          <MenuItem onClick={handleLogout}>
                            <ListItemIcon>
                              <LogoutOutlined />
                            </ListItemIcon>
                            <ListItemText>
                              <Typography variant="body2">Logout</Typography>
                            </ListItemText>
                          </MenuItem>
                        </MenuList>
                        
                      </Box>
                    </ClickAwayListener>
                  </Paper>
                </Fade>
              )}
            </Popper>
          </Box>
        )}

      </Stack>
    </Box>
  );
}