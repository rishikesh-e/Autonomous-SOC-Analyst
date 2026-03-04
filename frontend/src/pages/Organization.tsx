import React, { useState, useEffect } from 'react';
import {
  Building2,
  Users,
  UserPlus,
  Mail,
  Shield,
  Crown,
  UserCog,
  Eye,
  Trash2,
  Clock,
  RefreshCw,
  Copy,
  Check,
  AlertCircle,
  X,
  Link as LinkIcon,
  Send,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import {
  getCurrentOrganization,
  getOrganizationMembers,
  getPendingInvitations,
  inviteUser,
  removeMember,
  updateMemberRole,
} from '../utils/api';
import type {
  Organization,
  MemberWithUser,
  OrganizationInvitation,
  OrganizationRole,
} from '../types';
import { cn, formatRelativeTime } from '../utils/helpers';

const ROLE_LABELS: Record<OrganizationRole, string> = {
  OWNER: 'Owner',
  ADMIN: 'Admin',
  ANALYST: 'Analyst',
  VIEWER: 'Viewer',
};

const ROLE_COLORS: Record<OrganizationRole, string> = {
  OWNER: 'text-amber-400 bg-amber-400/10',
  ADMIN: 'text-purple-400 bg-purple-400/10',
  ANALYST: 'text-blue-400 bg-blue-400/10',
  VIEWER: 'text-gray-400 bg-gray-400/10',
};

const ROLE_ICONS: Record<OrganizationRole, React.ElementType> = {
  OWNER: Crown,
  ADMIN: Shield,
  ANALYST: UserCog,
  VIEWER: Eye,
};

// Invite Success Modal Component
function InviteSuccessModal({
  invitation,
  onClose,
}: {
  invitation: OrganizationInvitation;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const inviteLink = `${window.location.origin}/invite/${invitation.token}`;

  const copyLink = async () => {
    await navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-soc-card rounded-xl border border-soc-border max-w-lg w-full p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-soc-text-muted hover:text-white"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="text-center mb-6">
          <div className="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <Check className="w-8 h-8 text-emerald-400" />
          </div>
          <h2 className="text-xl font-semibold text-white">Invitation Sent!</h2>
          <p className="text-soc-text-muted mt-2">
            An invitation has been created for <span className="text-white">{invitation.email}</span>
          </p>
        </div>

        <div className="bg-soc-dark rounded-lg p-4 mb-4">
          <p className="text-sm text-soc-text-muted mb-2">Share this invite link:</p>
          <div className="flex items-center space-x-2">
            <div className="flex-1 bg-soc-darker rounded-lg p-3 font-mono text-sm text-soc-accent break-all">
              {inviteLink}
            </div>
            <button
              onClick={copyLink}
              className={cn(
                'p-3 rounded-lg transition-colors flex-shrink-0',
                copied
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'bg-soc-accent/20 text-soc-accent hover:bg-soc-accent/30'
              )}
            >
              {copied ? <Check className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
            </button>
          </div>
        </div>

        <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4 mb-6">
          <div className="flex items-start space-x-3">
            <Clock className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-amber-400 font-medium">Link expires in 7 days</p>
              <p className="text-sm text-amber-400/70 mt-1">
                The invitee must create an account or log in to accept the invitation.
              </p>
            </div>
          </div>
        </div>

        <div className="flex space-x-3">
          <button
            onClick={copyLink}
            className="flex-1 py-2.5 bg-soc-accent hover:bg-soc-accent/80 text-white rounded-lg font-medium flex items-center justify-center space-x-2"
          >
            <LinkIcon className="w-4 h-4" />
            <span>{copied ? 'Copied!' : 'Copy Link'}</span>
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-2.5 bg-soc-border hover:bg-soc-border/80 text-white rounded-lg font-medium"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

// Confirm Dialog Component
function ConfirmDialog({
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel,
  danger = false,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  danger?: boolean;
}) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-soc-card rounded-xl border border-soc-border max-w-md w-full p-6">
        <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
        <p className="text-soc-text-muted mb-6">{message}</p>
        <div className="flex space-x-3">
          <button
            onClick={onCancel}
            className="flex-1 py-2.5 bg-soc-border hover:bg-soc-border/80 text-white rounded-lg font-medium"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={cn(
              'flex-1 py-2.5 rounded-lg font-medium',
              danger
                ? 'bg-red-500 hover:bg-red-600 text-white'
                : 'bg-soc-accent hover:bg-soc-accent/80 text-white'
            )}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function OrganizationPage() {
  const { user } = useAuth();
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [members, setMembers] = useState<MemberWithUser[]>([]);
  const [invitations, setInvitations] = useState<OrganizationInvitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Invite form state
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<OrganizationRole>('ANALYST');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [newInvitation, setNewInvitation] = useState<OrganizationInvitation | null>(null);

  // Copy state
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  // Confirm dialog state
  const [confirmDialog, setConfirmDialog] = useState<{
    title: string;
    message: string;
    confirmLabel: string;
    onConfirm: () => void;
    danger?: boolean;
  } | null>(null);

  const isOwnerOrAdmin = user?.org_role === 'OWNER' || user?.org_role === 'ADMIN';
  const isOwner = user?.org_role === 'OWNER';

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [orgData, membersData] = await Promise.all([
        getCurrentOrganization(),
        getOrganizationMembers(),
      ]);

      setOrganization(orgData);
      setMembers(membersData);

      if (isOwnerOrAdmin) {
        const invitationsData = await getPendingInvitations();
        setInvitations(invitationsData);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load organization data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    try {
      setInviteLoading(true);
      setInviteError(null);

      const invitation = await inviteUser(inviteEmail.trim(), inviteRole);
      setInvitations((prev) => [...prev, invitation]);
      setNewInvitation(invitation);
      setInviteEmail('');
    } catch (err: any) {
      setInviteError(err.response?.data?.detail || 'Failed to send invitation');
    } finally {
      setInviteLoading(false);
    }
  };

  const handleRemoveMember = async (userId: string, username: string) => {
    setConfirmDialog({
      title: 'Remove Member',
      message: `Are you sure you want to remove ${username} from the organization? They will lose access to all organization data.`,
      confirmLabel: 'Remove',
      danger: true,
      onConfirm: async () => {
        try {
          await removeMember(userId);
          setMembers((prev) => prev.filter((m) => m.user_id !== userId));
        } catch (err: any) {
          alert(err.response?.data?.detail || 'Failed to remove member');
        }
        setConfirmDialog(null);
      },
    });
  };

  const handleRoleChange = async (userId: string, newRole: OrganizationRole, username: string) => {
    const currentMember = members.find((m) => m.user_id === userId);
    if (!currentMember || currentMember.role === newRole) return;

    setConfirmDialog({
      title: 'Change Role',
      message: `Change ${username}'s role from ${ROLE_LABELS[currentMember.role]} to ${ROLE_LABELS[newRole]}?`,
      confirmLabel: 'Change Role',
      onConfirm: async () => {
        try {
          const updated = await updateMemberRole(userId, newRole);
          setMembers((prev) =>
            prev.map((m) => (m.user_id === userId ? { ...m, role: updated.role } : m))
          );
        } catch (err: any) {
          alert(err.response?.data?.detail || 'Failed to update role');
        }
        setConfirmDialog(null);
      },
    });
  };

  const copyInviteLink = async (token: string) => {
    const link = `${window.location.origin}/invite/${token}`;
    await navigator.clipboard.writeText(link);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 2000);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-soc-accent animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
        <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <p className="text-red-400 mb-2">{error}</p>
        <p className="text-soc-text-muted text-sm mb-4">
          Make sure you're logged in and belong to an organization.
        </p>
        <button
          onClick={fetchData}
          className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 rounded-lg text-red-400 transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Modals */}
      {newInvitation && (
        <InviteSuccessModal
          invitation={newInvitation}
          onClose={() => setNewInvitation(null)}
        />
      )}

      {confirmDialog && (
        <ConfirmDialog
          {...confirmDialog}
          onCancel={() => setConfirmDialog(null)}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Organization</h1>
          <p className="text-soc-text-muted mt-1">
            Manage your organization and team members
          </p>
        </div>
        <button
          onClick={fetchData}
          className="p-2 text-soc-text-muted hover:text-white hover:bg-soc-card rounded-lg transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>

      {/* Organization Info */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-4">
            <div className="w-16 h-16 bg-gradient-to-br from-soc-accent to-soc-accent/50 rounded-xl flex items-center justify-center">
              <Building2 className="w-8 h-8 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold">{organization?.name}</h2>
              <p className="text-soc-text-muted text-sm mt-1">
                <span className="font-mono bg-soc-dark px-2 py-0.5 rounded">@{organization?.slug}</span>
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className="flex items-center space-x-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-white">{members.length}</p>
                <p className="text-xs text-soc-text-muted">Members</p>
              </div>
              {invitations.length > 0 && (
                <div className="text-center">
                  <p className="text-2xl font-bold text-amber-400">{invitations.length}</p>
                  <p className="text-xs text-soc-text-muted">Pending</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Invite Member - Only for Admin/Owner */}
      {isOwnerOrAdmin && (
        <div className="bg-soc-card rounded-xl border border-soc-border p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
            <UserPlus className="w-5 h-5 text-soc-accent" />
            <span>Invite Team Member</span>
          </h3>

          <form onSubmit={handleInvite} className="space-y-4">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1">
                <label className="block text-sm text-soc-text-muted mb-2">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-soc-text-muted" />
                  <input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="colleague@example.com"
                    className="w-full pl-10 pr-4 py-3 bg-soc-dark border border-soc-border rounded-lg focus:outline-none focus:border-soc-accent focus:ring-1 focus:ring-soc-accent"
                    required
                  />
                </div>
              </div>

              <div className="w-full md:w-48">
                <label className="block text-sm text-soc-text-muted mb-2">Role</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as OrganizationRole)}
                  className="w-full px-4 py-3 bg-soc-dark border border-soc-border rounded-lg focus:outline-none focus:border-soc-accent appearance-none cursor-pointer"
                >
                  <option value="VIEWER">Viewer - Read only</option>
                  <option value="ANALYST">Analyst - Full access</option>
                  {isOwner && <option value="ADMIN">Admin - Manage team</option>}
                </select>
              </div>

              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={inviteLoading || !inviteEmail.trim()}
                  className={cn(
                    'px-6 py-3 rounded-lg font-medium transition-all flex items-center space-x-2',
                    'bg-soc-accent hover:bg-soc-accent/80 text-white',
                    'disabled:opacity-50 disabled:cursor-not-allowed',
                    'hover:shadow-lg hover:shadow-soc-accent/20'
                  )}
                >
                  {inviteLoading ? (
                    <RefreshCw className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <Send className="w-5 h-5" />
                      <span>Send Invite</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {inviteError && (
              <div className="flex items-center space-x-2 text-red-400 text-sm bg-red-500/10 p-3 rounded-lg">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{inviteError}</span>
              </div>
            )}
          </form>
        </div>
      )}

      {/* Members List */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
          <Users className="w-5 h-5 text-soc-text-muted" />
          <span>Team Members</span>
          <span className="ml-2 px-2.5 py-0.5 bg-soc-dark rounded-full text-sm text-soc-text-muted">
            {members.length}
          </span>
        </h3>

        <div className="space-y-3">
          {members.map((member) => {
            const RoleIcon = ROLE_ICONS[member.role];
            const isCurrentUser = member.user_id === user?.id;
            const canModify = isOwnerOrAdmin && !isCurrentUser && member.role !== 'OWNER';
            const canChangeRole = isOwner && !isCurrentUser;

            return (
              <div
                key={member.id}
                className={cn(
                  'flex items-center justify-between p-4 rounded-lg transition-colors',
                  isCurrentUser ? 'bg-soc-accent/5 border border-soc-accent/20' : 'bg-soc-dark/50 hover:bg-soc-dark'
                )}
              >
                <div className="flex items-center space-x-4">
                  <div className={cn(
                    'w-12 h-12 rounded-full flex items-center justify-center font-semibold text-lg',
                    isCurrentUser ? 'bg-soc-accent/20 text-soc-accent' : 'bg-soc-border text-soc-text-muted'
                  )}>
                    {member.username.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <p className="font-medium flex items-center space-x-2">
                      <span>{member.username}</span>
                      {isCurrentUser && (
                        <span className="text-xs bg-soc-accent/20 text-soc-accent px-2 py-0.5 rounded-full">
                          You
                        </span>
                      )}
                    </p>
                    <p className="text-sm text-soc-text-muted">
                      {member.email}
                    </p>
                    <p className="text-xs text-soc-text-muted mt-1">
                      Joined {formatRelativeTime(member.joined_at)}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  {canChangeRole ? (
                    <select
                      value={member.role}
                      onChange={(e) =>
                        handleRoleChange(member.user_id, e.target.value as OrganizationRole, member.username)
                      }
                      className={cn(
                        'px-4 py-2 rounded-lg text-sm font-medium border-0',
                        'bg-soc-dark focus:outline-none focus:ring-2 focus:ring-soc-accent cursor-pointer'
                      )}
                    >
                      <option value="VIEWER">Viewer</option>
                      <option value="ANALYST">Analyst</option>
                      <option value="ADMIN">Admin</option>
                      {isOwner && <option value="OWNER">Owner</option>}
                    </select>
                  ) : (
                    <span
                      className={cn(
                        'px-4 py-2 rounded-lg text-sm font-medium flex items-center space-x-2',
                        ROLE_COLORS[member.role]
                      )}
                    >
                      <RoleIcon className="w-4 h-4" />
                      <span>{ROLE_LABELS[member.role]}</span>
                    </span>
                  )}

                  {canModify && (
                    <button
                      onClick={() => handleRemoveMember(member.user_id, member.username)}
                      className="p-2 text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                      title="Remove member"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Pending Invitations - Only for Admin/Owner */}
      {isOwnerOrAdmin && invitations.length > 0 && (
        <div className="bg-soc-card rounded-xl border border-soc-border p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center space-x-2">
            <Clock className="w-5 h-5 text-amber-400" />
            <span>Pending Invitations</span>
            <span className="ml-2 px-2.5 py-0.5 bg-amber-400/20 text-amber-400 rounded-full text-sm font-medium">
              {invitations.length}
            </span>
          </h3>

          <div className="space-y-3">
            {invitations.map((invitation) => {
              const RoleIcon = ROLE_ICONS[invitation.role];
              const isExpired = new Date(invitation.expires_at) < new Date();

              return (
                <div
                  key={invitation.id}
                  className={cn(
                    'flex items-center justify-between p-4 bg-soc-dark/50 rounded-lg',
                    isExpired && 'opacity-50'
                  )}
                >
                  <div className="flex items-center space-x-4">
                    <div className="w-12 h-12 bg-amber-400/20 rounded-full flex items-center justify-center">
                      <Mail className="w-6 h-6 text-amber-400" />
                    </div>
                    <div>
                      <p className="font-medium">{invitation.email}</p>
                      <p className="text-sm text-soc-text-muted">
                        {isExpired ? (
                          <span className="text-red-400">Expired</span>
                        ) : (
                          <>Expires {formatRelativeTime(invitation.expires_at)}</>
                        )}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <span
                      className={cn(
                        'px-3 py-1.5 rounded-lg text-sm font-medium flex items-center space-x-2',
                        ROLE_COLORS[invitation.role]
                      )}
                    >
                      <RoleIcon className="w-4 h-4" />
                      <span>{ROLE_LABELS[invitation.role]}</span>
                    </span>

                    {!isExpired && (
                      <button
                        onClick={() => copyInviteLink(invitation.token)}
                        className={cn(
                          'px-4 py-2 rounded-lg text-sm font-medium flex items-center space-x-2 transition-colors',
                          copiedToken === invitation.token
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : 'bg-soc-border hover:bg-soc-border/80 text-white'
                        )}
                      >
                        {copiedToken === invitation.token ? (
                          <>
                            <Check className="w-4 h-4" />
                            <span>Copied!</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-4 h-4" />
                            <span>Copy Link</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Role Descriptions */}
      <div className="bg-soc-card rounded-xl border border-soc-border p-6">
        <h3 className="text-lg font-semibold mb-4">Role Permissions</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <RoleDescription
            role="OWNER"
            description="Full access. Can manage all members, transfer ownership, and delete the organization."
          />
          <RoleDescription
            role="ADMIN"
            description="Can invite/remove members (except owners) and manage organization settings."
          />
          <RoleDescription
            role="ANALYST"
            description="Full access to incidents, can approve/deny actions, and view all security data."
          />
          <RoleDescription
            role="VIEWER"
            description="Read-only access to dashboard, incidents, and logs. Cannot take actions."
          />
        </div>
      </div>

      {/* Help Section */}
      <div className="bg-soc-dark/30 rounded-xl border border-soc-border/50 p-6">
        <h3 className="font-semibold mb-3 flex items-center space-x-2">
          <AlertCircle className="w-5 h-5 text-soc-text-muted" />
          <span>How Invitations Work</span>
        </h3>
        <ol className="list-decimal list-inside space-y-2 text-sm text-soc-text-muted">
          <li>Enter the email address of the person you want to invite</li>
          <li>Select their role (you can change it later)</li>
          <li>Click "Send Invite" - a unique invite link will be generated</li>
          <li>Share the link with your team member</li>
          <li>They click the link, log in (or create an account), and join your organization</li>
        </ol>
      </div>
    </div>
  );
}

function RoleDescription({ role, description }: { role: OrganizationRole; description: string }) {
  const Icon = ROLE_ICONS[role];
  return (
    <div className="flex items-start space-x-3 p-4 bg-soc-dark/50 rounded-lg">
      <div className={cn('p-2 rounded-lg', ROLE_COLORS[role])}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="font-medium">{ROLE_LABELS[role]}</p>
        <p className="text-sm text-soc-text-muted mt-1">{description}</p>
      </div>
    </div>
  );
}

export default OrganizationPage;
