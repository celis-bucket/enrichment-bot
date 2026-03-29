'use client';

import { useState, useEffect, useCallback } from 'react';
import { Header } from '@/components/Header';
import { TeamSelector } from '@/components/team/TeamSelector';
import { KPICards } from '@/components/team/KPICards';
import { AlertsPanel } from '@/components/team/AlertsPanel';
import { PotentialDistribution } from '@/components/team/PotentialDistribution';
import { EnrichmentProgress } from '@/components/team/EnrichmentProgress';
import { TeamLeadTable } from '@/components/team/TeamLeadTable';
import { getTeamMembers, getTeamStats, getTeamAlerts, getTeamLeads, analyzeUrlV2, getCompany } from '@/lib/api';
import type { TeamStatsResponse, TeamAlertsResponse, LeadListItem, PipelineStep } from '@/lib/types';

const STORAGE_KEY = 'team_selected_owner';

const EMPTY_STATS: TeamStatsResponse = {
  owner: '',
  total_leads: 0,
  tier_distribution: {},
  stage_distribution: {},
  leads_not_enriched: 0,
  leads_worth_enrichment: 0,
  leads_cold_30d: 0,
  leads_stale_6m: 0,
  enrichment_pct: 0,
  avg_potential_score: 0,
};

// --- Enrichment Modal (same as /leads) ---
function EnrichModal({ domain, geography, onClose, onDone }: {
  domain: string;
  geography: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [selectedGeo, setSelectedGeo] = useState<string | null>(
    geography && geography !== 'UNKNOWN' ? geography : null
  );
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [status, setStatus] = useState<'picking' | 'running' | 'done' | 'error'>('picking');
  const [error, setError] = useState('');

  const startEnrichment = (geo: string) => {
    setSelectedGeo(geo);
    setStatus('running');
    analyzeUrlV2(
      domain,
      geo,
      (step) => {
        setSteps((prev) => {
          const existing = prev.findIndex((s) => s.step === step.step);
          if (existing >= 0) {
            const updated = [...prev];
            updated[existing] = step;
            return updated;
          }
          return [...prev, step];
        });
      },
      () => { setStatus('done'); },
      (err) => { setStatus('error'); setError(err); },
    ).catch((err) => { setStatus('error'); setError(err.message); });
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40"
           onClick={status === 'picking' || status === 'done' || status === 'error' ? onClose : undefined} />
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] max-w-[95vw] bg-white rounded-xl shadow-2xl z-50 p-4 sm:p-6">
        <h3 className="font-bold text-melonn-navy font-heading mb-1">Full Enrichment: {domain}</h3>

        {status === 'picking' && (
          <>
            <p className="text-sm text-gray-500 mb-4">Selecciona el pais para enriquecer:</p>
            <div className="flex gap-3 mb-4">
              <button
                onClick={() => startEnrichment('COL')}
                className={`flex-1 py-3 rounded-lg border-2 text-sm font-semibold transition-all ${
                  selectedGeo === 'COL'
                    ? 'border-melonn-green bg-melonn-green/10 text-melonn-green'
                    : 'border-gray-200 text-gray-600 hover:border-melonn-green/50'
                }`}
              >
                Colombia
              </button>
              <button
                onClick={() => startEnrichment('MEX')}
                className={`flex-1 py-3 rounded-lg border-2 text-sm font-semibold transition-all ${
                  selectedGeo === 'MEX'
                    ? 'border-melonn-green bg-melonn-green/10 text-melonn-green'
                    : 'border-gray-200 text-gray-600 hover:border-melonn-green/50'
                }`}
              >
                Mexico
              </button>
            </div>
            <div className="flex justify-end">
              <button onClick={onClose} className="px-4 py-2 rounded-md bg-gray-200 text-gray-700 text-sm font-medium">
                Cancelar
              </button>
            </div>
          </>
        )}

        {status !== 'picking' && (
          <>
            <p className="text-xs text-gray-400 mb-4">
              {status === 'running' ? `Ejecutando pipeline completo (${selectedGeo})...` : status === 'done' ? 'Completado' : 'Error'}
            </p>
            <div className="max-h-[300px] overflow-y-auto space-y-1 mb-4">
              {steps.map((s) => (
                <div key={s.step} className="flex items-center gap-2 text-xs">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${
                    s.status === 'ok' ? 'bg-melonn-green' :
                    s.status === 'running' ? 'bg-yellow-400 animate-pulse' :
                    s.status === 'fail' ? 'bg-red-400' : 'bg-gray-300'
                  }`} />
                  <span className="text-melonn-navy font-medium w-32 truncate">{s.step}</span>
                  <span className="text-gray-400 truncate flex-1">{s.detail}</span>
                  {s.duration_ms != null && (
                    <span className="text-gray-300 shrink-0">{(s.duration_ms / 1000).toFixed(1)}s</span>
                  )}
                </div>
              ))}
            </div>
            {error && <p className="text-xs text-red-500 mb-3">{error}</p>}
            <div className="flex justify-end gap-2">
              {status === 'done' && (
                <button
                  onClick={() => { onDone(); onClose(); }}
                  className="px-4 py-2 rounded-md bg-melonn-green text-white text-sm font-medium hover:bg-melonn-green/90"
                >
                  Listo
                </button>
              )}
              {status === 'error' && (
                <button onClick={onClose} className="px-4 py-2 rounded-md bg-gray-200 text-gray-700 text-sm font-medium">
                  Cerrar
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}

export default function TeamPage() {
  const [members, setMembers] = useState<string[]>([]);
  const [owner, setOwner] = useState('');
  const [stats, setStats] = useState<TeamStatsResponse>(EMPTY_STATS);
  const [alerts, setAlerts] = useState<TeamAlertsResponse>({ owner: '', alerts: [] });
  const [leads, setLeads] = useState<LeadListItem[]>([]);
  const [sortBy, setSortBy] = useState('overall_potential_score');
  const [loading, setLoading] = useState(false);
  const [membersLoading, setMembersLoading] = useState(true);
  const [enrichingDomain, setEnrichingDomain] = useState<string | null>(null);
  const [enrichingGeo, setEnrichingGeo] = useState('COL');

  // Load members on mount
  useEffect(() => {
    getTeamMembers().then((m) => {
      setMembers(m);
      setMembersLoading(false);
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && m.includes(saved)) {
        setOwner(saved);
      }
    });
  }, []);

  // Fetch data when owner or sort changes
  const fetchData = useCallback(async (ownerName: string, sort: string) => {
    if (!ownerName) return;
    setLoading(true);
    try {
      const [statsData, alertsData, leadsData] = await Promise.all([
        getTeamStats(ownerName),
        getTeamAlerts(ownerName),
        getTeamLeads({ owner: ownerName, limit: 200, sort_by: sort }),
      ]);
      setStats(statsData);
      setAlerts(alertsData);
      setLeads(leadsData.companies);
    } catch (err) {
      console.error('Failed to fetch team data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (owner) {
      fetchData(owner, sortBy);
    }
  }, [owner, sortBy, fetchData]);

  const handleOwnerChange = (newOwner: string) => {
    setOwner(newOwner);
    if (newOwner) {
      localStorage.setItem(STORAGE_KEY, newOwner);
    } else {
      localStorage.removeItem(STORAGE_KEY);
      setStats(EMPTY_STATS);
      setAlerts({ owner: '', alerts: [] });
      setLeads([]);
    }
  };

  const handleSortChange = (field: string) => {
    setSortBy(field);
  };

  const handleEnrich = (domain: string, geography: string) => {
    setEnrichingDomain(domain);
    setEnrichingGeo(geography);
  };

  const handleEnrichDone = async () => {
    if (!enrichingDomain) return;
    try {
      const fresh = await getCompany(enrichingDomain);
      setLeads((prev) =>
        prev.map((l) =>
          l.domain === enrichingDomain
            ? {
                ...l,
                enrichment_type: 'full',
                potential_tier: (fresh as unknown as LeadListItem).potential_tier ?? l.potential_tier,
                overall_potential_score: (fresh as unknown as LeadListItem).overall_potential_score ?? l.overall_potential_score,
                ig_followers: fresh.ig_followers ?? l.ig_followers,
                predicted_orders_p90: fresh.prediction?.predicted_orders_p90 ?? l.predicted_orders_p90,
              }
            : l
        )
      );
    } catch {
      // Fallback: just mark as enriched locally
      setLeads((prev) =>
        prev.map((l) =>
          l.domain === enrichingDomain ? { ...l, enrichment_type: 'full' } : l
        )
      );
    }
    // Refresh stats and alerts after enrichment
    if (owner) {
      const [statsData, alertsData] = await Promise.all([
        getTeamStats(owner),
        getTeamAlerts(owner),
      ]);
      setStats(statsData);
      setAlerts(alertsData);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-[1400px] mx-auto px-4 py-8">
        {/* Row 1: Title + Selector */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
          <div>
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900">Mi Pipeline</h2>
            <p className="text-xs sm:text-sm text-gray-500">Panel de prospeccion personal</p>
          </div>
          <TeamSelector
            members={members}
            value={owner}
            onChange={handleOwnerChange}
          />
        </div>

        {/* Loading state for members */}
        {membersLoading && (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-melonn-purple" />
          </div>
        )}

        {/* No owner selected */}
        {!membersLoading && !owner && (
          <div className="flex flex-col items-center justify-center py-20 text-gray-400">
            <svg className="w-16 h-16 mb-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <p className="text-lg font-medium">Selecciona tu nombre para ver tu pipeline</p>
          </div>
        )}

        {/* Dashboard content */}
        {owner && !membersLoading && (
          <>
            {loading && (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-melonn-purple" />
              </div>
            )}

            {!loading && (
              <>
                <KPICards stats={stats} />

                <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-6">
                  <div className="lg:col-span-3">
                    <AlertsPanel alerts={alerts.alerts} />
                  </div>
                  <div className="lg:col-span-2 space-y-4">
                    <PotentialDistribution distribution={stats.tier_distribution} />
                    <EnrichmentProgress
                      total={stats.total_leads}
                      enrichedPct={stats.enrichment_pct}
                      worthEnrichment={stats.leads_worth_enrichment}
                    />
                  </div>
                </div>

                <TeamLeadTable
                  leads={leads}
                  sortBy={sortBy}
                  onSortChange={handleSortChange}
                  onEnrich={handleEnrich}
                />
              </>
            )}
          </>
        )}
      </main>

      {/* Enrichment Modal */}
      {enrichingDomain && (
        <EnrichModal
          domain={enrichingDomain}
          geography={enrichingGeo}
          onClose={() => setEnrichingDomain(null)}
          onDone={handleEnrichDone}
        />
      )}
    </div>
  );
}
