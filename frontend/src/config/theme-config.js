// next
import { Public_Sans } from 'next/font/google';

// ==============================|| THEME CONSTANT ||============================== //

export const twitterColor = '#1DA1F2';
export const facebookColor = '#3b5998';
export const linkedInColor = '#0e76a8';

export const APP_DEFAULT_PATH = '/';
export const DRAWER_WIDTH = 260;           // Largeur du menu latéral (sidebar)
export const MINI_DRAWER_WIDTH = 60;       // Largeur du menu replié (icônes seulement)
export const HORIZONTAL_MAX_ITEM = 7;      // Nombre max d'items dans menu horizontal

const publicSans = Public_Sans({ subsets: ['latin'], weight: ['400', '500', '300', '700'] });

export let SimpleLayoutType;

(function (SimpleLayoutType) {
  SimpleLayoutType['SIMPLE'] = 'simple';    // Layout basique
  SimpleLayoutType['LANDING'] = 'landing';  // Page d'accueil marketing
})(SimpleLayoutType || (SimpleLayoutType = {}));

export let ThemeMode;

(function (ThemeMode) {
  ThemeMode['LIGHT'] = 'light'; // Mode clair (défaut)
  ThemeMode['DARK'] = 'dark';   // Mode sombre
})(ThemeMode || (ThemeMode = {}));

export let MenuOrientation;

(function (MenuOrientation) {
  MenuOrientation['VERTICAL'] = 'vertical';     // Menu latéral (défaut)
  MenuOrientation['HORIZONTAL'] = 'horizontal'; // Menu en haut
})(MenuOrientation || (MenuOrientation = {}));

export let ThemeDirection;

(function (ThemeDirection) {
  ThemeDirection['LTR'] = 'ltr';    // Gauche vers droite (français)
  ThemeDirection['RTL'] = 'rtl';    // Droite vers gauche (arabe)
})(ThemeDirection || (ThemeDirection = {}));

export let NavActionType;

(function (NavActionType) {
  NavActionType['FUNCTION'] = 'function';
  NavActionType['LINK'] = 'link';
})(NavActionType || (NavActionType = {}));

export let Gender;

(function (Gender) {
  Gender['MALE'] = 'Male';
  Gender['FEMALE'] = 'Female';
})(Gender || (Gender = {}));

export let DropzoneType;

(function (DropzoneType) {
  DropzoneType['DEFAULT'] = 'default';
  DropzoneType['STANDARD'] = 'standard';
})(DropzoneType || (DropzoneType = {}));

// ==============================|| THEME CONFIG ||============================== //

const config = {
  fontFamily: publicSans.style.fontFamily,  // Police globale
  i18n: 'en',                               // Langue par défault
  menuOrientation: MenuOrientation.VERTICAL,// Police globale
  miniDrawer: false,                        // Menu normal (pas replié)
  container: true,                          // Conteneur avec largeur max
  mode: ThemeMode.LIGHT,                    // Mode clair
  presetColor: 'theme5',                   // Couleur primaire (bleu) [Dans themes/theme/index.js]
  themeDirection: ThemeDirection.LTR        // Texte gauche→droite
};

export default config;
