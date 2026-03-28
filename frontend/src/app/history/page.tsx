'use client';

import { useState, useEffect, useCallback } from 'react';
import { Header } from '@/components/Header';
import { getCompanies, getCompany } from '@/lib/api';
import { RetailDrawerSection } from '@/components/RetailDrawerSection';
import { PotentialTierBadge } from '@/components/PotentialTierBadge';
import type { CompanyListItem, EnrichmentV2Results } from '@/lib/types';

function fmt(n: number | null | undefined): string {
  if (n == null) return '—';
  return n.toLocaleString('es-CO');
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return '—';
  return `${(n * 100).toFixed(0)}%`;
}

function fmtDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('es-CO', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

function fmtShortDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  const dd = d.getDate().toString().padStart(2, '0');
  const mm = (d.getMonth() + 1).toString().padStart(2, '0');
  const hh = d.getHours().toString().padStart(2, '0');
  const min = d.getMinutes().toString().padStart(2, '0');
  return `${dd}/${mm} ${hh}:${min}`;
}

function ConfidenceBadge({ level }: { level: string | null | undefined }) {
  if (!level) return <span className="text-gray-400">—</span>;
  const colors: Record<string, string> = {
    high: 'bg-melonn-green-50 text-melonn-green',
    medium: 'bg-melonn-orange-50 text-melonn-orange',
    low: 'bg-red-50 text-red-500',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[level] || 'bg-gray-100 text-gray-500'}`}>
      {level}
    </span>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  if (value == null || value === '' || value === '—') return null;
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

function DetailDrawer({ domain, onClose }: { domain: string; onClose: () => void }) {
  const [data, setData] = useState<EnrichmentV2Results | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCompany(domain)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [domain]);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40"
        onClick={onClose}
      />
      {/* Drawer */}
      <div className="fixed top-0 right-0 h-full w-[480px] max-w-full bg-white shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            <h3 className="font-bold text-melonn-navy font-heading">
              {data?.company_name || domain}
            </h3>
            <p className="text-xs text-gray-400">{domain}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <p className="text-sm text-gray-400 text-center py-12">Cargando...</p>
          ) : !data ? (
            <p className="text-sm text-red-400 text-center py-12">No se encontró información.</p>
          ) : (
            <>
              <Section title="Identidad">
                <Row label="Empresa" value={data.company_name} />
                <Row label="Dominio" value={data.domain} />
                <Row label="País" value={data.geography} />
                <Row label="Confianza geografía" value={fmtPct(data.geography_confidence)} />
              </Section>

              <Section title="Categoría">
                <Row label="Categoría" value={data.category} />
                <Row label="Confianza" value={fmtPct(data.category_confidence)} />
                <Row label="Evidencia" value={data.category_evidence} />
              </Section>

              <Section title="Plataforma">
                <Row label="Plataforma" value={data.platform} />
                <Row label="Confianza" value={fmtPct(data.platform_confidence)} />
              </Section>

              <Section title="Redes Sociales">
                <Row label="IG Seguidores" value={fmt(data.ig_followers)} />
                <Row label="IG Score tamaño" value={data.ig_size_score} />
                <Row label="IG Score salud" value={data.ig_health_score} />
                <Row label="Instagram" value={data.instagram_url
                  ? <a href={data.instagram_url} target="_blank" rel="noreferrer" className="text-melonn-purple underline">{data.instagram_url}</a>
                  : undefined} />
                <Row label="FB Seguidores" value={fmt(data.fb_followers)} />
                <Row label="TikTok Seguidores" value={fmt(data.tiktok_followers)} />
              </Section>

              <Section title="Meta Ads">
                <Row label="Anuncios activos" value={fmt(data.meta_active_ads_count)} />
                <Row label="Ad Library" value={data.meta_ad_library_url
                  ? <a href={data.meta_ad_library_url} target="_blank" rel="noreferrer" className="text-melonn-purple underline">Ver anuncios</a>
                  : undefined} />
              </Section>

              <Section title="Catálogo">
                <Row label="Productos" value={fmt(data.product_count)} />
                <Row label="Precio promedio" value={data.avg_price != null ? `${data.currency || ''} ${fmt(data.avg_price)}` : undefined} />
                <Row label="Precio mínimo" value={data.price_range_min != null ? `${data.currency || ''} ${fmt(data.price_range_min)}` : undefined} />
                <Row label="Precio máximo" value={data.price_range_max != null ? `${data.currency || ''} ${fmt(data.price_range_max)}` : undefined} />
              </Section>

              <Section title="Tráfico web">
                <Row label="Visitas mensuales" value={fmt(data.estimated_monthly_visits)} />
                <Row label="Confianza" value={fmtPct(data.traffic_confidence)} />
                <Row label="Señales usadas" value={data.signals_used} />
              </Section>

              <Section title="Demanda Google">
                <Row label="Brand demand" value={data.brand_demand_score != null ? data.brand_demand_score.toFixed(2) : undefined} />
                <Row label="SERP coverage" value={data.site_serp_coverage_score != null ? data.site_serp_coverage_score.toFixed(2) : undefined} />
                <Row label="Confianza" value={fmtPct(data.google_confidence)} />
              </Section>

              <Section title="Estimación de pedidos">
                <Row label="Pesimista (p10)" value={fmt(data.prediction?.predicted_orders_p10)} />
                <Row label="Conservador (p50)" value={fmt(data.prediction?.predicted_orders_p50)} />
                <Row label="Optimista (p90)" value={fmt(data.prediction?.predicted_orders_p90)} />
                <Row label="Confianza" value={data.prediction?.prediction_confidence} />
              </Section>

              <RetailDrawerSection data={data} />

              <Section title="HubSpot CRM">
                <Row label="Estado" value={data.hubspot_company_id ? '✓ En CRM' : 'No encontrada'} />
                <Row label="Negocios" value={data.hubspot_deal_count != null ? String(data.hubspot_deal_count) : undefined} />
                <Row label="Etapa" value={data.hubspot_deal_stage} />
                <Row label="Contacto en CRM" value={data.hubspot_contact_exists != null ? (data.hubspot_contact_exists ? 'Sí' : 'No') : undefined} />
                <Row label="Ver en HubSpot" value={data.hubspot_company_url
                  ? <a href={data.hubspot_company_url} target="_blank" rel="noreferrer" className="text-melonn-purple underline">Abrir</a>
                  : undefined} />
              </Section>

              <Section title="Contacto">
                <Row label="Nombre" value={data.contact_name} />
                <Row label="Email" value={data.contact_email} />
                <Row label="LinkedIn empresa" value={data.company_linkedin
                  ? <a href={data.company_linkedin} target="_blank" rel="noreferrer" className="text-melonn-purple underline">Ver perfil</a>
                  : undefined} />
                <Row label="Empleados" value={fmt(data.number_employes)} />
              </Section>

              {data.contacts && data.contacts.length > 0 && (
                <Section title="Otros contactos">
                  {data.contacts.map((c, i) => (
                    <div key={i} className="py-1.5 border-b border-gray-100 last:border-0">
                      <p className="text-xs font-medium text-melonn-navy">{c.name}</p>
                      <p className="text-xs text-gray-400">{c.title}</p>
                      {c.email && <p className="text-xs text-gray-500">{c.email}</p>}
                    </div>
                  ))}
                </Section>
              )}

              <Section title="Ejecución">
                <Row label="Herramientas cubiertas" value={fmtPct(data.tool_coverage_pct)} />
                <Row label="Tiempo total" value={data.total_runtime_sec != null ? `${data.total_runtime_sec}s` : undefined} />
                <Row label="Costo estimado" value={data.cost_estimate_usd != null ? `$${data.cost_estimate_usd.toFixed(4)} USD` : undefined} />
              </Section>
            </>
          )}
        </div>
      </div>
    </>
  );
}

export default function HistoryPage() {
  const [companies, setCompanies] = useState<CompanyListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const limit = 25;

  const fetchCompanies = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getCompanies({ page, limit, search });
      setCompanies(data.companies);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to load companies:', err);
    } finally {
      setIsLoading(false);
    }
  }, [page, search]);

  useEffect(() => { fetchCompanies(); }, [fetchCompanies]);
  useEffect(() => { setPage(1); }, [search]);

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="min-h-screen bg-melonn-surface">
      <Header />

      <main className="max-w-[1400px] mx-auto px-4 py-8">
        {/* Search & Stats */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-bold text-melonn-navy font-heading">Enriched Companies</h2>
            <p className="text-sm text-gray-500">
              {total} {total === 1 ? 'empresa' : 'empresas'} en base de datos
            </p>
          </div>
          <input
            type="text"
            placeholder="Buscar por nombre o dominio..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-72 px-4 py-2 rounded-lg border border-gray-200 bg-white text-sm
                       focus:outline-none focus:ring-2 focus:ring-melonn-purple/30 focus:border-melonn-purple
                       placeholder:text-gray-400"
          />
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-melonn-purple-50 text-melonn-navy text-left">
                  <th className="px-3 py-2.5 font-semibold whitespace-nowrap">Empresa</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Potencial</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">País</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Categoría</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap text-right">IG</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap text-right">Meta Ads</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap text-right">Conservador</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap text-right">Optimista</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">CRM</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Contacto</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Fecha</th>
                  <th className="px-3 py-2.5 font-semibold w-[100px]"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {isLoading ? (
                  <tr>
                    <td colSpan={12} className="px-4 py-12 text-center text-gray-400">Cargando...</td>
                  </tr>
                ) : companies.length === 0 ? (
                  <tr>
                    <td colSpan={12} className="px-4 py-12 text-center text-gray-400">
                      {search ? 'Ninguna empresa coincide con la búsqueda' : 'Aún no hay empresas enriquecidas'}
                    </td>
                  </tr>
                ) : (
                  companies.map((c) => {
                    const isTop = c.potential_tier === 'Extraordinary' || c.potential_tier === 'Very Good';
                    return (
                    <tr key={c.id || c.domain} className={`hover:bg-melonn-purple-50/30 transition-colors ${isTop ? 'bg-melonn-green-50/30' : ''}`}>
                      <td className="px-3 py-2.5">
                        <div className="font-medium text-melonn-navy truncate max-w-[160px]">{c.company_name || c.domain}</div>
                        <div className="text-gray-400 truncate max-w-[160px]">{c.domain}</div>
                      </td>
                      <td className="px-2 py-2.5 whitespace-nowrap"><PotentialTierBadge tier={c.potential_tier} /></td>
                      <td className="px-2 py-2.5 text-gray-600 whitespace-nowrap">{c.geography || '—'}</td>
                      <td className="px-2 py-2.5 text-gray-600 whitespace-nowrap">{c.category || '—'}</td>
                      <td className="px-2 py-2.5 text-right text-gray-600 whitespace-nowrap">{fmt(c.ig_followers)}</td>
                      <td className="px-2 py-2.5 text-right text-gray-600 whitespace-nowrap">{fmt(c.meta_active_ads_count)}</td>
                      <td className="px-2 py-2.5 text-right font-semibold text-melonn-navy whitespace-nowrap">{fmt(c.predicted_orders_p50)}</td>
                      <td className="px-2 py-2.5 text-right text-gray-600 whitespace-nowrap">{fmt(c.predicted_orders_p90)}</td>
                      <td className="px-2 py-2.5 whitespace-nowrap">
                        {c.hubspot_company_id ? (
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-melonn-green-50 text-melonn-green">
                            {c.hubspot_deal_count ?? 0} {c.hubspot_deal_count === 1 ? 'deal' : 'deals'}
                          </span>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-2 py-2.5">
                        <div className="text-gray-600 truncate max-w-[120px]">{c.contact_name || '—'}</div>
                        {c.contact_email && (
                          <div className="text-gray-400 truncate max-w-[120px]">{c.contact_email}</div>
                        )}
                      </td>
                      <td className="px-2 py-2.5 text-gray-400 whitespace-nowrap">{fmtShortDate(c.updated_at)}</td>
                      <td className="px-3 py-2.5">
                        <button
                          onClick={() => setSelectedDomain(c.domain || null)}
                          className="px-2.5 py-1 rounded-md bg-melonn-purple text-white
                                     hover:bg-melonn-purple/90 transition-colors whitespace-nowrap font-medium"
                        >
                          Ver detalles
                        </button>
                      </td>
                    </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
              <p className="text-sm text-gray-500">
                Mostrando {(page - 1) * limit + 1}–{Math.min(page * limit, total)} de {total}
              </p>
              <div className="flex gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1 rounded-md text-sm border border-gray-200 disabled:opacity-40
                             hover:bg-melonn-purple-50 transition-colors"
                >
                  Anterior
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1 rounded-md text-sm border border-gray-200 disabled:opacity-40
                             hover:bg-melonn-purple-50 transition-colors"
                >
                  Siguiente
                </button>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Detail Drawer */}
      {selectedDomain && (
        <DetailDrawer domain={selectedDomain} onClose={() => setSelectedDomain(null)} />
      )}
    </div>
  );
}
