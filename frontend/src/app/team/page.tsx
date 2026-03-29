'use client';

import { useState, useEffect, useCallback } from 'react';
import { Header } from '@/components/Header';
import { TeamSelector } from '@/components/team/TeamSelector';
import { KPICards } from '@/components/team/KPICards';
import { AlertsPanel } from '@/components/team/AlertsPanel';
import { PotentialDistribution } from '@/components/team/PotentialDistribution';
import { EnrichmentProgress } from '@/components/team/EnrichmentProgress';
import { TeamLeadTable } from '@/components/team/TeamLeadTable';
import { getTeamMembers, getTeamStats, getTeamAlerts, getTeamLeads } from '@/lib/api';
import type { TeamStatsResponse, TeamAlertsResponse, LeadListItem } from '@/lib/types';

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

export default function TeamPage() {
  const [members, setMembers] = useState<string[]>([]);
  const [owner, setOwner] = useState('');
  const [stats, setStats] = useState<TeamStatsResponse>(EMPTY_STATS);
  const [alerts, setAlerts] = useState<TeamAlertsResponse>({ owner: '', alerts: [] });
  const [leads, setLeads] = useState<LeadListItem[]>([]);
  const [sortBy, setSortBy] = useState('overall_potential_score');
  const [loading, setLoading] = useState(false);
  const [membersLoading, setMembersLoading] = useState(true);

  // Load members on mount
  useEffect(() => {
    getTeamMembers().then((m) => {
      setMembers(m);
      setMembersLoading(false);
      // Restore persisted owner
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

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-[1400px] mx-auto px-4 py-8">
        {/* Row 1: Title + Selector */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Mi Pipeline</h2>
            <p className="text-sm text-gray-500">Panel de prospeccion personal</p>
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
            {/* Loading overlay */}
            {loading && (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-melonn-purple" />
              </div>
            )}

            {!loading && (
              <>
                {/* Row 2: KPI Cards */}
                <KPICards stats={stats} />

                {/* Row 3: Alerts + Distribution */}
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

                {/* Row 4: Lead Table */}
                <TeamLeadTable
                  leads={leads}
                  sortBy={sortBy}
                  onSortChange={handleSortChange}
                />
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
