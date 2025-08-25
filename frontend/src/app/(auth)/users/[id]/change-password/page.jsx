import ChangePasswordView from 'views/admin/users/change-password';

// ==============================|| CHANGE PASSWORD PAGE ||============================== //

export default function ChangePasswordPage() {
  return <ChangePasswordView />;
}

// Métadonnées de la page (optionnel)
export const metadata = {
  title: 'Change User Password',
  description: 'Change password for user account'
};