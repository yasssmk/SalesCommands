'use client';
import PropTypes from 'prop-types';

// material-ui
import { styled, useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Container from '@mui/material/Container';
import CardMedia from '@mui/material/CardMedia';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import Link from '@mui/material/Link';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// third party
import { motion } from 'framer-motion';

// project import
import AnimateButton from 'components/@extended/AnimateButton';
import { ThemeDirection, ThemeMode } from 'config';
import useConfig from 'hooks/useConfig';

// assets
import FacebookFilled from '@ant-design/icons/FacebookFilled';
import InstagramFilled from '@ant-design/icons/InstagramFilled';
import LinkedinFilled from '@ant-design/icons/LinkedinFilled';
import TwitterOutlined from '@ant-design/icons/TwitterOutlined';
import SendOutlined from '@ant-design/icons/SendOutlined';

const imgfooterlogo = 'assets/images/landing/codedthemes-logo.svg';

// link - custom style
const FooterLink = styled(Link)(({ theme }) => ({
  color: theme.palette.text.secondary,
  '&:hover': {
    color: theme.palette.primary.main
  },
  '&:active': {
    color: theme.palette.primary.main
  }
}));

export default function FooterBlock({ isFull }) {
  const theme = useTheme();
  const { mode, presetColor } = useConfig();
  const textColor = mode === ThemeMode.DARK ? 'text.primary' : 'background.paper';

  const linkSX = {
    color: theme.palette.common.white,
    fontSize: '0.875rem',
    fontWeight: 400,
    opacity: '0.6',
    cursor: 'pointer',
    '&:hover': {
      opacity: '1'
    }
  };

  const frameworks = [
    { title: 'CodeIgniter', link: 'https://codedthemes.com/item/mantis-codeigniter-admin-template/' },
    {
      title: 'React MUI',
      link: 'https://mui.com/store/items/mantis-react-admin-dashboard-template/'
    },
    {
      title: 'Angular',
      link: 'https://codedthemes.com/item/mantis-angular-admin-template/'
    },
    {
      title: 'Bootstrap 5',
      link: 'https://codedthemes.com/item/mantis-bootstrap-admin-dashboard/'
    },
    {
      title: '.Net',
      link: 'https://codedthemes.com/item/mantis-dotnet-bootstrap-dashboard-template/'
    }
  ];

  return (
    <>
      <Divider sx={{ borderColor: 'grey.700' }} />
      <Box sx={{ py: 1.5, bgcolor: mode === ThemeMode.DARK ? 'grey.50' : 'grey.800' }}>
        <Container>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={8}>
              <Typography variant="subtitle2" color="secondary">
                © Made with love by Team CodedThemes
              </Typography>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Grid container spacing={2} alignItems="center" sx={{ justifyContent: 'flex-end' }}>
                <Grid item>
                  <Link href="https://www.instagram.com/codedthemes" underline="none" target="_blank" sx={linkSX}>
                    <InstagramFilled />
                  </Link>
                </Grid>
                <Grid item>
                  <Link href="https://twitter.com/codedthemes/status/1768163845858603500" underline="none" target="_blank" sx={linkSX}>
                    <TwitterOutlined />
                  </Link>
                </Grid>
                <Grid item>
                  <Link href="https://in.linkedin.com/company/codedthemes" underline="none" target="_blank" sx={linkSX}>
                    <LinkedinFilled />
                  </Link>
                </Grid>
                <Grid item>
                  <Link href="https://www.facebook.com/codedthemes/" underline="none" target="_blank" sx={linkSX}>
                    <FacebookFilled />
                  </Link>
                </Grid>
              </Grid>
            </Grid>
          </Grid>
        </Container>
      </Box>
    </>
  );
}

FooterBlock.propTypes = { isFull: PropTypes.bool };
