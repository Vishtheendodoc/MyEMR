import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { api, clearTokens, setTokens, User } from '../api/client';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    try {
      const u = await api.me();
      setUser(u);
    } catch {
      setUser(null);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      refreshUser().finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    const tokens = await api.login(email, password);
    setTokens(tokens.access_token, tokens.refresh_token);
    await refreshUser();
  };

  const logout = () => {
    const refresh = localStorage.getItem('refresh_token');
    if (refresh) api.logout(refresh).catch(() => {});
    clearTokens();
    setUser(null);
  };

  useEffect(() => {
    if (!user) return;
    const limit = 20 * 60 * 1000;
    let timer = window.setTimeout(logout, limit);
    const bump = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(logout, limit);
    };
    const events = ['mousedown', 'keydown', 'touchstart'] as const;
    events.forEach(name => window.addEventListener(name, bump));
    return () => {
      window.clearTimeout(timer);
      events.forEach(name => window.removeEventListener(name, bump));
    };
  }, [user]);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
