import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Shield, Eye, EyeOff, AlertCircle, Check } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

type AuthMode = 'login' | 'signup';

export function AuthPage() {
  const [mode, setMode] = useState<AuthMode>('login');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login, register, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Redirect if already authenticated
  React.useEffect(() => {
    if (isAuthenticated) {
      const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, location]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      if (mode === 'login') {
        await login({ email, password });
      } else {
        await register({ email, username, password });
      }

      // Navigate to the intended destination
      const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';
      navigate(from, { replace: true });
    } catch (err: unknown) {
      const errorMessage = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'An error occurred. Please try again.';
      setError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const features = [
    'AI-Powered Threat Detection',
    'Real-time Security Analysis',
    'Automated Incident Response',
    'LangGraph Agent Workflows',
  ];

  return (
    <div className="min-h-screen bg-soc-darker flex">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-soc-dark via-soc-darker to-soc-card p-12 flex-col justify-center items-center relative overflow-hidden">
        {/* Background decoration */}
        <div className="absolute inset-0 opacity-5">
          <div className="absolute top-20 left-20 w-64 h-64 bg-soc-accent rounded-full blur-3xl" />
          <div className="absolute bottom-20 right-20 w-96 h-96 bg-blue-500 rounded-full blur-3xl" />
        </div>

        <div className="relative z-10 text-center max-w-md">
          {/* Shield Icon */}
          <div className="mb-8 flex justify-center">
            <div className="p-6 bg-soc-accent/10 rounded-2xl border border-soc-accent/20">
              <Shield className="w-20 h-20 text-soc-accent" />
            </div>
          </div>

          {/* Title */}
          <h1 className="text-4xl font-bold text-white mb-4">
            SOC Analyst
          </h1>
          <p className="text-lg text-soc-text-muted mb-10">
            Autonomous Security Operations Center
          </p>

          {/* Features */}
          <ul className="space-y-4 text-left">
            {features.map((feature, index) => (
              <li key={index} className="flex items-center text-soc-text">
                <div className="mr-3 p-1 bg-soc-accent/10 rounded-full">
                  <Check className="w-4 h-4 text-soc-accent" />
                </div>
                {feature}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Right Panel - Auth Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden mb-8 text-center">
            <div className="inline-flex p-4 bg-soc-accent/10 rounded-xl mb-4">
              <Shield className="w-12 h-12 text-soc-accent" />
            </div>
            <h1 className="text-2xl font-bold text-white">SOC Analyst</h1>
          </div>

          {/* Form Header */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-white">
              {mode === 'login' ? 'Welcome Back' : 'Create Account'}
            </h2>
            <p className="text-soc-text-muted mt-2">
              {mode === 'login'
                ? 'Sign in to access your security dashboard'
                : 'Set up your account to get started'}
            </p>
          </div>

          {/* Error Alert */}
          {error && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg flex items-start">
              <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 mr-3 flex-shrink-0" />
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          {/* Auth Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Email Input */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-soc-text mb-2">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-3 bg-soc-card border border-soc-border rounded-lg text-white placeholder-soc-text-muted focus:outline-none focus:ring-2 focus:ring-soc-accent focus:border-transparent transition-all"
                placeholder="you@example.com"
              />
            </div>

            {/* Username Input (Signup only) */}
            {mode === 'signup' && (
              <div>
                <label htmlFor="username" className="block text-sm font-medium text-soc-text mb-2">
                  Username
                </label>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  minLength={3}
                  maxLength={50}
                  className="w-full px-4 py-3 bg-soc-card border border-soc-border rounded-lg text-white placeholder-soc-text-muted focus:outline-none focus:ring-2 focus:ring-soc-accent focus:border-transparent transition-all"
                  placeholder="johndoe"
                />
              </div>
            )}

            {/* Password Input */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-soc-text mb-2">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  className="w-full px-4 py-3 bg-soc-card border border-soc-border rounded-lg text-white placeholder-soc-text-muted focus:outline-none focus:ring-2 focus:ring-soc-accent focus:border-transparent transition-all pr-12"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-soc-text-muted hover:text-soc-text transition-colors"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              {mode === 'signup' && (
                <p className="mt-2 text-xs text-soc-text-muted">
                  Password must be at least 8 characters
                </p>
              )}
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3 px-4 bg-soc-accent hover:bg-soc-accent/90 text-white font-semibold rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
            >
              {isSubmitting ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                mode === 'login' ? 'Sign In' : 'Create Account'
              )}
            </button>
          </form>

          {/* Toggle Mode */}
          <p className="mt-8 text-center text-soc-text-muted">
            {mode === 'login' ? (
              <>
                Don't have an account?{' '}
                <button
                  onClick={() => { setMode('signup'); setError(null); }}
                  className="text-soc-accent hover:underline font-medium"
                >
                  Sign Up
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button
                  onClick={() => { setMode('login'); setError(null); }}
                  className="text-soc-accent hover:underline font-medium"
                >
                  Sign In
                </button>
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}

export default AuthPage;
