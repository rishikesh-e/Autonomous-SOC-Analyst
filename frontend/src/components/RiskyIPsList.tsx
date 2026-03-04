import React from 'react';
import { Globe, AlertTriangle, Ban } from 'lucide-react';
import type { RiskyIP } from '../types';
import { cn } from '../utils/helpers';

interface RiskyIPsListProps {
  ips: RiskyIP[];
  title?: string;
  onBlock?: (ip: string) => void;
}

export function RiskyIPsList({
  ips,
  title = 'Top Risky IPs',
  onBlock,
}: RiskyIPsListProps) {
  const maxCount = Math.max(...ips.map((ip) => ip.count), 1);

  return (
    <div className="bg-soc-card rounded-xl border border-soc-border p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <Globe className="w-5 h-5 text-soc-text-muted" />
      </div>

      {ips.length === 0 ? (
        <div className="text-center py-8 text-soc-text-muted">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
          <p>No risky IPs detected</p>
        </div>
      ) : (
        <div className="space-y-2">
          {ips.map((ip, index) => (
            <div
              key={ip.ip}
              className="flex items-center justify-between p-3 bg-soc-dark/50 rounded-lg hover:bg-soc-dark transition-colors"
            >
              <div className="flex items-center space-x-3">
                <span
                  className={cn(
                    'w-6 h-6 rounded flex items-center justify-center text-xs font-semibold',
                    index === 0
                      ? 'bg-red-600/20 text-red-400'
                      : index === 1
                        ? 'bg-orange-600/20 text-orange-400'
                        : index === 2
                          ? 'bg-amber-600/20 text-amber-400'
                          : 'bg-soc-border text-soc-text-muted'
                  )}
                >
                  {index + 1}
                </span>
                <span className="font-mono text-sm text-soc-text">{ip.ip}</span>
              </div>

              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <div className="w-20 bg-soc-dark rounded-full h-1.5">
                    <div
                      className={cn(
                        'h-1.5 rounded-full',
                        index === 0
                          ? 'bg-red-500'
                          : index === 1
                            ? 'bg-orange-500'
                            : 'bg-amber-500'
                      )}
                      style={{ width: `${(ip.count / maxCount) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-soc-text-muted w-10 text-right">
                    {ip.count}
                  </span>
                </div>

                {onBlock && (
                  <button
                    onClick={() => onBlock(ip.ip)}
                    className="p-1.5 hover:bg-red-600/20 rounded transition-colors"
                    title="Block IP"
                  >
                    <Ban className="w-4 h-4 text-red-400" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default RiskyIPsList;
