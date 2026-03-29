'use client';

import { useState } from 'react';
import type { TeamAlert } from '@/lib/types';

interface AlertsPanelProps {
  alerts: TeamAlert[];
}

const SEVERITY_STYLES: Record<string, { border: string; bg: string; icon: string }> = {
  red: { border: 'border-l-4 border-red-500', bg: 'bg-red-50', icon: '!' },
  yellow: { border: 'border-l-4 border-melonn-orange', bg: 'bg-orange-50', icon: '~' },
  green: { border: 'border-l-4 border-melonn-green', bg: 'bg-green-50', icon: '' },
};

function AlertCard({ alert }: { alert: TeamAlert }) {
  const [expanded, setExpanded] = useState(false);
  const style = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.yellow;

  return (
    <div className={`${style.border} ${style.bg} rounded-r-lg p-3 cursor-pointer`}
         onClick={() => setExpanded(!expanded)}>
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold text-white ${
              alert.severity === 'red' ? 'bg-red-500' : 'bg-melonn-orange'
            }`}>
              {alert.count}
            </span>
            <h4 className="text-sm font-semibold text-gray-800">{alert.title}</h4>
          </div>
          <p className="text-xs text-gray-600 mt-1">{alert.description}</p>
        </div>
        {alert.affected_domains.length > 0 && (
          <span className="text-gray-400 text-xs ml-2 shrink-0">
            {expanded ? 'v' : '>'}
          </span>
        )}
      </div>
      {expanded && alert.affected_domains.length > 0 && (
        <div className="mt-2 pt-2 border-t border-gray-200/50">
          <p className="text-xs text-gray-500 mb-1">Leads afectados:</p>
          <div className="flex flex-wrap gap-1">
            {alert.affected_domains.map((d) => (
              <span key={d} className="inline-block px-2 py-0.5 bg-white rounded text-xs text-gray-600 border border-gray-200">
                {d}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function AlertsPanel({ alerts }: AlertsPanelProps) {
  if (alerts.length === 0) {
    return (
      <div className="border-l-4 border-melonn-green bg-green-50 rounded-r-lg p-4">
        <p className="text-sm font-semibold text-melonn-green">Todo en orden</p>
        <p className="text-xs text-gray-500 mt-0.5">No hay alertas activas en tu pipeline.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Alertas</h3>
      {alerts.map((alert) => (
        <AlertCard key={alert.alert_type} alert={alert} />
      ))}
    </div>
  );
}
