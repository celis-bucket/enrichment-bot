'use client';

import Link from 'next/link';
import type { LeadListItem } from '@/lib/types';
import { PotentialTierBadge } from '@/components/PotentialTierBadge';

interface TeamLeadTableProps {
  leads: LeadListItem[];
  sortBy: string;
  onSortChange: (field: string) => void;
  onEnrich: (domain: string, geography: string) => void;
  onView: (domain: string) => void;
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
  const colors: Record<string, string> = {
    'Nuevo': 'bg-blue-50 text-blue-600',
    'Enrichment': 'bg-purple-50 text-purple-600',
    'Intentando contactar': 'bg-yellow-50 text-yellow-700',
    'Conectado': 'bg-green-50 text-green-600',
    'Descartado': 'bg-red-50 text-red-500',
    'Negocio abierto': 'bg-melonn-green-50 text-melonn-green',
  };
  const c = colors[stage] || 'bg-gray-100 text-gray-500';
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${c}`}>
      {stage}
    </span>
  );
}

function SourceBadge({ source }: { source: string | null | undefined }) {
  if (!source) return <span className="text-gray-400 text-xs">--</span>;
  const label = source === 'hubspot_leads' ? 'HubSpot' : source;
  return (
    <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-600 whitespace-nowrap">
      {label}
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
function LeadCard({ lead, onEnrich, onView }: { lead: LeadListItem; onEnrich: (domain: string, geography: string) => void; onView: (domain: string) => void }) {
  const activity = formatRelativeDate(lead.hs_last_activity_date);

  return (
    <div className="bg-white border border-gray-100 rounded-lg p-3 space-y-2">
      {/* Row 1: Name + Potential */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-gray-900 text-sm truncate">
            {lead.company_name || lead.domain}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            {lead.domain && (
              <a href={`https://${lead.domain}`} target="_blank" rel="noopener noreferrer"
                 className="text-xs text-melonn-purple hover:underline">{lead.domain}</a>
            )}
            {lead.hubspot_company_url && (
              <a href={lead.hubspot_company_url} target="_blank" rel="noopener noreferrer"
                 className="text-xs text-blue-500 hover:underline">HS</a>
            )}
          </div>
        </div>
        <PotentialTierBadge tier={lead.potential_tier} />
      </div>

      {/* Row 2: Metrics */}
      <div className="grid grid-cols-4 gap-2 text-xs">
        <div>
          <span className="text-gray-400">IG</span>
          <p className="text-gray-700 font-medium">{formatNumber(lead.ig_followers)}</p>
        </div>
        <div>
          <span className="text-gray-400">P90</span>
          <p className="text-gray-700 font-medium">{lead.predicted_orders_p90 ?? '--'}</p>
        </div>
        <div>
          <span className="text-gray-400">Stage</span>
          <div className="mt-0.5"><StageBadge stage={lead.hs_lead_stage} /></div>
        </div>
        <div>
          <span className="text-gray-400">Actividad</span>
          <p className={activity.cold ? 'text-red-500 font-semibold' : 'text-gray-500'}>{activity.text}</p>
        </div>
      </div>

      {/* Row 3: Actions */}
      <div className="flex items-center justify-end gap-2">
        <button onClick={() => lead.domain && onView(lead.domain)}
          className="px-3 py-1 rounded-md border border-gray-200 text-gray-600 text-xs font-medium hover:bg-gray-50 transition-colors">
          Ver
        </button>
        {lead.domain && (
          <Link href={`/conexion?domain=${encodeURIComponent(lead.domain)}`}
            className="px-3 py-1 rounded-md bg-emerald-500 text-white text-xs font-medium hover:bg-emerald-600 transition-colors whitespace-nowrap">
            Llamada
          </Link>
        )}
        {lead.enrichment_type !== 'full' && lead.domain && (
          <button onClick={() => onEnrich(lead.domain!, lead.geography || 'COL')}
            className="px-3 py-1 rounded-md bg-melonn-purple text-white text-xs font-medium hover:bg-melonn-purple/90 transition-colors">
            Enrich
          </button>
        )}
      </div>
    </div>
  );
}

export function TeamLeadTable({ leads, sortBy, onSortChange, onEnrich, onView }: TeamLeadTableProps) {
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
      <div className="md:hidden p-3 space-y-2 max-h-[70vh] overflow-y-auto">
        {leads.map((lead) => (
          <LeadCard key={lead.domain || lead.id} lead={lead} onEnrich={onEnrich} onView={onView} />
        ))}
        {leads.length === 0 && (
          <p className="text-center text-gray-400 text-sm py-8">No hay leads asignados.</p>
        )}
      </div>

      {/* Desktop: Table layout with sticky header */}
      <div className="hidden md:block overflow-auto max-h-[70vh]">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10">
            <tr className="bg-gray-50 text-xs text-gray-500 uppercase">
              <th className="text-left px-4 py-2.5 font-medium bg-gray-50">Empresa</th>
              <th className="text-left px-2 py-2.5 font-medium bg-gray-50">Potencial</th>
              <th className="text-right px-2 py-2.5 font-medium bg-gray-50">P90</th>
              <th className="text-right px-2 py-2.5 font-medium bg-gray-50">IG</th>
              <th className="text-left px-2 py-2.5 font-medium bg-gray-50">Fuente</th>
              <th className="text-left px-2 py-2.5 font-medium bg-gray-50">Stage</th>
              <th className="text-left px-2 py-2.5 font-medium bg-gray-50">Actividad</th>
              <th className="text-left px-2 py-2.5 font-medium bg-gray-50">Enrich</th>
              <th className="px-2 py-2.5 font-medium bg-gray-50 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {leads.map((lead) => {
              const activity = formatRelativeDate(lead.hs_last_activity_date);
              return (
                <tr key={lead.domain || lead.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-4 py-2.5">
                    <div>
                      <p className="font-medium text-gray-900 truncate max-w-[180px]">
                        {lead.company_name || lead.domain}
                      </p>
                      <div className="flex items-center gap-2">
                        {lead.domain && (
                          <a href={`https://${lead.domain}`} target="_blank" rel="noopener noreferrer"
                             className="text-xs text-melonn-purple hover:underline truncate max-w-[140px]">{lead.domain}</a>
                        )}
                        {lead.hubspot_company_url && (
                          <a href={lead.hubspot_company_url} target="_blank" rel="noopener noreferrer"
                             className="text-xs text-blue-500 hover:underline shrink-0" title="Abrir en HubSpot">HS</a>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-2 py-2.5">
                    <PotentialTierBadge tier={lead.potential_tier} />
                  </td>
                  <td className="px-2 py-2.5 text-right text-gray-600 font-medium tabular-nums">
                    {lead.predicted_orders_p90 != null ? lead.predicted_orders_p90.toLocaleString('es-CO') : '--'}
                  </td>
                  <td className="px-2 py-2.5 text-right text-gray-600 tabular-nums">
                    {formatNumber(lead.ig_followers)}
                  </td>
                  <td className="px-2 py-2.5">
                    <SourceBadge source={lead.source} />
                  </td>
                  <td className="px-2 py-2.5">
                    <StageBadge stage={lead.hs_lead_stage} />
                  </td>
                  <td className="px-2 py-2.5">
                    <span className={`text-xs ${
                      activity.cold ? (activity.stale ? 'text-red-500 font-semibold' : 'text-melonn-orange font-medium') : 'text-gray-500'
                    }`}>
                      {activity.text}
                    </span>
                  </td>
                  <td className="px-2 py-2.5">
                    <EnrichmentBadge type={lead.enrichment_type} />
                  </td>
                  <td className="px-2 py-2.5">
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        onClick={() => lead.domain && onView(lead.domain)}
                        className="px-2.5 py-1 rounded border border-gray-200 text-gray-600 text-xs font-medium
                                   hover:bg-gray-50 transition-colors whitespace-nowrap"
                      >
                        Ver
                      </button>
                      {lead.domain && (
                        <Link
                          href={`/conexion?domain=${encodeURIComponent(lead.domain)}`}
                          className="px-2.5 py-1 rounded bg-emerald-500 text-white text-xs font-medium
                                     hover:bg-emerald-600 transition-colors whitespace-nowrap"
                        >
                          Llamada
                        </Link>
                      )}
                      {lead.enrichment_type !== 'full' && lead.domain && (
                        <button
                          onClick={(e) => { e.stopPropagation(); onEnrich(lead.domain!, lead.geography || 'COL'); }}
                          className="px-2.5 py-1 rounded bg-melonn-purple text-white text-xs font-medium
                                     hover:bg-melonn-purple/90 transition-colors whitespace-nowrap"
                        >
                          Enrich
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
            {leads.length === 0 && (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-gray-400 text-sm">
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
