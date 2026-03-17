'use client';

import { useState, useEffect, useCallback } from 'react';
import { Header } from '@/components/Header';
import { getCompanies } from '@/lib/api';
import type { CompanyListItem } from '@/lib/types';

function formatNumber(n: number | null | undefined): string {
  if (n == null) return '—';
  return n.toLocaleString();
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
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

export default function HistoryPage() {
  const [companies, setCompanies] = useState<CompanyListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);
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

  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies]);

  // Reset to page 1 when search changes
  useEffect(() => {
    setPage(1);
  }, [search]);

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="min-h-screen bg-melonn-surface">
      <Header />

      <main className="max-w-6xl mx-auto px-6 py-8">
        {/* Search & Stats */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-bold text-melonn-navy font-heading">
              Enriched Companies
            </h2>
            <p className="text-sm text-gray-500">
              {total} {total === 1 ? 'company' : 'companies'} in database
            </p>
          </div>
          <input
            type="text"
            placeholder="Search by name or domain..."
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
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-melonn-purple-50 text-melonn-navy text-left">
                  <th className="px-4 py-3 font-semibold">Company</th>
                  <th className="px-4 py-3 font-semibold">Category</th>
                  <th className="px-4 py-3 font-semibold">Platform</th>
                  <th className="px-4 py-3 font-semibold text-right">IG Followers</th>
                  <th className="px-4 py-3 font-semibold text-right">Meta Ads</th>
                  <th className="px-4 py-3 font-semibold text-right">Est. Orders</th>
                  <th className="px-4 py-3 font-semibold">Confidence</th>
                  <th className="px-4 py-3 font-semibold">Contact</th>
                  <th className="px-4 py-3 font-semibold">Analyzed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {isLoading ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-12 text-center text-gray-400">
                      Loading...
                    </td>
                  </tr>
                ) : companies.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-12 text-center text-gray-400">
                      {search ? 'No companies match your search' : 'No companies enriched yet'}
                    </td>
                  </tr>
                ) : (
                  companies.map((c) => (
                    <tr key={c.id || c.domain} className="hover:bg-melonn-purple-50/30 transition-colors">
                      <td className="px-4 py-3">
                        <div className="font-medium text-melonn-navy">
                          {c.company_name || c.domain}
                        </div>
                        <div className="text-xs text-gray-400">{c.domain}</div>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{c.category || '—'}</td>
                      <td className="px-4 py-3 text-gray-600">{c.platform || '—'}</td>
                      <td className="px-4 py-3 text-right text-gray-600">
                        {formatNumber(c.ig_followers)}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600">
                        {c.meta_active_ads_count != null ? c.meta_active_ads_count : '—'}
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-melonn-navy">
                        {formatNumber(c.predicted_orders_p50)}
                      </td>
                      <td className="px-4 py-3">
                        <ConfidenceBadge level={c.prediction_confidence} />
                      </td>
                      <td className="px-4 py-3">
                        <div className="text-gray-600 truncate max-w-[140px]">
                          {c.contact_name || '—'}
                        </div>
                        {c.contact_email && (
                          <div className="text-xs text-gray-400 truncate max-w-[140px]">
                            {c.contact_email}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {formatDate(c.updated_at)}
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
                Showing {(page - 1) * limit + 1}–{Math.min(page * limit, total)} of {total}
              </p>
              <div className="flex gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1 rounded-md text-sm border border-gray-200 disabled:opacity-40
                             hover:bg-melonn-purple-50 transition-colors"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1 rounded-md text-sm border border-gray-200 disabled:opacity-40
                             hover:bg-melonn-purple-50 transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
