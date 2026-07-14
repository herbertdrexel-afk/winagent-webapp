import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, token, type AuthUser } from "../api";

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token.get()) {
      api.auth.me()
        .then(setUser)
        .catch(() => token.clear())
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  async function login(username: string, password: string) {
    const res = await api.auth.login(username, password);
    token.set(res.access_token);
    setUser(res.user);
  }

  function logout() {
    token.clear();
    setUser(null);
  }

  async function refreshUser() {
    try {
      const updated = await api.auth.me();
      setUser(updated);
    } catch {}
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
