import PropTypes from 'prop-types';
import { Inter } from 'next/font/google';
import Script from 'next/script';
import './globals.css';

// PROJECT IMPORTS
import ProviderWrapper from './ProviderWrapper';

const inter = Inter({ subsets: ['latin'] });

export const metadata = {
  title: 'SalesCommands - Dashboard App',
  description: 'DESCRPTION A CHANGER app/layout',
};

export default function RootLayout({ children }) {

  return (
    <html lang="en">
    <head>
        {process.env.NODE_ENV === 'development' && (
          <Script src="http://localhost:8097" strategy="beforeInteractive" />
        )}
      </head>
      <body className={inter.className}>
        <ProviderWrapper>{children}</ProviderWrapper>
      </body>
    </html>
  );
}

RootLayout.propTypes = { children: PropTypes.node };