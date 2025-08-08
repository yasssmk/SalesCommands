// project import
import SimpleLayout from 'layout/SimpleLayout';
import Landing from 'views/landing';
import DashboardAnalytics from 'views/dashboard/analytics'

export default function HomePage() {
  return (
    <SimpleLayout>
      <Landing />
    </SimpleLayout>
  );
}

// export default function HomePage() {
//   return (
//       <DashboardAnalytics />
//   );
// }
