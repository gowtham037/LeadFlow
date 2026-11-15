import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { fetchMe, login as apiLogin } from '../api/client';
import type { UserInfo } from '../api/client';

interface AuthContextValue {
  user: UserInfo | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount: if a token exists, validate it and load user
  useEffect(() => {
    const token = localStorage.getItem('leadflow_token');
    const cached = localStorage.getItem('leadflow_user');

    if (!token) {
      setLoading(false);
      return;
    }

    if (cached) {
      try {
        setUser(JSON.parse(cached));
      } catch {
        localStorage.removeItem('leadflow_user');
      }
    }

    fetchMe()
      .then((me) => {
        setUser(me);
        localStorage.setItem('leadflow_user', JSON.stringify(me));
      })
      .catch(() => {
        localStorage.removeItem('leadflow_token');
        localStorage.removeItem('leadflow_user');
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const signIn = async (email: string, password: string) => {
    const res = await apiLogin(email, password);
    localStorage.setItem('leadflow_token', res.access_token);
    localStorage.setItem('leadflow_user', JSON.stringify(res.user));
    setUser(res.user);
  };

  const signOut = () => {
    localStorage.removeItem('leadflow_token');
    localStorage.removeItem('leadflow_user');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
