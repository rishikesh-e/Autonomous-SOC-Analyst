import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { User, AuthToken, LoginCredentials, RegisterCredentials } from '../types';
import api from '../utils/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (credentials: RegisterCredentials) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = 'soc_auth_token';
const USER_KEY = 'soc_auth_user';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Initialize auth state from localStorage
  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    const storedUser = localStorage.getItem(USER_KEY);

    if (storedToken && storedUser) {
      setToken(storedToken);
      setUser(JSON.parse(storedUser));

      // Verify token is still valid
      api.get('/auth/me')
        .then(response => {
          setUser(response.data);
          localStorage.setItem(USER_KEY, JSON.stringify(response.data));
        })
        .catch(() => {
          // Token expired or invalid
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(USER_KEY);
          setToken(null);
          setUser(null);
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const response = await api.post<AuthToken>('/auth/login', credentials);
    const { access_token } = response.data;

    // Store token
    localStorage.setItem(TOKEN_KEY, access_token);
    setToken(access_token);

    // Fetch user info
    const userResponse = await api.get<User>('/auth/me');
    localStorage.setItem(USER_KEY, JSON.stringify(userResponse.data));
    setUser(userResponse.data);
  }, []);

  const register = useCallback(async (credentials: RegisterCredentials) => {
    // Register the user
    await api.post<User>('/auth/register', credentials);

    // Auto-login after registration
    await login({ email: credentials.email, password: credentials.password });
  }, [login]);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated: !!token && !!user,
    isLoading,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export default AuthContext;
