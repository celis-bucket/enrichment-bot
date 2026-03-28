'use client';

import { useState, useEffect, useCallback } from 'react';
import { Header } from '@/components/Header';
import { ScoreBar } from '@/components/ScoreBar';
import { PotentialTierBadge } from '@/components/PotentialTierBadge';
import { RetailDrawerSection } from '@/components/RetailDrawerSection';
import { getLeads, getCompany, getHubSpotDetail, analyzeUrlV2, syncLeads, submitFeedback } from '@/lib/api';
import type { LeadListItem, EnrichmentV2Results, PipelineStep, ApolloContact, HubSpotContact } from '@/lib/types';

function fmt(n: number | null | undefined): string {
  if (n == null) return '--';
  return n.toLocaleString('es-CO');
}

function isOlderThanMonths(dateStr: string | null | undefined, months: number): boolean {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  const cutoff = new Date();
  cutoff.setMonth(cutoff.getMonth() - months);
  return d < cutoff;
}

function isOlderThanDays(dateStr: string | null | undefined, days: number): boolean {
  if (!dateStr) return true; // no date = alert
  const d = new Date(dateStr);
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  return d < cutoff;
}

function AlertIcon({ color, title }: { color: string; title: string }) {
  return (
    <span title={title} className={`inline-block ml-1 w-2 h-2 rounded-full ${color}`} />
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  if (value == null || value === '' || value === '--') return null;
  return (
    <div className="flex justify-between items-start py-1.5 border-b border-gray-50 last:border-0">
      <span className="text-xs text-gray-400 shrink-0 w-44">{label}</span>
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

// --- Badges ---
function EnrichmentBadge({ type }: { type?: string | null }) {
  if (type === 'full') {
    return <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-melonn-green-50 text-melonn-green">Full</span>;
  }
  return <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">Lite</span>;
}

function WorthBadge({ worth }: { worth?: boolean | null }) {
  if (worth) {
    return <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-600">Si</span>;
  }
  return <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-400">No</span>;
}

function StageBadge({ stage }: { stage?: string | null }) {
  if (!stage) return <span className="text-gray-400">--</span>;
  const colors: Record<string, string> = {
    'Nuevo': 'bg-blue-50 text-blue-600',
    'Enrichment': 'bg-purple-50 text-purple-600',
    'Intentando contactar': 'bg-yellow-50 text-yellow-700',
    'Conectado': 'bg-green-50 text-green-600',
  };
  const c = colors[stage] || 'bg-gray-100 text-gray-500';
  return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${c}`}>{stage}</span>;
}

// --- Unified Contact type ---
interface UnifiedContact {
  name: string;
  title?: string | null;
  email?: string | null;
  phone?: string | null;
  linkedin_url?: string | null;
  source: 'apollo' | 'hubspot';
}

function SourceBadge({ source }: { source: 'apollo' | 'hubspot' }) {
  const styles = source === 'apollo'
    ? 'bg-orange-50 text-orange-600'
    : 'bg-blue-50 text-blue-600';
  return <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${styles}`}>{source === 'apollo' ? 'Apollo' : 'HubSpot'}</span>;
}

function ContactCard({ contact }: { contact: UnifiedContact }) {
  return (
    <div className="py-2 border-b border-gray-50 last:border-0">
      <div className="flex items-center gap-2 mb-0.5">
        <span className="text-xs font-medium text-melonn-navy">{contact.name || 'Sin nombre'}</span>
        <SourceBadge source={contact.source} />
      </div>
      {contact.title && <p className="text-[11px] text-gray-500">{contact.title}</p>}
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
        {contact.email && (
          <a href={`mailto:${contact.email}`} className="text-[11px] text-melonn-purple hover:underline">{contact.email}</a>
        )}
        {contact.phone && (
          <span className="text-[11px] text-gray-500">{contact.phone}</span>
        )}
        {contact.linkedin_url && (
          <a href={contact.linkedin_url} target="_blank" rel="noreferrer" className="text-[11px] text-melonn-purple hover:underline">LinkedIn</a>
        )}
      </div>
    </div>
  );
}

// --- Detail Drawer ---
function DetailDrawer({ domain, onClose, onEnrich }: { domain: string; onClose: () => void; onEnrich: (domain: string) => void }) {
  const [data, setData] = useState<EnrichmentV2Results | null>(null);
  const [loading, setLoading] = useState(true);
  const [hsContacts, setHsContacts] = useState<HubSpotContact[]>([]);

  useEffect(() => {
    getCompany(domain)
      .then((result) => {
        setData(result);
        // Fetch HubSpot contacts if company_id exists
        if (result.hubspot_company_id) {
          getHubSpotDetail(result.hubspot_company_id)
            .then((hs) => setHsContacts(hs.contacts || []))
            .catch(() => {});
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [domain]);

  // Merge contacts from both sources, deduplicate by email
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
      <div className="fixed top-0 right-0 h-full w-[480px] max-w-full bg-white shadow-2xl z-50 flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-melonn-navy font-heading">{data?.company_name || domain}</h3>
              {data?.potential_tier && <PotentialTierBadge tier={data.potential_tier} />}
            </div>
            <p className="text-xs text-gray-400">{domain}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onEnrich(domain)}
              className="px-3 py-1.5 rounded-md bg-melonn-green text-white text-xs font-medium hover:bg-melonn-green/90 transition-colors"
            >
              Full Enrich
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">x</button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <p className="text-sm text-gray-400 text-center py-12">Cargando...</p>
          ) : !data ? (
            <p className="text-sm text-red-400 text-center py-12">No se encontro informacion.</p>
          ) : (
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

              {(data.meta_active_ads_count != null || data.tiktok_active_ads_count != null) && (
                <Section title="Publicidad">
                  <Row label="Meta Ads activos" value={data.meta_active_ads_count != null ? String(data.meta_active_ads_count) : undefined} />
                  <Row label="Meta Ad Library" value={data.meta_ad_library_url
                    ? <a href={data.meta_ad_library_url} target="_blank" rel="noreferrer" className="text-melonn-purple underline">Ver</a>
                    : undefined} />
                  <Row label="TikTok Ads activos" value={data.tiktok_active_ads_count != null ? String(data.tiktok_active_ads_count) : undefined} />
                  <Row label="TikTok Ad Library" value={data.tiktok_ads_library_url
                    ? <a href={data.tiktok_ads_library_url} target="_blank" rel="noreferrer" className="text-melonn-purple underline">Ver</a>
                    : undefined} />
                </Section>
              )}

              {data.product_count != null && (
                <Section title="Catalogo">
                  <Row label="Productos" value={fmt(data.product_count)} />
                  <Row label="Precio promedio" value={data.avg_price != null ? `${data.currency || '$'} ${fmt(data.avg_price)}` : undefined} />
                  <Row label="Rango" value={data.price_range_min != null && data.price_range_max != null
                    ? `${data.currency || '$'} ${fmt(data.price_range_min)} - ${fmt(data.price_range_max)}`
                    : undefined} />
                </Section>
              )}

              {data.estimated_monthly_visits != null && (
                <Section title="Trafico Web">
                  <Row label="Visitas mensuales" value={fmt(data.estimated_monthly_visits)} />
                  <Row label="Confianza" value={data.traffic_confidence != null ? `${(data.traffic_confidence * 100).toFixed(0)}%` : undefined} />
                </Section>
              )}

              {(data.brand_demand_score != null || data.site_serp_coverage_score != null) && (
                <Section title="Demanda Google">
                  <Row label="Demanda de marca" value={data.brand_demand_score} />
                  <Row label="Cobertura SERP" value={data.site_serp_coverage_score} />
                </Section>
              )}

              {data.prediction && (
                <Section title="Estimacion de pedidos">
                  <Row label="Pesimista (p10)" value={fmt(data.prediction.predicted_orders_p10)} />
                  <Row label="Conservador (p50)" value={fmt(data.prediction.predicted_orders_p50)} />
                  <Row label="Optimista (p90)" value={fmt(data.prediction.predicted_orders_p90)} />
                </Section>
              )}

              {/* Contacts Section */}
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
          )}
        </div>
      </div>
    </>
  );
}

// --- Enrichment Modal ---
function EnrichModal({ domain, geography, onClose, onDone }: { domain: string; geography: string; onClose: () => void; onDone: () => void }) {
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [status, setStatus] = useState<'running' | 'done' | 'error'>('running');
  const [error, setError] = useState('');

  useEffect(() => {
    analyzeUrlV2(
      domain,
      geography || 'COL',
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
  }, [domain]);

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={status !== 'running' ? onClose : undefined} />
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] max-w-[90vw] bg-white rounded-xl shadow-2xl z-50 p-6">
        <h3 className="font-bold text-melonn-navy font-heading mb-1">Full Enrichment: {domain}</h3>
        <p className="text-xs text-gray-400 mb-4">
          {status === 'running' ? 'Ejecutando pipeline completo...' : status === 'done' ? 'Completado' : 'Error'}
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
      </div>
    </>
  );
}

// --- Feedback Button ---
function FeedbackButton({ domain }: { domain: string }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    if (!text.trim()) return;
    setSaving(true);
    try {
      await submitFeedback(domain, 'leads', text.trim());
      setSaved(true);
      setText('');
      setTimeout(() => { setSaved(false); setOpen(false); }, 1200);
    } catch (err) {
      console.error('Feedback error:', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
        className="px-2 py-1 rounded-md border border-gray-200 text-gray-500
                   hover:bg-gray-50 hover:text-melonn-purple transition-colors whitespace-nowrap text-xs"
        title="Dejar feedback"
      >
        Feedback
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={(e) => { e.stopPropagation(); setOpen(false); }} />
          <div
            className="absolute right-0 top-8 z-40 w-64 bg-white rounded-lg shadow-xl border border-gray-200 p-3"
            onClick={(e) => e.stopPropagation()}
          >
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="¿Qué salió mal?"
              className="w-full h-20 text-xs border border-gray-200 rounded-md p-2 resize-none
                         focus:outline-none focus:ring-2 focus:ring-melonn-purple/30 focus:border-melonn-purple"
              autoFocus
            />
            <div className="flex justify-end gap-2 mt-2">
              <button
                onClick={(e) => { e.stopPropagation(); setOpen(false); }}
                className="px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
              >
                Cancelar
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !text.trim()}
                className="px-3 py-1 text-xs rounded-md bg-melonn-purple text-white
                           hover:bg-melonn-purple/90 disabled:opacity-50 font-medium"
              >
                {saved ? 'Guardado!' : saving ? 'Guardando...' : 'Guardar'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// --- Filter Select ---
function FilterSelect({
  label, value, onChange, options,
}: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value} onChange={(e) => onChange(e.target.value)}
      className="px-3 py-2 rounded-lg border border-gray-200 bg-white text-sm
                 focus:outline-none focus:ring-2 focus:ring-melonn-purple/30 focus:border-melonn-purple text-gray-600"
      aria-label={label}
    >
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

// --- Summary Cards ---
function SummaryCards({ total, worthFull, fullyEnriched, leads }: { total: number; worthFull: number; fullyEnriched: number; leads: LeadListItem[] }) {
  const oldLeads = leads.filter(l => isOlderThanMonths(l.hs_lead_created_at, 6)).length;
  const noActivity = leads.filter(l => isOlderThanDays(l.hs_last_activity_date, 30)).length;
  const cards = [
    { label: 'Total Leads', count: total, color: 'border-melonn-purple text-melonn-purple bg-melonn-purple-50' },
    { label: 'Worth Enrichment', count: worthFull, color: 'border-melonn-green text-melonn-green bg-melonn-green-50' },
    { label: 'Fully Enriched', count: fullyEnriched, color: 'border-blue-400 text-blue-600 bg-blue-50' },
    { label: `Alertas (>6m: ${oldLeads}, inact: ${noActivity})`, count: oldLeads + noActivity, color: 'border-red-400 text-red-600 bg-red-50' },
  ];

  return (
    <div className="grid grid-cols-4 gap-3 mb-6">
      {cards.map((c) => (
        <div key={c.label} className={`rounded-xl border-2 px-4 py-3 ${c.color}`}>
          <p className="text-2xl font-bold font-heading">{c.count}</p>
          <p className="text-xs font-medium">{c.label}</p>
        </div>
      ))}
    </div>
  );
}

// --- Main Page ---
export default function LeadsPage() {
  const [leads, setLeads] = useState<LeadListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [worthFullCount, setWorthFullCount] = useState(0);
  const [fullyEnrichedCount, setFullyEnrichedCount] = useState(0);
  const [search, setSearch] = useState('');
  const [worthEnrich, setWorthEnrich] = useState('');
  const [enrichmentType, setEnrichmentType] = useState('');
  const [leadStage, setLeadStage] = useState('');
  const [owner, setOwner] = useState('');
  const [sortBy, setSortBy] = useState('lite_triage_score');
  const [isLoading, setIsLoading] = useState(true);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [enrichingDomain, setEnrichingDomain] = useState<string | null>(null);
  const [enrichingGeo, setEnrichingGeo] = useState<string>('COL');
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState('');

  const fetchLeads = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getLeads({
        page: 1, limit: 5000, search,
        worth_full_enrichment: worthEnrich,
        enrichment_type: enrichmentType,
        lead_stage: leadStage,
        sort_by: sortBy,
      });
      let filtered = data.companies;
      if (owner) {
        filtered = filtered.filter(l => (l.hs_lead_owner || '') === owner);
      }
      setLeads(filtered);
      setTotal(filtered.length);
      setWorthFullCount(filtered.filter(l => l.worth_full_enrichment).length);
      setFullyEnrichedCount(filtered.filter(l => l.enrichment_type === 'full').length);
    } catch (err) {
      console.error('Failed to load leads:', err);
    } finally {
      setIsLoading(false);
    }
  }, [search, worthEnrich, enrichmentType, leadStage, owner, sortBy]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  const handleSync = async () => {
    setSyncing(true);
    setSyncMsg('Iniciando sync...');
    try {
      await syncLeads(
        (detail) => setSyncMsg(detail),
        () => { setSyncMsg('Sync completado'); fetchLeads(); },
        (err) => { setSyncMsg(`Error: ${err}`); },
      );
    } catch (err) {
      setSyncMsg(`Error: ${err}`);
    } finally {
      setTimeout(() => { setSyncing(false); setSyncMsg(''); }, 3000);
    }
  };

  return (
    <div className="min-h-screen bg-melonn-surface">
      <Header />

      <main className="max-w-[1400px] mx-auto px-4 py-8">
        {/* Title + Sync button */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h2 className="text-lg font-bold text-melonn-navy font-heading">Leads Dashboard</h2>
            <p className="text-sm text-gray-500">
              {total} leads con lite enrichment
            </p>
          </div>
          <div className="flex items-center gap-3">
            {syncMsg && (
              <span className="text-xs text-gray-500 max-w-[300px] truncate">{syncMsg}</span>
            )}
            <button
              onClick={handleSync}
              disabled={syncing}
              className="px-4 py-2 rounded-lg bg-melonn-purple text-white text-sm font-medium
                         hover:bg-melonn-purple/90 transition-colors disabled:opacity-50 whitespace-nowrap"
            >
              {syncing ? 'Syncing...' : 'Sync HubSpot'}
            </button>
          </div>
        </div>

        {/* Summary Cards */}
        <SummaryCards total={total} worthFull={worthFullCount} fullyEnriched={fullyEnrichedCount} leads={leads} />

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <input
            type="text"
            placeholder="Buscar por nombre o dominio..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-64 px-4 py-2 rounded-lg border border-gray-200 bg-white text-sm
                       focus:outline-none focus:ring-2 focus:ring-melonn-purple/30 focus:border-melonn-purple
                       placeholder:text-gray-400"
          />
          <FilterSelect label="Worth Enrich" value={worthEnrich} onChange={setWorthEnrich} options={[
            { value: '', label: 'Worth Enrich: Todos' },
            { value: 'true', label: 'Si' },
            { value: 'false', label: 'No' },
          ]} />
          <FilterSelect label="Enrichment" value={enrichmentType} onChange={setEnrichmentType} options={[
            { value: '', label: 'Enrichment: Todos' },
            { value: 'lite', label: 'Lite' },
            { value: 'full', label: 'Full' },
          ]} />
          <FilterSelect label="Lead Stage" value={leadStage} onChange={setLeadStage} options={[
            { value: '', label: 'Todos los stages' },
            { value: 'Nuevo', label: 'Nuevo' },
            { value: 'Enrichment', label: 'Enrichment' },
            { value: 'Intentando contactar', label: 'Intentando contactar' },
            { value: 'Conectado', label: 'Conectado' },
          ]} />
          <FilterSelect label="Responsable" value={owner} onChange={setOwner} options={[
            { value: '', label: 'Todos los responsables' },
            { value: 'Alejandra Gil Rivera', label: 'Alejandra Gil' },
            { value: 'Angie Aristizabal', label: 'Angie Aristizabal' },
            { value: 'Camila Quiceno', label: 'Camila Quiceno' },
            { value: 'Aury Giselly Osuna Saavedra', label: 'Aury Osuna' },
            { value: 'Daniela Garcia Viasus', label: 'Daniela Garcia' },
            { value: 'Rogers Belandria', label: 'Rogers Belandria' },
            { value: 'Yeraldine Prieto', label: 'Yeraldine Prieto' },
            { value: 'Esteban Sanchez', label: 'Esteban Sanchez' },
          ]} />
          <FilterSelect label="Ordenar" value={sortBy} onChange={setSortBy} options={[
            { value: 'lite_triage_score', label: 'Score' },
            { value: 'ig_followers', label: 'IG Followers' },
            { value: 'updated_at', label: 'Actualizado' },
          ]} />
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-melonn-purple-50 text-melonn-navy text-left">
                  <th className="px-3 py-2.5 font-semibold whitespace-nowrap">Empresa</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Score</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap text-right">IG Seguidores</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Responsable</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Creado</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Lead Stage</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Ult. Actividad</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Ult. Cierre Perdido</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Enrich</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap text-right">P90 Orders</th>
                  <th className="px-3 py-2.5 font-semibold w-[140px]"></th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap text-right">Feedback</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {isLoading ? (
                  <tr>
                    <td colSpan={12} className="px-4 py-12 text-center text-gray-400">Cargando...</td>
                  </tr>
                ) : leads.length === 0 ? (
                  <tr>
                    <td colSpan={12} className="px-4 py-12 text-center text-gray-400">
                      {search ? 'Ningun lead coincide con los filtros' : 'No hay leads. Haz click en "Sync HubSpot" para importar.'}
                    </td>
                  </tr>
                ) : (
                  leads.map((l) => {
                    const webUrl = l.clean_url || (l.domain ? `https://${l.domain}` : null);
                    return (
                    <tr
                      key={l.id || l.domain}
                      className="hover:bg-melonn-purple-50/30 transition-colors cursor-pointer"
                      onClick={() => setSelectedDomain(l.domain || null)}
                    >
                      <td className="px-3 py-2.5">
                        <div className="font-medium text-melonn-navy truncate max-w-[180px]">
                          {l.company_name || l.domain}
                        </div>
                        {webUrl ? (
                          <a
                            href={webUrl}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="text-xs text-melonn-purple hover:underline truncate block max-w-[180px]"
                          >
                            {l.domain}
                          </a>
                        ) : (
                          <div className="text-xs text-gray-400 truncate max-w-[180px]">{l.domain || '--'}</div>
                        )}
                      </td>
                      <td className="px-2 py-2.5 whitespace-nowrap">
                        <ScoreBar score={l.lite_triage_score} />
                      </td>
                      <td className="px-2 py-2.5 text-right text-gray-600 whitespace-nowrap">{fmt(l.ig_followers)}</td>
                      <td className="px-2 py-2.5 text-gray-600 whitespace-nowrap truncate max-w-[120px]">
                        {l.hs_lead_owner || '--'}
                      </td>
                      <td className="px-2 py-2.5 text-gray-500 whitespace-nowrap text-xs">
                        {l.hs_lead_created_at ? l.hs_lead_created_at.slice(0, 10) : '--'}
                        {isOlderThanMonths(l.hs_lead_created_at, 6) && (
                          <AlertIcon color="bg-red-500" title="Lead creado hace mas de 6 meses" />
                        )}
                      </td>
                      <td className="px-2 py-2.5 whitespace-nowrap"><StageBadge stage={l.hs_lead_stage} /></td>
                      <td className="px-2 py-2.5 text-gray-500 whitespace-nowrap text-xs">
                        {l.hs_last_activity_date ? l.hs_last_activity_date.slice(0, 10) : '--'}
                        {isOlderThanDays(l.hs_last_activity_date, 30) && (
                          <AlertIcon color="bg-orange-400" title="Sin actividad hace mas de 30 dias" />
                        )}
                        {(l.hs_open_tasks_count == null || l.hs_open_tasks_count === 0) && (
                          <AlertIcon color="bg-yellow-400" title="Sin tareas pendientes" />
                        )}
                      </td>
                      <td className="px-2 py-2.5 text-gray-500 whitespace-nowrap text-xs">
                        {l.hs_last_lost_deal_date || '--'}
                      </td>
                      <td className="px-2 py-2.5 whitespace-nowrap"><EnrichmentBadge type={l.enrichment_type} /></td>
                      <td className="px-2 py-2.5 text-right font-semibold text-melonn-navy whitespace-nowrap">
                        {l.enrichment_type === 'full' && l.predicted_orders_p90 ? fmt(l.predicted_orders_p90) : '--'}
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex gap-1">
                          <button
                            onClick={(e) => { e.stopPropagation(); setSelectedDomain(l.domain || null); }}
                            className="px-2.5 py-1 rounded-md bg-melonn-purple text-white
                                       hover:bg-melonn-purple/90 transition-colors whitespace-nowrap font-medium"
                          >
                            Ver
                          </button>
                          {l.enrichment_type !== 'full' && l.domain && (
                            <button
                              onClick={(e) => { e.stopPropagation(); setEnrichingDomain(l.domain || null); setEnrichingGeo(l.geography || 'COL'); }}
                              className="px-2.5 py-1 rounded-md bg-melonn-green text-white
                                         hover:bg-melonn-green/90 transition-colors whitespace-nowrap font-medium"
                            >
                              Enrich
                            </button>
                          )}
                        </div>
                      </td>
                      <td className="px-2 py-2.5 text-right">
                        {l.domain && <FeedbackButton domain={l.domain} />}
                      </td>
                    </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Row count */}
          <div className="px-4 py-3 border-t border-gray-100">
            <p className="text-sm text-gray-500">
              Mostrando {leads.length} de {total} leads
            </p>
          </div>
        </div>
      </main>

      {/* Detail Drawer */}
      {selectedDomain && !enrichingDomain && (
        <DetailDrawer
          domain={selectedDomain}
          onClose={() => setSelectedDomain(null)}
          onEnrich={(d) => { setSelectedDomain(null); setEnrichingDomain(d); }}
        />
      )}

      {/* Enrichment Modal */}
      {enrichingDomain && (
        <EnrichModal
          domain={enrichingDomain}
          geography={enrichingGeo}
          onClose={() => setEnrichingDomain(null)}
          onDone={fetchLeads}
        />
      )}
    </div>
  );
}
