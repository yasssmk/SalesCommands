'use client';
import PropTypes from 'prop-types';

import { useEffect, useState } from 'react';

// next
import NextLink from 'next/link';
import { usePathname } from 'next/navigation';

// material-ui
import { useTheme } from '@mui/material/styles';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Unstable_Grid2';
import Typography from '@mui/material/Typography';
import MuiBreadcrumbs from '@mui/material/Breadcrumbs';

// third-party - i18n
import { FormattedMessage } from 'react-intl';

// project import
import MainCard from 'components/MainCard';
import { ThemeDirection } from 'config';
import navigation from 'menu-items';

// assets
import ApartmentOutlined from '@ant-design/icons/ApartmentOutlined';
import HomeOutlined from '@ant-design/icons/HomeOutlined';
import HomeFilled from '@ant-design/icons/HomeFilled';

// ==============================|| HELPER FUNCTION - i18n ||============================== //

/**
 * Helper pour obtenir un titre traduit ou le titre brut comme fallback
 * Même logique que dans NavItem.jsx
 */
const getTranslatedTitle = (title) => {
  if (!title) return '';
  
  // Si le titre contient des espaces ou caractères spéciaux, c'est du texte brut
  if (title.includes(' ') || title.includes('&')) {
    return title;
  }
  
  // Sinon, c'est une clé i18n
  return <FormattedMessage id={title} defaultMessage={title} />;
};

// ==============================|| BREADCRUMBS COMPONENT ||============================== //

export default function Breadcrumbs({
  card = false,
  custom = false,
  divider = false,
  heading,
  icon,
  icons,
  maxItems,
  links,
  rightAlign,
  separator,
  title = true,
  titleBottom = true,
  sx,
  ...others
}) {
  const theme = useTheme();
  const location = usePathname();
  const [main, setMain] = useState();
  const [item, setItem] = useState();

  const iconSX = {
    marginRight: theme.direction === ThemeDirection.RTL ? 0 : theme.spacing(0.75),
    marginLeft: theme.direction === ThemeDirection.RTL ? theme.spacing(0.75) : 0,
    width: '1rem',
    height: '1rem',
    color: theme.palette.secondary.main
  };

  let customLocation = location;

  // only used for component demo breadcrumbs
  if (customLocation.includes('/components-overview/breadcrumbs')) {
    customLocation = '/apps/customer/card';
  }

  useEffect(() => {
  let found = false;
  
  navigation?.items?.forEach((menu) => {
    if (menu.type && menu.type === 'group') {
      if (menu?.url && menu.url === customLocation) {
        setMain(menu);
        setItem(menu);
        found = true;
      } else {
        if (getCollapse(menu)) {
          found = true;
        }
      }
    }
  });

  // Si aucune correspondance trouvée, réinitialiser les states
  if (!found) {
    setMain(undefined);
    setItem(undefined);
  }
});

  // set active item state
const getCollapse = (menu) => {
  if (!custom && menu.children) {
    let found = false;
    menu.children.forEach((collapse) => {
      if (collapse.type && collapse.type === 'collapse') {
        // Appel récursif
        if (getCollapse(collapse)) {
          found = true;
        }
        if (collapse.url === customLocation) {
          setMain(collapse);
          setItem(collapse);
          found = true;
        }
      } else if (collapse.type && collapse.type === 'item') {
        if (customLocation === collapse.url) {
          setMain(menu);
          setItem(collapse);
          found = true;
        }
      }
    });
    return found;
  }
  return false;
};

  // item separator
  const SeparatorIcon = separator;
  const separatorIcon = separator ? <SeparatorIcon style={{ fontSize: '0.75rem', marginTop: 2 }} /> : '/';

  let mainContent;
  let itemContent;
  let breadcrumbContent = <Typography />;
  let itemTitle = '';
  let CollapseIcon;
  let ItemIcon;

  // collapse item
  if (!custom && main && main.type === 'collapse' && main.breadcrumbs === true) {
    CollapseIcon = main.icon ? main.icon : ApartmentOutlined;
  //   mainContent = (
  //     <NextLink href={main.url} passHref legacyBehavior>
  //       <Typography
  //         variant={location === main.url ? 'subtitle1' : 'h6'}
  //         sx={{ textDecoration: 'none', cursor: 'pointer' }}
  //         color={location === main.url ? 'text.primary' : 'text.secondary'}
  //       >
  //         {icons && <CollapseIcon style={iconSX} />}
  //         {getTranslatedTitle(main.title)}
  //       </Typography>
  //     </NextLink>
  //   );

  //   breadcrumbContent = (
  //     <MainCard
  //       border={card}
  //       sx={card === false ? { mb: 3, bgcolor: 'inherit', backgroundImage: 'none', ...sx } : { mb: 3, ...sx }}
  //       {...others}
  //       content={card}
  //       shadow="none"
  //     >
  //       <Grid
  //         container
  //         direction={rightAlign ? 'row' : 'column'}
  //         justifyContent={rightAlign ? 'space-between' : 'flex-start'}
  //         alignItems={rightAlign ? 'center' : 'flex-start'}
  //         spacing={1}
           
  //       >
  //         <Grid >
  //           <MuiBreadcrumbs aria-label="breadcrumb" maxItems={maxItems || 8} separator={separatorIcon}>
  //             <NextLink href="/" passHref legacyBehavior>
  //               <Typography color="text.secondary" variant="h6" sx={{ textDecoration: 'none', cursor: 'pointer' }}>
  //                 {icons && <HomeOutlined style={iconSX} />}
  //                 {icon && !icons && <HomeFilled style={{ ...iconSX, marginRight: 0 }} />}
  //                 {(!icon || icons) && 'Home'}
  //               </Typography>
  //             </NextLink>
  //             {mainContent}
  //           </MuiBreadcrumbs>
  //         </Grid>
  //         {title && titleBottom && (
  //           <Grid sx={{ mt: card === false ? 0.25 : 1 }}>
  //             <Typography variant="h2">{getTranslatedTitle(main.title)}</Typography>
  //           </Grid>
  //         )}
  //       </Grid>
  //       {card === false && divider !== false && <Divider sx={{ mt: 2 }} />}
  //     </MainCard>
  //   );
  // }

  mainContent = (
      <Typography
        variant="h6"
        sx={{ textDecoration: 'none' }}
        color="text.secondary"
      >
        {icons && <CollapseIcon style={iconSX} />}
        {getTranslatedTitle(main.title)}
      </Typography>
    );

    breadcrumbContent = (
      <MainCard
        border={card}
        sx={card === false ? { mb: 3, bgcolor: 'inherit', backgroundImage: 'none', ...sx } : { mb: 3, ...sx }}
        {...others}
        content={card}
        shadow="none"
      >
        <Grid
          container
          direction={rightAlign ? 'row' : 'column'}
          justifyContent={rightAlign ? 'space-between' : 'flex-start'}
          alignItems={rightAlign ? 'center' : 'flex-start'}
          spacing={1}
           
        >
          <Grid >
            <MuiBreadcrumbs aria-label="breadcrumb" maxItems={maxItems || 8} separator={separatorIcon}>
              <NextLink href="/" passHref legacyBehavior>
                <Typography color="text.secondary" variant="h6" sx={{ textDecoration: 'none', cursor: 'pointer' }}>
                  {icons && <HomeOutlined style={iconSX} />}
                  {icon && !icons && <HomeFilled style={{ ...iconSX, marginRight: 0 }} />}
                  {(!icon || icons) && 'Home'}
                </Typography>
              </NextLink>
              {mainContent}
            </MuiBreadcrumbs>
          </Grid>
          {title && titleBottom && (
            <Grid sx={{ mt: card === false ? 0.25 : 1 }}>
              <Typography variant="h2">{getTranslatedTitle(main.title)}</Typography>
            </Grid>
          )}
        </Grid>
        {card === false && divider !== false && <Divider sx={{ mt: 2 }} />}
      </MainCard>
    );
  }

  // items
  if ((item && item.type === 'item') || (item?.type === 'group' && item?.url) || custom) {
    itemTitle = item?.title;

    ItemIcon = item?.icon ? item.icon : ApartmentOutlined;
    itemContent = (
      <Typography variant="subtitle1" color="text.primary">
        {icons && <ItemIcon style={iconSX} />}
        {getTranslatedTitle(itemTitle)}
      </Typography>
    );

    let tempContent = (
      <MuiBreadcrumbs aria-label="breadcrumb" maxItems={maxItems || 8} separator={separatorIcon}>
        <NextLink href="/" passHref legacyBehavior>
          <Typography color="text.secondary" variant="h6" sx={{ textDecoration: 'none', cursor: 'pointer' }}>
            {icons && <HomeOutlined style={iconSX} />}
            {icon && !icons && <HomeFilled style={{ ...iconSX, marginRight: 0 }} />}
            {(!icon || icons) && 'Home'}
          </Typography>
        </NextLink>
        {mainContent}
        {itemContent}
      </MuiBreadcrumbs>
    );

    if (custom && links && links?.length > 0) {
      tempContent = (
        <MuiBreadcrumbs aria-label="breadcrumb" maxItems={maxItems || 8} separator={separatorIcon}>
          {links?.map((link, index) => {
            CollapseIcon = link.icon ? link.icon : ApartmentOutlined;
            const key = index.toString();
            let breadcrumbLink = (
              <Typography
                key={index}
                variant={!link.to ? 'subtitle1' : 'h6'}
                sx={{ textDecoration: 'none', ...(link.to && { cursor: 'pointer' }) }}
                color={!link.to ? 'text.primary' : 'text.secondary'}
              >
                {link.icon && <CollapseIcon style={iconSX} />}
                {getTranslatedTitle(link.title)}
              </Typography>
            );
            if (link.to) {
              breadcrumbLink = (
                <NextLink key={key} href={link.to} passHref legacyBehavior>
                  {breadcrumbLink}
                </NextLink>
              );
            }
            return breadcrumbLink;
          })}
        </MuiBreadcrumbs>
      );
    }

    // main
    if (item?.breadcrumbs !== false || custom) {
      breadcrumbContent = (
        <MainCard
          border={card}
          sx={card === false ? { mb: 3, bgcolor: 'inherit', backgroundImage: 'none', ...sx } : { mb: 3, ...sx }}
          {...others}
          content={card}
          shadow="none"
        >
          <Grid
            container
            direction={rightAlign ? 'row' : 'column'}
            justifyContent={rightAlign ? 'space-between' : 'flex-start'}
            alignItems={rightAlign ? 'center' : 'flex-start'}
            spacing={1}
            
          >
            {title && !titleBottom && (
              <Grid >
                <Typography variant="h2">
                  {custom ? heading : getTranslatedTitle(item?.title)}
                </Typography>
              </Grid>
            )}
            <Grid >{tempContent}</Grid>
            {title && titleBottom && (
              <Grid sx={{ mt: card === false ? 0.25 : 1 }}>
                <Typography variant="h2">
                  {custom ? heading : getTranslatedTitle(item?.title)}
                </Typography>
              </Grid>
            )}
          </Grid>
          {card === false && divider !== false && <Divider sx={{ mt: 2 }} />}
        </MainCard>
      );
    }
  }

  return breadcrumbContent;
}

Breadcrumbs.propTypes = {
  card: PropTypes.bool,
  custom: PropTypes.bool,
  divider: PropTypes.bool,
  heading: PropTypes.string,
  icon: PropTypes.bool,
  icons: PropTypes.bool,
  maxItems: PropTypes.number,
  links: PropTypes.array,
  rightAlign: PropTypes.bool,
  separator: PropTypes.any,
  title: PropTypes.bool,
  titleBottom: PropTypes.bool,
  sx: PropTypes.any,
  others: PropTypes.any
};