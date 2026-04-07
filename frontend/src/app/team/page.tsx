'use client';

import { useState, useEffect, useCallback } from 'react';
import { Header } from '@/components/Header';
import { ScoreBar } from '@/components/ScoreBar';
import { PotentialTierBadge } from '@/components/PotentialTierBadge';
import { RetailDrawerSection } from '@/components/RetailDrawerSection';
import { TeamSelector } from '@/components/team/TeamSelector';
import { KPICards } from '@/components/team/KPICards';
import { AlertsPanel } from '@/components/team/AlertsPanel';
import { PotentialDistribution } from '@/components/team/PotentialDistribution';
import { EnrichmentProgress } from '@/components/team/EnrichmentProgress';
import { TeamLeadTable } from '@/components/team/TeamLeadTable';
import { getTeamMembers, getTeamStats, getTeamAlerts, getTeamLeads, analyzeUrlV2, getCompany, getHubSpotDetail } from '@/lib/api';
import type { TeamStatsResponse, TeamAlertsResponse, LeadListItem, PipelineStep, EnrichmentV2Results, ApolloContact, HubSpotContact } from '@/lib/types';

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

function fmt(n: number | null | undefined): string {
  if (n == null) return '--';
  return n.toLocaleString('es-CO');
}

// --- Detail helpers ---
function Row({ label, value }: { label: string; value: React.ReactNode }) {
  if (value == null || value === '' || value === '--') return null;
  return (
    <div className="flex justify-between items-start py-1.5 border-b border-gray-50 last:border-0">
      <span className="text-xs text-gray-400 shrink-0 w-40">{label}</span>
      <span className="text-xs text-melonn-navy text-right break-all">{value}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-melonn-purple mb-1">{title}</h4>
      <div className="bg-gray-50 rounded-lg px-3 py-1">{children}</div>
    </div>
  );
}

// --- Contact types ---
interface UnifiedContact {
  name: string;
  title?: string | null;
  email?: string | null;
  phone?: string | null;
  linkedin_url?: string | null;
  source: 'apollo' | 'hubspot';
}

function ContactCard({ contact }: { contact: UnifiedContact }) {
  return (
    <div className="py-2 border-b border-gray-50 last:border-0">
      <div className="flex items-center gap-2 mb-0.5">
        <span className="text-xs font-medium text-melonn-navy">{contact.name || 'Sin nombre'}</span>
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
          contact.source === 'apollo' ? 'bg-orange-50 text-orange-600' : 'bg-blue-50 text-blue-600'
        }`}>{contact.source === 'apollo' ? 'Apollo' : 'HubSpot'}</span>
      </div>
      {contact.title && <p className="text-[11px] text-gray-500">{contact.title}</p>}
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
        {contact.email && <a href={`mailto:${contact.email}`} className="text-[11px] text-melonn-purple hover:underline">{contact.email}</a>}
        {contact.phone && <span className="text-[11px] text-gray-500">{contact.phone}</span>}
        {contact.linkedin_url && <a href={contact.linkedin_url} target="_blank" rel="noreferrer" className="text-[11px] text-melonn-purple hover:underline">LinkedIn</a>}
      </div>
    </div>
  );
}

// --- Detail Modal ---
function DetailModal({ domain, onClose, onEnrich }: { domain: string; onClose: () => void; onEnrich: (domain: string) => void }) {
  const [data, setData] = useState<EnrichmentV2Results | null>(null);
  const [loading, setLoading] = useState(true);
  const [hsContacts, setHsContacts] = useState<HubSpotContact[]>([]);
  const [tab, setTab] = useState<'detail' | 'activity'>('detail');

  useEffect(() => {
    getCompany(domain)
      .then((result) => {
        setData(result);
        if (result.hubspot_company_id) {
          getHubSpotDetail(result.hubspot_company_id)
            .then((hs) => setHsContacts(hs.contacts || []))
            .catch(() => {});
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [domain]);

  const allContacts: UnifiedContact[] = [];
  const seenEmails = new Set<string>();
  if (data?.contacts) {
    for (const c of data.contacts as ApolloContact[]) {
      if (c.email) seenEmails.add(c.email.toLowerCase());
      allContacts.push({ name: c.name, title: c.title, email: c.email, phone: c.phone, linkedin_url: c.linkedin_url, source: 'apollo' });
    }
  }
  for (const c of hsContacts) {
    if (c.email && seenEmails.has(c.email.toLowerCase())) continue;
    allContacts.push({ name: c.name || '', title: c.title, email: c.email, source: 'hubspot' });
  }

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />
      <div className="fixed top-0 right-0 h-full w-[520px] max-w-full bg-white shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 shrink-0">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-melonn-navy font-heading truncate">{data?.company_name || domain}</h3>
              {data?.potential_tier && <PotentialTierBadge tier={data.potential_tier} />}
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <p className="text-xs text-gray-400">{domain}</p>
              {data?.hubspot_company_url && (
                <a href={data.hubspot_company_url} target="_blank" rel="noreferrer" className="text-xs text-blue-500 hover:underline">HubSpot</a>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={() => onEnrich(domain)}
              className="px-3 py-1.5 rounded-md bg-melonn-green text-white text-xs font-medium hover:bg-melonn-green/90">
              Full Enrich
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">x</button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-100 px-5 shrink-0">
          <button onClick={() => setTab('detail')}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
              tab === 'detail' ? 'border-melonn-purple text-melonn-purple' : 'border-transparent text-gray-400 hover:text-gray-600'
            }`}>
            Detalle
          </button>
          <button onClick={() => setTab('activity')}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
              tab === 'activity' ? 'border-melonn-purple text-melonn-purple' : 'border-transparent text-gray-400 hover:text-gray-600'
            }`}>
            Actividad
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-melonn-purple" />
            </div>
          ) : !data ? (
            <p className="text-sm text-red-400 text-center py-12">No se encontro informacion.</p>
          ) : tab === 'detail' ? (
            <>
              <Section title="Triage Score">
                <Row label="Lite Score" value={<ScoreBar score={(data as unknown as LeadListItem).lite_triage_score} />} />
                <Row label="Plataforma" value={data.platform} />
                <Row label="Pais" value={data.geography} />
                <Row label="Categoria" value={data.category} />
                <Row label="Enrichment" value={(data as unknown as LeadListItem).enrichment_type || 'lite'} />
              </Section>

              {data.overall_potential_score != null && (
                <Section title="Potential Score">
                  <Row label="Overall" value={<ScoreBar score={data.overall_potential_score} />} />
                  <Row label="Tier" value={<PotentialTierBadge tier={data.potential_tier} />} />
                  <Row label="E-commerce Size" value={<ScoreBar score={data.ecommerce_size_score} />} />
                  <Row label="Fit" value={<ScoreBar score={data.fit_score} />} />
                </Section>
              )}

              <Section title="Redes Sociales">
                <Row label="IG Seguidores" value={fmt(data.ig_followers)} />
                <Row label="IG Score tamano" value={data.ig_size_score} />
                <Row label="IG Score salud" value={data.ig_health_score} />
                <Row label="Instagram" value={data.instagram_url
                  ? <a href={data.instagram_url} target="_blank" rel="noreferrer" className="text-melonn-purple underline">Ver perfil</a>
                  : undefined} />
                <Row label="FB Seguidores" value={data.fb_followers ? fmt(data.fb_followers) : undefined} />
                <Row label="TikTok Seguidores" value={data.tiktok_followers ? fmt(data.tiktok_followers) : undefined} />
              </Section>

              {data.meta_active_ads_count != null && (
                <Section title="Publicidad">
                  <Row label="Meta Ads activos" value={String(data.meta_active_ads_count)} />
                  <Row label="Meta Ad Library" value={data.meta_ad_library_url
                    ? <a href={data.meta_ad_library_url} target="_blank" rel="noreferrer" className="text-melonn-purple underline">Ver</a>
                    : undefined} />
                </Section>
              )}

              {data.product_count != null && (
                <Section title="Catalogo">
                  <Row label="Productos" value={fmt(data.product_count)} />
                  <Row label="Precio promedio" value={data.avg_price != null ? `${data.currency || '$'} ${fmt(data.avg_price)}` : undefined} />
                </Section>
              )}

              {data.estimated_monthly_visits != null && (
                <Section title="Trafico Web">
                  <Row label="Visitas mensuales" value={fmt(data.estimated_monthly_visits)} />
                </Section>
              )}

              {data.prediction && (
                <Section title="Estimacion de pedidos">
                  <Row label="Pesimista (p10)" value={fmt(data.prediction.predicted_orders_p10)} />
                  <Row label="Conservador (p50)" value={fmt(data.prediction.predicted_orders_p50)} />
                  <Row label="Optimista (p90)" value={fmt(data.prediction.predicted_orders_p90)} />
                </Section>
              )}

              <Section title={`Contactos (${allContacts.length})`}>
                {allContacts.length === 0 ? (
                  <p className="text-xs text-gray-400 py-2">Sin contactos. Ejecuta Full Enrich para obtener contactos via Apollo.</p>
                ) : (
                  allContacts.map((c, i) => <ContactCard key={`${c.source}-${c.email || i}`} contact={c} />)
                )}
                {data.company_linkedin && (
                  <div className="pt-2">
                    <Row label="LinkedIn empresa" value={
                      <a href={data.company_linkedin} target="_blank" rel="noreferrer" className="text-melonn-purple underline">Ver</a>
                    } />
                  </div>
                )}
                <Row label="Empleados" value={data.number_employes ? fmt(data.number_employes) : undefined} />
              </Section>

              <RetailDrawerSection data={data} />

              <Section title="HubSpot CRM">
                <Row label="Estado" value={data.hubspot_company_id ? 'En CRM' : 'No encontrada'} />
                <Row label="Negocios" value={data.hubspot_deal_count != null ? String(data.hubspot_deal_count) : undefined} />
                <Row label="Etapa" value={data.hubspot_deal_stage} />
                <Row label="Ver en HubSpot" value={data.hubspot_company_url
                  ? <a href={data.hubspot_company_url} target="_blank" rel="noreferrer" className="text-melonn-purple underline">Abrir</a>
                  : undefined} />
              </Section>
            </>
          ) : (
            /* Activity tab */
            <ActivityTab domain={domain} data={data} />
          )}
        </div>
      </div>
    </>
  );
}

// --- Activity Tab ---
function ActivityTab({ domain, data }: { domain: string; data: EnrichmentV2Results | null }) {
  const lead = data as unknown as LeadListItem | null;

  const activityCount = lead?.hs_activity_count ?? 0;
  const openTasks = lead?.hs_open_tasks_count ?? 0;
  const lastActivity = lead?.hs_last_activity_date;
  const createdAt = lead?.hs_lead_created_at;
  const lastLostDeal = lead?.hs_last_lost_deal_date;
  const dealCount = data?.hubspot_deal_count ?? 0;
  const dealStage = data?.hubspot_deal_stage;
  const leadStage = lead?.hs_lead_stage;
  const leadLabel = lead?.hs_lead_label;

  const daysSinceActivity = lastActivity
    ? Math.floor((Date.now() - new Date(lastActivity).getTime()) / (1000 * 60 * 60 * 24))
    : null;

  const daysSinceCreated = createdAt
    ? Math.floor((Date.now() - new Date(createdAt).getTime()) / (1000 * 60 * 60 * 24))
    : null;

  return (
    <div className="space-y-4">
      <Section title="Estado del Lead">
        <Row label="Lead Stage" value={leadStage} />
        <Row label="Lead Label" value={leadLabel} />
        <Row label="Creado" value={createdAt ? `${new Date(createdAt).toLocaleDateString('es-CO')}${daysSinceCreated != null ? ` (hace ${daysSinceCreated}d)` : ''}` : undefined} />
      </Section>

      <Section title="Actividad de Prospeccion">
        <Row label="Total actividades" value={activityCount > 0 ? String(activityCount) : '0'} />
        <Row label="Tareas abiertas" value={String(openTasks)} />
        <Row label="Ultima actividad" value={lastActivity
          ? `${new Date(lastActivity).toLocaleDateString('es-CO')}${daysSinceActivity != null ? ` (hace ${daysSinceActivity}d)` : ''}`
          : 'Sin actividad registrada'} />
        {daysSinceActivity != null && daysSinceActivity > 30 && (
          <div className="py-2">
            <span className="px-2 py-1 rounded text-xs font-medium bg-red-50 text-red-500">
              Sin actividad hace {daysSinceActivity} dias
            </span>
          </div>
        )}
      </Section>

      <Section title="Deals">
        <Row label="Negocios" value={String(dealCount)} />
        <Row label="Etapa mas avanzada" value={dealStage} />
        <Row label="Ultimo cierre perdido" value={lastLostDeal ? new Date(lastLostDeal).toLocaleDateString('es-CO') : undefined} />
      </Section>

      {data?.hubspot_company_url && (
        <div className="pt-2">
          <a href={data.hubspot_company_url} target="_blank" rel="noreferrer"
             className="block w-full text-center px-4 py-2.5 rounded-lg bg-blue-50 text-blue-600 text-sm font-medium hover:bg-blue-100 transition-colors">
            Ver actividad completa en HubSpot
          </a>
        </div>
      )}
    </div>
  );
}

// --- Enrichment Modal ---
function EnrichModal({ domain, geography, onClose, onDone }: {
  domain: string; geography: string; onClose: () => void; onDone: () => void;
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
    analyzeUrlV2(domain, geo,
      (step) => {
        setSteps((prev) => {
          const idx = prev.findIndex((s) => s.step === step.step);
          if (idx >= 0) { const u = [...prev]; u[idx] = step; return u; }
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
              <button onClick={() => startEnrichment('COL')}
                className={`flex-1 py-3 rounded-lg border-2 text-sm font-semibold transition-all ${
                  selectedGeo === 'COL' ? 'border-melonn-green bg-melonn-green/10 text-melonn-green' : 'border-gray-200 text-gray-600 hover:border-melonn-green/50'
                }`}>Colombia</button>
              <button onClick={() => startEnrichment('MEX')}
                className={`flex-1 py-3 rounded-lg border-2 text-sm font-semibold transition-all ${
                  selectedGeo === 'MEX' ? 'border-melonn-green bg-melonn-green/10 text-melonn-green' : 'border-gray-200 text-gray-600 hover:border-melonn-green/50'
                }`}>Mexico</button>
            </div>
            <div className="flex justify-end">
              <button onClick={onClose} className="px-4 py-2 rounded-md bg-gray-200 text-gray-700 text-sm font-medium">Cancelar</button>
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
                    s.status === 'ok' ? 'bg-melonn-green' : s.status === 'running' ? 'bg-yellow-400 animate-pulse' : s.status === 'fail' ? 'bg-red-400' : 'bg-gray-300'
                  }`} />
                  <span className="text-melonn-navy font-medium w-32 truncate">{s.step}</span>
                  <span className="text-gray-400 truncate flex-1">{s.detail}</span>
                  {s.duration_ms != null && <span className="text-gray-300 shrink-0">{(s.duration_ms / 1000).toFixed(1)}s</span>}
                </div>
              ))}
            </div>
            {error && <p className="text-xs text-red-500 mb-3">{error}</p>}
            <div className="flex justify-end gap-2">
              {status === 'done' && (
                <button onClick={() => { onDone(); onClose(); }}
                  className="px-4 py-2 rounded-md bg-melonn-green text-white text-sm font-medium hover:bg-melonn-green/90">Listo</button>
              )}
              {status === 'error' && (
                <button onClick={onClose} className="px-4 py-2 rounded-md bg-gray-200 text-gray-700 text-sm font-medium">Cerrar</button>
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}

// --- Main Page ---
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
  const [viewingDomain, setViewingDomain] = useState<string | null>(null);

  useEffect(() => {
    getTeamMembers().then((m) => {
      setMembers(m);
      setMembersLoading(false);
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && m.includes(saved)) setOwner(saved);
    });
  }, []);

  const fetchData = useCallback(async (ownerName: string, sort: string) => {
    if (!ownerName) return;
    setLoading(true);
    try {
      const [s, a, l] = await Promise.all([
        getTeamStats(ownerName), getTeamAlerts(ownerName),
        getTeamLeads({ owner: ownerName, limit: 200, sort_by: sort }),
      ]);
      setStats(s); setAlerts(a); setLeads(l.companies);
    } catch (err) { console.error('Failed to fetch team data:', err); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { if (owner) fetchData(owner, sortBy); }, [owner, sortBy, fetchData]);

  const handleOwnerChange = (newOwner: string) => {
    setOwner(newOwner);
    if (newOwner) { localStorage.setItem(STORAGE_KEY, newOwner); }
    else { localStorage.removeItem(STORAGE_KEY); setStats(EMPTY_STATS); setAlerts({ owner: '', alerts: [] }); setLeads([]); }
  };

  const handleEnrich = (domain: string, geography: string) => {
    setEnrichingDomain(domain); setEnrichingGeo(geography);
  };

  const handleEnrichDone = async () => {
    if (!enrichingDomain) return;
    try {
      const fresh = await getCompany(enrichingDomain);
      setLeads((prev) => prev.map((l) =>
        l.domain === enrichingDomain ? {
          ...l, enrichment_type: 'full',
          potential_tier: (fresh as unknown as LeadListItem).potential_tier ?? l.potential_tier,
          overall_potential_score: (fresh as unknown as LeadListItem).overall_potential_score ?? l.overall_potential_score,
          ig_followers: fresh.ig_followers ?? l.ig_followers,
          predicted_orders_p90: fresh.prediction?.predicted_orders_p90 ?? l.predicted_orders_p90,
        } : l
      ));
    } catch {
      setLeads((prev) => prev.map((l) => l.domain === enrichingDomain ? { ...l, enrichment_type: 'full' } : l));
    }
    if (owner) {
      const [s, a] = await Promise.all([getTeamStats(owner), getTeamAlerts(owner)]);
      setStats(s); setAlerts(a);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-[1400px] mx-auto px-4 py-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
          <div>
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900">Mi Pipeline</h2>
            <p className="text-xs sm:text-sm text-gray-500">Panel de prospeccion personal</p>
          </div>
          <TeamSelector members={members} value={owner} onChange={handleOwnerChange} />
        </div>

        {membersLoading && (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-melonn-purple" />
          </div>
        )}

        {!membersLoading && !owner && (
          <div className="flex flex-col items-center justify-center py-20 text-gray-400">
            <svg className="w-16 h-16 mb-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <p className="text-lg font-medium">Selecciona tu nombre para ver tu pipeline</p>
          </div>
        )}

        {owner && !membersLoading && (
          <>
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-melonn-purple" />
              </div>
            ) : (
              <>
                <KPICards stats={stats} />
                <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-6">
                  <div className="lg:col-span-3"><AlertsPanel alerts={alerts.alerts} /></div>
                  <div className="lg:col-span-2 space-y-4">
                    <PotentialDistribution distribution={stats.tier_distribution} />
                    <EnrichmentProgress total={stats.total_leads} enrichedPct={stats.enrichment_pct} worthEnrichment={stats.leads_worth_enrichment} />
                  </div>
                </div>
                <TeamLeadTable leads={leads} sortBy={sortBy} onSortChange={setSortBy}
                  onEnrich={handleEnrich} onView={(d) => setViewingDomain(d)} />
              </>
            )}
          </>
        )}
      </main>

      {enrichingDomain && (
        <EnrichModal domain={enrichingDomain} geography={enrichingGeo}
          onClose={() => setEnrichingDomain(null)} onDone={handleEnrichDone} />
      )}

      {viewingDomain && (
        <DetailModal domain={viewingDomain} onClose={() => setViewingDomain(null)}
          onEnrich={(d) => { setViewingDomain(null); setEnrichingDomain(d); setEnrichingGeo('COL'); }} />
      )}
    </div>
  );
}
