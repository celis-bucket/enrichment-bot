'use client';

import { useState, useEffect, useCallback } from 'react';
import { Header } from '@/components/Header';
import { getTikTokWeekly, getTikTokShopHistory } from '@/lib/api';
import type { TikTokShopWeeklyItem, TikTokShopHistoryItem } from '@/lib/types';

function formatMXN(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toLocaleString()}`;
}

function formatNum(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
}

function WowCell({ value, isNew }: { value?: number | null; isNew: boolean }) {
  if (isNew) {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-melonn-cyan-50 text-melonn-cyan">
        NUEVO
      </span>
    );
  }
  if (value == null) return <span className="text-melonn-navy/30">-</span>;
  const isUp = value > 0;
  const color = isUp ? 'text-green-600' : value < 0 ? 'text-red-500' : 'text-melonn-navy/50';
  const arrow = isUp ? '\u2191' : value < 0 ? '\u2193' : '';
  return <span className={`text-sm font-medium ${color}`}>{arrow}{Math.abs(value).toFixed(1)}%</span>;
}

const FILTER_TABS = [
  { key: 'all', label: 'Todas' },
  { key: 'new', label: 'Nuevas' },
  { key: 'rising', label: 'Suben' },
  { key: 'falling', label: 'Bajan' },
];

const SORT_OPTIONS = [
  { key: 'gmv', label: 'Ingresos' },
  { key: 'sales_count', label: 'Ventas' },
  { key: 'wow_sales', label: 'Crecimiento ventas' },
  { key: 'wow_gmv', label: 'Crecimiento ingresos' },
];

export default function TikTokPage() {
  const [shops, setShops] = useState<TikTokShopWeeklyItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalNew, setTotalNew] = useState(0);
  const [weekStart, setWeekStart] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [sortBy, setSortBy] = useState('gmv');
  const [loading, setLoading] = useState(true);
  const [selectedShop, setSelectedShop] = useState<TikTokShopWeeklyItem | null>(null);
  const [shopHistory, setShopHistory] = useState<TikTokShopHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const limit = 50;

  const fetchData = useCallback(async () => {
    setLoading(true);
    const result = await getTikTokWeekly({ page, limit, search, filter, sort_by: sortBy });
    setShops(result.shops);
    setTotal(result.total);
    setTotalNew(result.total_new);
    setWeekStart(result.week_start || null);
    setLoading(false);
  }, [page, search, filter, sortBy]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Debounced search
  const [searchInput, setSearchInput] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  async function openShopDetail(shop: TikTokShopWeeklyItem) {
    setSelectedShop(shop);
    setHistoryLoading(true);
    try {
      const result = await getTikTokShopHistory(shop.shop_name);
      setShopHistory(result.history);
    } catch {
      setShopHistory([]);
    }
    setHistoryLoading(false);
  }

  const topGmvShop = shops.length > 0 && filter === 'all' ? shops[0] : null;
  const totalPages = Math.ceil(total / limit);

  return (
    <div className="min-h-screen bg-melonn-surface">
      <Header />
      <main className="max-w-6xl mx-auto px-6 py-6">
        {/* Title */}
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-melonn-navy font-heading">TikTok Shop Mexico</h2>
          <p className="text-sm text-melonn-navy/50 mt-1">
            Ranking semanal de tiendas TikTok Shop
            {weekStart && <span> &middot; Semana del {weekStart}</span>}
          </p>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-4 text-center">
            <p className="text-xs text-melonn-navy/50 mb-1">Total tiendas</p>
            <p className="text-2xl font-bold text-melonn-navy font-heading">{total.toLocaleString()}</p>
          </div>
          <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-4 text-center">
            <p className="text-xs text-melonn-navy/50 mb-1">Nuevas esta semana</p>
            <p className="text-2xl font-bold text-melonn-cyan font-heading">{totalNew.toLocaleString()}</p>
          </div>
          <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-4 text-center">
            <p className="text-xs text-melonn-navy/50 mb-1">Top ingresos</p>
            <p className="text-lg font-bold text-melonn-navy font-heading">
              {topGmvShop ? topGmvShop.shop_name : '-'}
            </p>
            {topGmvShop?.gmv != null && (
              <p className="text-sm text-melonn-navy/60">{formatMXN(topGmvShop.gmv)}</p>
            )}
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-4 mb-4">
          <div className="flex flex-wrap items-center gap-3">
            {/* Search */}
            <input
              type="text"
              placeholder="Buscar tienda..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="flex-1 min-w-[200px] px-3 py-2 text-sm border border-melonn-purple-50 rounded-lg focus:outline-none focus:ring-2 focus:ring-melonn-purple/30"
            />

            {/* Filter tabs */}
            <div className="flex gap-1">
              {FILTER_TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => { setFilter(tab.key); setPage(1); }}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    filter === tab.key
                      ? 'bg-melonn-purple text-white'
                      : 'bg-melonn-surface text-melonn-navy/60 hover:bg-melonn-purple-50'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Sort */}
            <select
              value={sortBy}
              onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
              className="px-3 py-2 text-xs border border-melonn-purple-50 rounded-lg focus:outline-none focus:ring-2 focus:ring-melonn-purple/30"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.key} value={opt.key}>Ordenar: {opt.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-melonn-navy/30 animate-pulse">Cargando...</div>
          ) : shops.length === 0 ? (
            <div className="p-8 text-center text-melonn-navy/40">No se encontraron tiendas</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-melonn-purple-50 text-left">
                    <th className="px-4 py-3 text-xs font-medium text-melonn-navy/50 w-10">#</th>
                    <th className="px-4 py-3 text-xs font-medium text-melonn-navy/50">Tienda</th>
                    <th className="px-4 py-3 text-xs font-medium text-melonn-navy/50">Categoria</th>
                    <th className="px-4 py-3 text-xs font-medium text-melonn-navy/50 text-right">Ventas</th>
                    <th className="px-4 py-3 text-xs font-medium text-melonn-navy/50 text-right">Ingresos</th>
                    <th className="px-4 py-3 text-xs font-medium text-melonn-navy/50 text-right">Productos</th>
                    <th className="px-4 py-3 text-xs font-medium text-melonn-navy/50 text-center">Cambio WoW</th>
                    <th className="px-4 py-3 text-xs font-medium text-melonn-navy/50">Empresa</th>
                  </tr>
                </thead>
                <tbody>
                  {shops.map((shop, i) => (
                    <tr
                      key={shop.shop_name}
                      className="border-b border-melonn-purple-50/50 hover:bg-melonn-surface/50 cursor-pointer transition-colors"
                      onClick={() => openShopDetail(shop)}
                    >
                      <td className="px-4 py-3 text-melonn-navy/40">{(page - 1) * limit + i + 1}</td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-melonn-navy">{shop.shop_name}</p>
                        {shop.company_name && shop.company_name !== shop.shop_name && (
                          <p className="text-xs text-melonn-navy/40">{shop.company_name}</p>
                        )}
                      </td>
                      <td className="px-4 py-3 text-melonn-navy/60 text-xs">{shop.category || '-'}</td>
                      <td className="px-4 py-3 text-right font-medium text-melonn-navy">
                        {shop.sales_count != null ? formatNum(shop.sales_count) : '-'}
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-melonn-navy">
                        {shop.gmv != null ? formatMXN(shop.gmv) : '-'}
                      </td>
                      <td className="px-4 py-3 text-right text-melonn-navy/60">
                        {shop.products != null ? shop.products.toLocaleString() : '-'}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <WowCell value={shop.wow_sales_pct} isNew={shop.is_new} />
                      </td>
                      <td className="px-4 py-3">
                        {shop.matched_domain ? (
                          <a
                            href={`/analyze-v2?domain=${shop.matched_domain}`}
                            onClick={(e) => e.stopPropagation()}
                            className="text-xs text-melonn-purple hover:text-melonn-purple-light"
                          >
                            {shop.matched_domain}
                          </a>
                        ) : (
                          <span className="text-xs text-melonn-navy/20">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-melonn-purple-50">
              <p className="text-xs text-melonn-navy/40">
                {total.toLocaleString()} tiendas
              </p>
              <div className="flex gap-1">
                <button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1 text-xs rounded-md bg-melonn-surface text-melonn-navy/60 hover:bg-melonn-purple-50 disabled:opacity-30"
                >
                  Anterior
                </button>
                <span className="px-3 py-1 text-xs text-melonn-navy/50">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page >= totalPages}
                  className="px-3 py-1 text-xs rounded-md bg-melonn-surface text-melonn-navy/60 hover:bg-melonn-purple-50 disabled:opacity-30"
                >
                  Siguiente
                </button>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Detail Drawer */}
      {selectedShop && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/20" onClick={() => setSelectedShop(null)} />
          <div className="relative w-full max-w-md bg-white shadow-xl overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-melonn-purple-50 px-5 py-4 flex items-center justify-between">
              <h3 className="text-lg font-bold text-melonn-navy font-heading">{selectedShop.shop_name}</h3>
              <button
                onClick={() => setSelectedShop(null)}
                className="text-melonn-navy/30 hover:text-melonn-navy text-xl"
              >
                &times;
              </button>
            </div>

            <div className="p-5 space-y-5">
              {/* Shop info */}
              <div className="space-y-2">
                {selectedShop.company_name && (
                  <p className="text-sm text-melonn-navy/60">
                    Empresa: <span className="text-melonn-navy font-medium">{selectedShop.company_name}</span>
                  </p>
                )}
                {selectedShop.category && (
                  <p className="text-sm text-melonn-navy/60">
                    Categoria: <span className="text-melonn-navy font-medium">{selectedShop.category}</span>
                  </p>
                )}
                {selectedShop.rating != null && selectedShop.rating > 0 && (
                  <p className="text-sm text-melonn-navy/60">
                    Rating: <span className="text-melonn-navy font-medium">{selectedShop.rating.toFixed(1)}</span>
                  </p>
                )}
              </div>

              {/* Current metrics */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-melonn-surface rounded-xl p-3 text-center">
                  <p className="text-xs text-melonn-navy/50 mb-1">Ventas</p>
                  <p className="text-lg font-bold text-melonn-navy font-heading">
                    {selectedShop.sales_count != null ? formatNum(selectedShop.sales_count) : '-'}
                  </p>
                  <WowCell value={selectedShop.wow_sales_pct} isNew={selectedShop.is_new} />
                </div>
                <div className="bg-melonn-surface rounded-xl p-3 text-center">
                  <p className="text-xs text-melonn-navy/50 mb-1">Ingresos</p>
                  <p className="text-lg font-bold text-melonn-navy font-heading">
                    {selectedShop.gmv != null ? formatMXN(selectedShop.gmv) : '-'}
                  </p>
                  <WowCell value={selectedShop.wow_gmv_pct} isNew={selectedShop.is_new} />
                </div>
                <div className="bg-melonn-surface rounded-xl p-3 text-center">
                  <p className="text-xs text-melonn-navy/50 mb-1">Productos</p>
                  <p className="text-lg font-bold text-melonn-navy font-heading">
                    {selectedShop.products?.toLocaleString() || '-'}
                  </p>
                </div>
                <div className="bg-melonn-surface rounded-xl p-3 text-center">
                  <p className="text-xs text-melonn-navy/50 mb-1">Influencers</p>
                  <p className="text-lg font-bold text-melonn-navy font-heading">
                    {selectedShop.influencers != null ? formatNum(selectedShop.influencers) : '-'}
                  </p>
                </div>
              </div>

              {/* History table */}
              <div>
                <h4 className="text-sm font-semibold text-melonn-navy font-heading mb-2">Historial semanal</h4>
                {historyLoading ? (
                  <p className="text-sm text-melonn-navy/30 animate-pulse">Cargando...</p>
                ) : shopHistory.length === 0 ? (
                  <p className="text-sm text-melonn-navy/40">Sin historial</p>
                ) : (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-melonn-purple-50 text-left">
                        <th className="py-2 text-melonn-navy/50">Semana</th>
                        <th className="py-2 text-right text-melonn-navy/50">Ventas</th>
                        <th className="py-2 text-right text-melonn-navy/50">Ingresos</th>
                        <th className="py-2 text-right text-melonn-navy/50">Productos</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shopHistory.map((h) => (
                        <tr key={h.week_start} className="border-b border-melonn-purple-50/30">
                          <td className="py-2 text-melonn-navy/70">{h.week_start}</td>
                          <td className="py-2 text-right text-melonn-navy">
                            {h.sales_count != null ? formatNum(h.sales_count) : '-'}
                          </td>
                          <td className="py-2 text-right text-melonn-navy">
                            {h.gmv != null ? formatMXN(h.gmv) : '-'}
                          </td>
                          <td className="py-2 text-right text-melonn-navy/60">
                            {h.products?.toLocaleString() || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Links */}
              <div className="space-y-2">
                {selectedShop.fastmoss_url && (
                  <a
                    href={selectedShop.fastmoss_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-sm text-melonn-purple hover:text-melonn-purple-light"
                  >
                    Ver en FastMoss
                  </a>
                )}
                {selectedShop.matched_domain && (
                  <a
                    href={`/analyze-v2?domain=${selectedShop.matched_domain}`}
                    className="block text-sm text-melonn-purple hover:text-melonn-purple-light"
                  >
                    Ver enrichment: {selectedShop.matched_domain}
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
