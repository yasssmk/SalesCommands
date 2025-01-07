import PropTypes from 'prop-types';
import AccProfileApp from 'views/apps/profiles/account';

// Multiple versions of this page will be statically generated
// using the `params` returned by `generateStaticParams`
export default function Page({ params }) {
  const { tabs } = params;

  return <AccProfileApp tab={tabs} />;
}

// Return a list of `params` to populate the [slug] dynamic segment
export async function generateStaticParams() {
  const response = ['basic', 'personal', 'my-account', 'password', 'role', 'settings'];

  return response.map((tabs) => ({
    tabs: tabs
  }));
}

Page.propTypes = { params: PropTypes.object };
