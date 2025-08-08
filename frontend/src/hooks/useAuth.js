'use client';
import { createContext, useContext, useEffect, useState } from 'react';

// ==============================|| AUTH CONTEXT ||============================== //

const AuthContext = createContext();

// ==============================|| AUTH PROVIDER ||============================== //

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Vérification auth au chargement
  useEffect(() => {
    // TODO: Quand vous donnerez l'API Django, remplacer par :
    // const token = localStorage.getItem('authToken');
    // if (token) {
    //   // Vérifier le token avec votre backend
    // }
    
    // SIMULATION pour l'instant - pas d'utilisateur connecté
    setIsAuthenticated(false);
    setUser(null);
    setIsLoading(false);
  }, []);

  const login = async (email, password) => {
    // TODO: Implémenter avec votre API Django
    return { success: false, error: 'API pas encore configurée' };
  };

  const logout = async () => {
    // TODO: Implémenter avec votre API Django
    setUser(null);
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated,
      isLoading,
      login,
      logout
    }}>
      {children}
    </AuthContext.Provider>
  );
}

// ==============================|| AUTH HOOK ||============================== //

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth doit être utilisé dans un AuthProvider');
  }
  return context;
}