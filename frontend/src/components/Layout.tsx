import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Shield,
  LayoutDashboard,
  AlertTriangle,
  Activity,
  Settings,
  Ban,
  FileText,
  Brain,
  LogOut,
  User,
  Building2,
} from 'lucide-react';
import { cn } from '../utils/helpers';
import { useAuth } from '../contexts/AuthContext';

interface LayoutProps {
  children: React.ReactNode;
}

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/incidents', icon: AlertTriangle, label: 'Incidents' },
  { path: '/detection', icon: Activity, label: 'Detection' },
  { path: '/actions', icon: Ban, label: 'Actions' },
  { path: '/logs', icon: FileText, label: 'Agent Logs' },
  { path: '/ml-metrics', icon: Brain, label: 'ML Metrics' },
  { path: '/organization', icon: Building2, label: 'Organization' },
  { path: '/settings', icon: Settings, label: 'Settings' },
];

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-soc-darker text-soc-text flex">
      {/* Sidebar */}
      <aside className="w-64 bg-soc-dark border-r border-soc-border flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-soc-border">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-soc-accent/10 rounded-lg">
              <Shield className="w-6 h-6 text-soc-accent" />
            </div>
            <div>
              <h1 className="font-semibold text-lg text-white">SOC Analyst</h1>
              <p className="text-xs text-soc-text-muted">Security Operations</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <ul className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    className={cn(
                      'flex items-center space-x-3 px-4 py-2.5 rounded-lg transition-all duration-200',
                      isActive
                        ? 'bg-soc-accent/15 text-soc-accent border-l-2 border-soc-accent'
                        : 'text-soc-text-muted hover:bg-soc-card hover:text-soc-text'
                    )}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="font-medium">{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* User Info & Logout */}
        <div className="p-4 border-t border-soc-border">
          {user && (
            <div className="mb-4 p-3 bg-soc-card rounded-lg">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-soc-accent/20 rounded-full flex items-center justify-center text-soc-accent font-semibold">
                  {user.username.slice(0, 2).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">
                    {user.username}
                  </p>
                  <p className="text-xs text-soc-text-muted truncate">
                    {user.email}
                  </p>
                  {user.org_role && (
                    <p className="text-xs text-soc-accent truncate mt-0.5">
                      {user.org_role}
                    </p>
                  )}
                </div>
              </div>
              <button
                onClick={logout}
                className="mt-3 w-full flex items-center justify-center space-x-2 px-3 py-2 text-sm text-soc-text-muted hover:text-white hover:bg-soc-border rounded-lg transition-colors"
              >
                <LogOut className="w-4 h-4" />
                <span>Sign Out</span>
              </button>
            </div>
          )}
          <p className="text-xs text-soc-text-muted text-center">
            Powered by LangGraph + Groq
          </p>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}

export default Layout;
