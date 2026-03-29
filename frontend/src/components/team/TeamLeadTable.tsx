'use client';

import type { LeadListItem } from '@/lib/types';
import { PotentialTierBadge } from '@/components/PotentialTierBadge';

interface TeamLeadTableProps {
  leads: LeadListItem[];
  sortBy: string;
  onSortChange: (field: string) => void;
  onEnrich: (domain: string, geography: string) => void;
}

function formatRelativeDate(dateStr: string | null | undefined): { text: string; stale: boolean; cold: boolean } {
  if (!dateStr) return { text: '--', stale: false, cold: false };
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const days = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
    if (days === 0) return { text: 'hoy', stale: false, cold: false };
    if (days === 1) return { text: 'ayer', stale: false, cold: false };
    if (days < 30) return { text: `hace ${days}d`, stale: false, cold: false };
    if (days < 180) return { text: `hace ${days}d`, stale: false, cold: true };
    return { text: `hace ${days}d`, stale: true, cold: true };
  } catch {
    return { text: '--', stale: false, cold: false };
  }
}

function formatNumber(n: number | null | undefined): string {
  if (n == null) return '--';
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

function EnrichmentBadge({ type }: { type: string | null | undefined }) {
  if (!type) return <span className="text-gray-400 text-xs">--</span>;
  const isFull = type === 'full';
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
      isFull ? 'bg-melonn-green-50 text-melonn-green' : 'bg-gray-100 text-gray-500'
    }`}>
      {isFull ? 'Full' : 'Lite'}
    </span>
  );
}

function StageBadge({ stage }: { stage: string | null | undefined }) {
  if (!stage) return <span className="text-gray-400 text-xs">--</span>;
  return (
    <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-600 whitespace-nowrap">
      {stage}
    </span>
  );
}

const SORT_OPTIONS = [
  { value: 'overall_potential_score', label: 'Potencial' },
  { value: 'ig_followers', label: 'IG Seguidores' },
  { value: 'hs_last_activity_date', label: 'Ult. Actividad' },
  { value: 'hs_lead_created_at', label: 'Creado' },
  { value: 'updated_at', label: 'Actualizado' },
];

// --- Mobile card view ---
function LeadCard({ lead, onEnrich }: { lead: LeadListItem; onEnrich: (domain: string, geography: string) => void }) {
  const activity = formatRelativeDate(lead.hs_last_activity_date);
  const created = formatRelativeDate(lead.hs_lead_created_at);

  return (
    <div className="bg-white border border-gray-100 rounded-lg p-3 space-y-2">
      {/* Row 1: Name + Potential */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-gray-900 text-sm truncate">
            {lead.company_name || lead.domain}
          </p>
          {lead.domain && (
            <a
              href={`https://${lead.domain}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-melonn-purple hover:underline"
            >
              {lead.domain}
            </a>
          )}
        </div>
        <PotentialTierBadge tier={lead.potential_tier} />
      </div>

      {/* Row 2: Metrics grid */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <span className="text-gray-400">IG</span>
          <p className="text-gray-700 font-medium">{formatNumber(lead.ig_followers)}</p>
        </div>
        <div>
          <span className="text-gray-400">Stage</span>
          <div className="mt-0.5"><StageBadge stage={lead.hs_lead_stage} /></div>
        </div>
        <div>
          <span className="text-gray-400">Enrich</span>
          <div className="mt-0.5"><EnrichmentBadge type={lead.enrichment_type} /></div>
        </div>
      </div>

      {/* Row 3: Dates + Enrich button */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex gap-3">
          <span className={activity.cold ? (activity.stale ? 'text-red-500 font-semibold' : 'text-melonn-orange font-medium') : 'text-gray-500'}>
            Act: {activity.text}
          </span>
          <span className={created.stale ? 'text-red-500 font-semibold' : 'text-gray-400'}>
            Creado: {created.text}
          </span>
        </div>
        {lead.enrichment_type !== 'full' && lead.domain && (
          <button
            onClick={() => onEnrich(lead.domain!, lead.geography || 'COL')}
            className="px-3 py-1 rounded-md bg-melonn-purple text-white text-xs font-medium
                       hover:bg-melonn-purple/90 transition-colors whitespace-nowrap"
          >
            Enrich
          </button>
        )}
      </div>
    </div>
  );
}

export function TeamLeadTable({ leads, sortBy, onSortChange, onEnrich }: TeamLeadTableProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          Mis Leads ({leads.length})
        </h3>
        <select
          value={sortBy}
          onChange={(e) => onSortChange(e.target.value)}
          className="text-xs border border-gray-200 rounded px-2 py-1 bg-white text-gray-600"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* Mobile: Card layout */}
      <div className="md:hidden p-3 space-y-2">
        {leads.map((lead) => (
          <LeadCard key={lead.domain || lead.id} lead={lead} onEnrich={onEnrich} />
        ))}
        {leads.length === 0 && (
          <p className="text-center text-gray-400 text-sm py-8">No hay leads asignados.</p>
        )}
      </div>

      {/* Desktop: Table layout */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-xs text-gray-500 uppercase">
              <th className="text-left px-4 py-2 font-medium">Empresa</th>
              <th className="text-left px-3 py-2 font-medium">Potencial</th>
              <th className="text-right px-3 py-2 font-medium">IG</th>
              <th className="text-left px-3 py-2 font-medium">Stage</th>
              <th className="text-left px-3 py-2 font-medium">Ult. Actividad</th>
              <th className="text-left px-3 py-2 font-medium">Creado</th>
              <th className="text-left px-3 py-2 font-medium">Enrich</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {leads.map((lead) => {
              const activity = formatRelativeDate(lead.hs_last_activity_date);
              const created = formatRelativeDate(lead.hs_lead_created_at);
              return (
                <tr key={lead.domain || lead.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-2.5">
                    <div>
                      <p className="font-medium text-gray-900 truncate max-w-[200px]">
                        {lead.company_name || lead.domain}
                      </p>
                      {lead.domain && (
                        <a
                          href={`https://${lead.domain}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-melonn-purple hover:underline"
                        >
                          {lead.domain}
                        </a>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2.5">
                    <PotentialTierBadge tier={lead.potential_tier} />
                  </td>
                  <td className="px-3 py-2.5 text-right text-gray-600">
                    {formatNumber(lead.ig_followers)}
                  </td>
                  <td className="px-3 py-2.5">
                    <StageBadge stage={lead.hs_lead_stage} />
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={`text-xs ${
                      activity.cold ? (activity.stale ? 'text-red-500 font-semibold' : 'text-melonn-orange font-medium') : 'text-gray-500'
                    }`}>
                      {activity.text}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={`text-xs ${created.stale ? 'text-red-500 font-semibold' : 'text-gray-500'}`}>
                      {created.text}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <EnrichmentBadge type={lead.enrichment_type} />
                  </td>
                  <td className="px-3 py-2.5">
                    {lead.enrichment_type !== 'full' && lead.domain && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onEnrich(lead.domain!, lead.geography || 'COL');
                        }}
                        className="px-3 py-1 rounded-md bg-melonn-purple text-white text-xs font-medium
                                   hover:bg-melonn-purple/90 transition-colors whitespace-nowrap"
                      >
                        Enrich
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
            {leads.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-gray-400 text-sm">
                  No hay leads asignados.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
