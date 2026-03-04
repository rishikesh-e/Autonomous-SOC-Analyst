import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { format, formatDistanceToNow } from 'date-fns';
import type { SeverityLevel, IncidentStatus, AttackType } from '../types';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  return format(new Date(date), 'MMM dd, yyyy HH:mm:ss');
}

export function formatRelativeTime(date: string | Date): string {
  return formatDistanceToNow(new Date(date), { addSuffix: true });
}

export function getSeverityColor(severity: SeverityLevel): string {
  const colors: Record<SeverityLevel, string> = {
    LOW: 'bg-sky-600/20 text-sky-400',
    MEDIUM: 'bg-amber-600/20 text-amber-400',
    HIGH: 'bg-orange-600/20 text-orange-400',
    CRITICAL: 'bg-red-600/20 text-red-400',
  };
  return colors[severity] || 'bg-gray-600/20 text-gray-400';
}

export function getSeverityTextColor(severity: SeverityLevel): string {
  const colors: Record<SeverityLevel, string> = {
    LOW: 'text-sky-400',
    MEDIUM: 'text-amber-400',
    HIGH: 'text-orange-400',
    CRITICAL: 'text-red-400',
  };
  return colors[severity] || 'text-gray-400';
}

export function getStatusColor(status: IncidentStatus): string {
  const colors: Record<IncidentStatus, string> = {
    DETECTED: 'bg-blue-600/20 text-blue-400',
    ANALYZING: 'bg-violet-600/20 text-violet-400',
    PENDING_APPROVAL: 'bg-amber-600/20 text-amber-400',
    APPROVED: 'bg-emerald-600/20 text-emerald-400',
    DENIED: 'bg-red-600/20 text-red-400',
    EXECUTED: 'bg-teal-600/20 text-teal-400',
    RESOLVED: 'bg-slate-600/20 text-slate-400',
  };
  return colors[status] || 'bg-gray-600/20 text-gray-400';
}

export function getStatusTextColor(status: IncidentStatus): string {
  const colors: Record<IncidentStatus, string> = {
    DETECTED: 'text-blue-400',
    ANALYZING: 'text-violet-400',
    PENDING_APPROVAL: 'text-amber-400',
    APPROVED: 'text-emerald-400',
    DENIED: 'text-red-400',
    EXECUTED: 'text-teal-400',
    RESOLVED: 'text-slate-400',
  };
  return colors[status] || 'text-gray-400';
}

export function getAttackTypeLabel(type: AttackType): string {
  const labels: Record<AttackType, string> = {
    BRUTE_FORCE: 'Brute Force',
    RECONNAISSANCE: 'Reconnaissance',
    DDOS: 'DDoS Attack',
    INJECTION: 'Injection Attack',
    ANOMALOUS_TRAFFIC: 'Anomalous Traffic',
    SUSPICIOUS_IP: 'Suspicious IP',
    AUTH_FAILURE: 'Auth Failure',
    UNKNOWN: 'Unknown',
  };
  return labels[type] || type;
}

export function formatPercentage(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatNumber(value: number): string {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`;
  }
  return value.toString();
}
