'use client';

import { useState, useEffect, useCallback } from 'react';
import { Header } from '@/components/Header';
import { PotentialTierBadge } from '@/components/PotentialTierBadge';
import { ScoreBar } from '@/components/ScoreBar';
import { getCompanies, getCompany } from '@/lib/api';
import type { CompanyListItem, EnrichmentV2Results } from '@/lib/types';

function fmt(n: number | null | undefined): string {
  if (n == null) return '--';
  return n.toLocaleString('es-CO');
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return '--';
  return `${(n * 100).toFixed(0)}%`;
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

// --- Detail Drawer ---
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
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />
      <div className="fixed top-0 right-0 h-full w-[480px] max-w-full bg-white shadow-2xl z-50 flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-melonn-navy font-heading">{data?.company_name || domain}</h3>
              <PotentialTierBadge tier={data?.potential_tier} />
            </div>
            <p className="text-xs text-gray-400">{domain}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">x</button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <p className="text-sm text-gray-400 text-center py-12">Cargando...</p>
          ) : !data ? (
            <p className="text-sm text-red-400 text-center py-12">No se encontro informacion.</p>
          ) : (
            <>
              <Section title="Potential Score">
                <Row label="Overall" value={<ScoreBar score={data.overall_potential_score} />} />
                <Row label="Tier" value={<PotentialTierBadge tier={data.potential_tier} />} />
                <Row label="E-commerce Size" value={<ScoreBar score={data.ecommerce_size_score} />} />
                <Row label="Retail Size" value={<ScoreBar score={data.retail_size_score} />} />
                <Row label="Combined Size" value={<ScoreBar score={data.combined_size_score} />} />
                <Row label="Fit" value={<ScoreBar score={data.fit_score} />} />
              </Section>

              <Section title="Identidad">
                <Row label="Empresa" value={data.company_name} />
                <Row label="Pais" value={data.geography} />
                <Row label="Categoria" value={data.category} />
                <Row label="Plataforma" value={data.platform} />
              </Section>

              <Section title="Estimacion de pedidos">
                <Row label="Pesimista (p10)" value={fmt(data.prediction?.predicted_orders_p10)} />
                <Row label="Conservador (p50)" value={fmt(data.prediction?.predicted_orders_p50)} />
                <Row label="Optimista (p90)" value={fmt(data.prediction?.predicted_orders_p90)} />
                <Row label="Confianza" value={data.prediction?.prediction_confidence} />
              </Section>

              <Section title="Redes Sociales">
                <Row label="IG Seguidores" value={fmt(data.ig_followers)} />
                <Row label="IG Score tamano" value={data.ig_size_score} />
                <Row label="IG Score salud" value={data.ig_health_score} />
                <Row label="FB Seguidores" value={fmt(data.fb_followers)} />
                <Row label="TikTok Seguidores" value={fmt(data.tiktok_followers)} />
              </Section>

              <Section title="Trafico y Demanda">
                <Row label="Visitas mensuales" value={fmt(data.estimated_monthly_visits)} />
                <Row label="Brand demand" value={data.brand_demand_score != null ? data.brand_demand_score.toFixed(2) : undefined} />
                <Row label="Meta Ads activos" value={fmt(data.meta_active_ads_count)} />
              </Section>

              <Section title="Catalogo">
                <Row label="Productos" value={fmt(data.product_count)} />
                <Row label="Precio promedio" value={data.avg_price != null ? `${data.currency || ''} ${fmt(data.avg_price)}` : undefined} />
              </Section>

              <Section title="HubSpot CRM">
                <Row label="Estado" value={data.hubspot_company_id ? 'En CRM' : 'No encontrada'} />
                <Row label="Negocios" value={data.hubspot_deal_count != null ? String(data.hubspot_deal_count) : undefined} />
                <Row label="Etapa" value={data.hubspot_deal_stage} />
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
            </>
          )}
        </div>
      </div>
    </>
  );
}

// --- Filter Select ---
function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="px-3 py-2 rounded-lg border border-gray-200 bg-white text-sm
                 focus:outline-none focus:ring-2 focus:ring-melonn-purple/30 focus:border-melonn-purple
                 text-gray-600"
      aria-label={label}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

// --- Summary Cards ---
function SummaryCards({ companies }: { companies: CompanyListItem[] }) {
  const scored = companies.filter((c) => c.overall_potential_score != null);
  const extraordinary = scored.filter((c) => c.potential_tier === 'Extraordinary').length;
  const veryGood = scored.filter((c) => c.potential_tier === 'Very Good').length;
  const good = scored.filter((c) => c.potential_tier === 'Good').length;
  const low = scored.filter((c) => c.potential_tier === 'Low').length;

  const cards = [
    { label: 'Extraordinary', count: extraordinary, color: 'border-melonn-green text-melonn-green bg-melonn-green-50' },
    { label: 'Very Good', count: veryGood, color: 'border-blue-400 text-blue-600 bg-blue-50' },
    { label: 'Good', count: good, color: 'border-melonn-orange text-melonn-orange bg-melonn-orange-50' },
    { label: 'Low', count: low, color: 'border-gray-300 text-gray-500 bg-gray-50' },
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

// --- Categories ---
const CATEGORIES = [
  '', 'Accesorios', 'Alimentos', 'Alimentos refrigerados', 'Autopartes', 'Bebidas',
  'Cosmeticos-belleza', 'Deporte', 'Electronicos', 'Farmaceutica', 'Hogar',
  'Infantiles y Bebes', 'Joyeria/Bisuteria', 'Juguetes', 'Juguetes Sexuales',
  'Libros', 'Mascotas', 'Papeleria', 'Ropa', 'Salud y Bienestar',
  'Suplementos', 'Tecnologia', 'Textil Hogar', 'Zapatos',
];

// --- Main Page ---
export default function PotentialPage() {
  const [companies, setCompanies] = useState<CompanyListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [geography, setGeography] = useState('');
  const [category, setCategory] = useState('');
  const [potentialTier, setPotentialTier] = useState('');
  const [hideInHubSpot, setHideInHubSpot] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const limit = 25;

  const fetchCompanies = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getCompanies({
        page,
        limit,
        search,
        category,
        geography,
        potential_tier: potentialTier,
        sort_by: 'overall_potential_score',
        hide_in_hubspot: hideInHubSpot,
      });
      setCompanies(data.companies);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to load companies:', err);
    } finally {
      setIsLoading(false);
    }
  }, [page, search, category, geography, potentialTier, hideInHubSpot]);

  useEffect(() => { fetchCompanies(); }, [fetchCompanies]);
  useEffect(() => { setPage(1); }, [search, category, geography, potentialTier, hideInHubSpot]);

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="min-h-screen bg-melonn-surface">
      <Header />

      <main className="max-w-[1400px] mx-auto px-4 py-8">
        {/* Title */}
        <div className="mb-6">
          <h2 className="text-lg font-bold text-melonn-navy font-heading">Potential Dashboard</h2>
          <p className="text-sm text-gray-500">
            {total} {total === 1 ? 'empresa' : 'empresas'} rankeadas por potencial
          </p>
        </div>

        {/* Summary Cards */}
        <SummaryCards companies={companies} />

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
          <FilterSelect
            label="Pais"
            value={geography}
            onChange={setGeography}
            options={[
              { value: '', label: 'Todos los paises' },
              { value: 'COL', label: 'Colombia' },
              { value: 'MEX', label: 'Mexico' },
            ]}
          />
          <FilterSelect
            label="Categoria"
            value={category}
            onChange={setCategory}
            options={CATEGORIES.map((c) => ({ value: c, label: c || 'Todas las categorias' }))}
          />
          <FilterSelect
            label="Tier"
            value={potentialTier}
            onChange={setPotentialTier}
            options={[
              { value: '', label: 'Todos los tiers' },
              { value: 'Extraordinary', label: 'Extraordinary' },
              { value: 'Very Good', label: 'Very Good' },
              { value: 'Good', label: 'Good' },
              { value: 'Low', label: 'Low' },
            ]}
          />
          <label className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 bg-white text-sm cursor-pointer select-none">
            <input
              type="checkbox"
              checked={hideInHubSpot}
              onChange={(e) => setHideInHubSpot(e.target.checked)}
              className="rounded border-gray-300 text-melonn-purple focus:ring-melonn-purple/30"
            />
            <span className="text-gray-600 whitespace-nowrap">Ocultar en HubSpot</span>
          </label>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-melonn-purple-50 text-melonn-navy text-left">
                  <th className="px-3 py-2.5 font-semibold whitespace-nowrap">Empresa</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Tier</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Overall</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Size</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Fit</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Pais</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Categoria</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap text-right">P90 Orders</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap text-right">IG</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">CRM</th>
                  <th className="px-2 py-2.5 font-semibold whitespace-nowrap">Contacto</th>
                  <th className="px-3 py-2.5 font-semibold w-[80px]"></th>
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
                      {search || potentialTier ? 'Ninguna empresa coincide con los filtros' : 'No hay empresas con scores calculados'}
                    </td>
                  </tr>
                ) : (
                  companies.map((c) => (
                    <tr
                      key={c.id || c.domain}
                      className="hover:bg-melonn-purple-50/30 transition-colors cursor-pointer"
                      onClick={() => setSelectedDomain(c.domain || null)}
                    >
                      <td className="px-3 py-2.5">
                        <div className="font-medium text-melonn-navy truncate max-w-[160px]">
                          {c.company_name || c.domain}
                        </div>
                        <div className="text-gray-400 truncate max-w-[160px]">{c.domain}</div>
                      </td>
                      <td className="px-2 py-2.5 whitespace-nowrap">
                        <PotentialTierBadge tier={c.potential_tier} />
                      </td>
                      <td className="px-2 py-2.5 whitespace-nowrap">
                        <ScoreBar score={c.overall_potential_score} />
                      </td>
                      <td className="px-2 py-2.5 whitespace-nowrap">
                        <ScoreBar score={c.combined_size_score} />
                      </td>
                      <td className="px-2 py-2.5 whitespace-nowrap">
                        <ScoreBar score={c.fit_score} />
                      </td>
                      <td className="px-2 py-2.5 text-gray-600 whitespace-nowrap">{c.geography || '--'}</td>
                      <td className="px-2 py-2.5 text-gray-600 whitespace-nowrap truncate max-w-[100px]">
                        {c.category || '--'}
                      </td>
                      <td className="px-2 py-2.5 text-right font-semibold text-melonn-navy whitespace-nowrap">
                        {fmt(c.predicted_orders_p90)}
                      </td>
                      <td className="px-2 py-2.5 text-right text-gray-600 whitespace-nowrap">
                        {fmt(c.ig_followers)}
                      </td>
                      <td className="px-2 py-2.5 whitespace-nowrap">
                        {c.hubspot_company_id ? (
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-melonn-green-50 text-melonn-green">
                            {c.hubspot_deal_count ?? 0} deals
                          </span>
                        ) : (
                          <span className="text-gray-400">--</span>
                        )}
                      </td>
                      <td className="px-2 py-2.5">
                        <div className="text-gray-600 truncate max-w-[120px]">{c.contact_name || '--'}</div>
                      </td>
                      <td className="px-3 py-2.5">
                        <button
                          onClick={(e) => { e.stopPropagation(); setSelectedDomain(c.domain || null); }}
                          className="px-2.5 py-1 rounded-md bg-melonn-purple text-white
                                     hover:bg-melonn-purple/90 transition-colors whitespace-nowrap font-medium"
                        >
                          Ver
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
              <p className="text-sm text-gray-500">
                Mostrando {(page - 1) * limit + 1}--{Math.min(page * limit, total)} de {total}
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
