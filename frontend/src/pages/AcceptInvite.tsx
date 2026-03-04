import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Shield, Check, AlertCircle, RefreshCw, UserPlus } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { acceptInvitation } from '../utils/api';
import { cn } from '../utils/helpers';

export function AcceptInvite() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    // If user is not authenticated, redirect to login with return URL
    if (!authLoading && !isAuthenticated) {
      const returnUrl = encodeURIComponent(`/invite/${token}`);
      navigate(`/login?redirect=${returnUrl}`);
    }
  }, [authLoading, isAuthenticated, token, navigate]);

  const handleAccept = async () => {
    if (!token) return;

    try {
      setLoading(true);
      setError(null);

      await acceptInvitation(token);
      setSuccess(true);

      // Redirect to organization page after a delay
      setTimeout(() => {
        // Force page reload to refresh user context with new org
        window.location.href = '/organization';
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to accept invitation');
    } finally {
      setLoading(false);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-soc-darker flex items-center justify-center">
        <RefreshCw className="w-8 h-8 text-soc-accent animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-soc-darker flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center p-3 bg-soc-accent/10 rounded-xl mb-4">
            <Shield className="w-10 h-10 text-soc-accent" />
          </div>
          <h1 className="text-2xl font-bold text-white">SOC Analyst</h1>
          <p className="text-soc-text-muted mt-1">Security Operations Center</p>
        </div>

        {/* Invitation Card */}
        <div className="bg-soc-card rounded-xl border border-soc-border p-8">
          {success ? (
            <div className="text-center">
              <div className="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Check className="w-8 h-8 text-emerald-400" />
              </div>
              <h2 className="text-xl font-semibold text-white mb-2">
                Welcome to the team!
              </h2>
              <p className="text-soc-text-muted">
                You've successfully joined the organization. Redirecting...
              </p>
            </div>
          ) : (
            <>
              <div className="text-center mb-6">
                <div className="w-16 h-16 bg-soc-accent/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  <UserPlus className="w-8 h-8 text-soc-accent" />
                </div>
                <h2 className="text-xl font-semibold text-white mb-2">
                  You've been invited!
                </h2>
                <p className="text-soc-text-muted">
                  You're signed in as <span className="text-white">{user?.email}</span>
                </p>
              </div>

              {error && (
                <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center space-x-3">
                  <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
              )}

              {user?.org_id && (
                <div className="mb-6 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-center space-x-3">
                  <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0" />
                  <p className="text-amber-400 text-sm">
                    You already belong to an organization. Accepting this invitation will transfer you to the new organization.
                  </p>
                </div>
              )}

              <button
                onClick={handleAccept}
                disabled={loading}
                className={cn(
                  'w-full py-3 rounded-lg font-medium transition-colors',
                  'bg-soc-accent hover:bg-soc-accent/80 text-white',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  'flex items-center justify-center space-x-2'
                )}
              >
                {loading ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <Check className="w-5 h-5" />
                    <span>Accept Invitation</span>
                  </>
                )}
              </button>

              <button
                onClick={() => navigate('/')}
                className="w-full mt-3 py-3 rounded-lg font-medium text-soc-text-muted hover:text-white transition-colors"
              >
                Decline & Go to Dashboard
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default AcceptInvite;
