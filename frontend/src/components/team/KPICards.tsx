'use client';

import type { TeamStatsResponse } from '@/lib/types';

interface KPICardsProps {
  stats: TeamStatsResponse;
}

function KPICard({ label, value, sub, borderColor }: {
  label: string;
  value: string | number;
  sub?: string;
  borderColor: string;
}) {
  return (
    <div className={`bg-white rounded-xl shadow-sm border-l-4 ${borderColor} p-3 sm:p-4 min-w-0`}>
      <p className="text-[10px] sm:text-xs text-gray-500 font-medium uppercase tracking-wide">{label}</p>
      <p className="text-xl sm:text-2xl font-bold text-gray-900 mt-0.5 sm:mt-1">{value}</p>
      {sub && <p className="text-[10px] sm:text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

export function KPICards({ stats }: KPICardsProps) {
  const fullCount = Math.round(stats.enrichment_pct * stats.total_leads / 100);

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 sm:gap-4 mb-6">
      <KPICard
        label="Total Leads"
        value={stats.total_leads}
        borderColor="border-melonn-purple"
      />
      <KPICard
        label="Enrichment Completo"
        value={`${fullCount}/${stats.total_leads}`}
        sub={`${stats.enrichment_pct}%`}
        borderColor={stats.enrichment_pct >= 70 ? 'border-melonn-green' : stats.enrichment_pct >= 40 ? 'border-melonn-orange' : 'border-red-500'}
      />
      <KPICard
        label="Sin Actividad 30d"
        value={stats.leads_cold_30d}
        borderColor={stats.leads_cold_30d > 0 ? 'border-red-500' : 'border-melonn-green'}
      />
      <KPICard
        label="Leads Viejos >6m"
        value={stats.leads_stale_6m}
        borderColor={stats.leads_stale_6m > 0 ? 'border-red-500' : 'border-melonn-green'}
      />
      <KPICard
        label="Score Promedio"
        value={stats.avg_potential_score}
        borderColor={stats.avg_potential_score >= 60 ? 'border-melonn-green' : stats.avg_potential_score >= 40 ? 'border-blue-500' : 'border-melonn-orange'}
      />
    </div>
  );
}
