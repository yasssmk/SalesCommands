'use client';
import PropTypes from 'prop-types';

import { createContext } from 'react';

// project import
import defaultConfig from '.config';
import useLocalStorage from 'hooks/useLocalStorage';

// initial state
const initialState = {
  ...defaultConfig,
  onChangeContainer: () => {},
  onChangeLocalization: () => {},
  onChangeMode: () => {},
  onChangePresetColor: () => {},
  onChangeDirection: () => {},
  onChangeMiniDrawer: () => {},
  onChangeThemeLayout: () => {},
  onChangeMenuOrientation: () => {},
  onChangeFontFamily: () => {}
};

// ==============================|| CONFIG CONTEXT & PROVIDER ||============================== //

const ConfigContext = createContext(initialState);

function ConfigProvider({ children }) {
  const [config, setConfig] = useLocalStorage('mantis-react-next-ts-config', initialState);

  const onChangeContainer = (container) => {
    setConfig({
      ...config,
      container: container
    });
  };

  const onChangeLocalization = (lang) => {
    setConfig({
      ...config,
      i18n: lang
    });
  };

  const onChangeMode = (mode) => {
    setConfig({
      ...config,
      mode
    });
  };

  const onChangePresetColor = (theme) => {
    setConfig({
      ...config,
      presetColor: theme
    });
  };

  const onChangeDirection = (direction) => {
    setConfig({
      ...config,
      themeDirection: direction
    });
  };

  const onChangeMiniDrawer = (miniDrawer) => {
    setConfig({
      ...config,
      miniDrawer
    });
  };

  const onChangeThemeLayout = (direction, miniDrawer) => {
    setConfig({
      ...config,
      miniDrawer,
      themeDirection: direction
    });
  };

  const onChangeMenuOrientation = (layout) => {
    setConfig({
      ...config,
      menuOrientation: layout
    });
  };

  const onChangeFontFamily = (fontFamily) => {
    setConfig({
      ...config,
      fontFamily
    });
  };

  return (
    <ConfigContext.Provider
      value={{
        ...config,
        onChangeContainer,
        onChangeLocalization,
        onChangeMode,
        onChangePresetColor,
        onChangeDirection,
        onChangeMiniDrawer,
        onChangeThemeLayout,
        onChangeMenuOrientation,
        onChangeFontFamily
      }}
    >
      {children}
    </ConfigContext.Provider>
  );
}

export { ConfigProvider, ConfigContext };

ConfigProvider.propTypes = { children: PropTypes.node };
