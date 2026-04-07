'use client';

import { useState, useEffect } from 'react';
import type { FeedbackItem, TikTokShopForDomainResponse } from '@/lib/types';
import { getTikTokShopForDomain } from '@/lib/api';
import { FeedbackPanel } from '../FeedbackPanel';

interface TikTokShopCardV2Props {
  domain: string;
  geography?: string | null;
  feedback?: FeedbackItem[];
}

function formatMXN(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toLocaleString()}`;
}

function formatNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
}

function WowBadge({ value }: { value?: number | null }) {
  if (value == null) return null;
  const isUp = value > 0;
  const color = isUp ? 'text-green-600' : 'text-red-500';
  const arrow = isUp ? '\u2191' : '\u2193';
  return (
    <span className={`text-xs font-medium ${color}`}>
      {arrow} {Math.abs(value).toFixed(1)}%
    </span>
  );
}

export function TikTokShopCardV2({ domain, geography, feedback = [] }: TikTokShopCardV2Props) {
  const [data, setData] = useState<TikTokShopForDomainResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!domain || geography !== 'MEX') {
      setLoading(false);
      return;
    }
    getTikTokShopForDomain(domain)
      .then(setData)
      .finally(() => setLoading(false));
  }, [domain, geography]);

  // Only show for MEX
  if (geography !== 'MEX') return null;

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-2">TikTok Shop</h3>
        <p className="text-sm text-melonn-navy/30 animate-pulse">Cargando...</p>
      </div>
    );
  }

  if (!data?.has_data) {
    return (
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-2">TikTok Shop</h3>
        <p className="text-sm text-melonn-navy/40">No hay datos de TikTok Shop</p>
        {domain && <FeedbackPanel domain={domain} section="tiktok_shop" existingFeedback={feedback} />}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading">TikTok Shop</h3>
        {data.rating != null && data.rating > 0 && (
          <span className="text-xs px-3 py-1 rounded-full font-medium bg-melonn-green-50 text-melonn-green">
            {data.rating.toFixed(1)} rating
          </span>
        )}
      </div>

      {/* Shop name */}
      {data.shop_name && (
        <p className="text-sm text-melonn-navy/70 mb-3">
          Tienda: <span className="font-medium text-melonn-navy">{data.shop_name}</span>
        </p>
      )}

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        {/* Sales */}
        <div className="bg-melonn-surface rounded-xl p-3 text-center">
          <p className="text-xs text-melonn-navy/50 mb-1">Ventas</p>
          <p className="text-lg font-bold text-melonn-navy font-heading">
            {data.sales_count != null ? formatNumber(data.sales_count) : '-'}
          </p>
          <WowBadge value={data.wow_sales_pct} />
        </div>

        {/* GMV */}
        <div className="bg-melonn-surface rounded-xl p-3 text-center">
          <p className="text-xs text-melonn-navy/50 mb-1">Ingresos</p>
          <p className="text-lg font-bold text-melonn-navy font-heading">
            {data.gmv != null ? formatMXN(data.gmv) : '-'}
          </p>
          <WowBadge value={data.wow_gmv_pct} />
        </div>

        {/* Products */}
        <div className="bg-melonn-surface rounded-xl p-3 text-center">
          <p className="text-xs text-melonn-navy/50 mb-1">Productos</p>
          <p className="text-lg font-bold text-melonn-navy font-heading">
            {data.products != null ? data.products.toLocaleString() : '-'}
          </p>
        </div>

        {/* Influencers */}
        <div className="bg-melonn-surface rounded-xl p-3 text-center">
          <p className="text-xs text-melonn-navy/50 mb-1">Influencers</p>
          <p className="text-lg font-bold text-melonn-navy font-heading">
            {data.influencers != null ? formatNumber(data.influencers) : '-'}
          </p>
        </div>
      </div>

      {/* Week info */}
      {data.week_start && (
        <p className="text-xs text-melonn-navy/30 text-center mb-2">
          Semana del {data.week_start}
        </p>
      )}

      {/* FastMoss link */}
      {data.fastmoss_url && (
        <a
          href={data.fastmoss_url}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full text-center text-sm text-melonn-purple hover:text-melonn-purple-light transition-colors py-1"
        >
          Ver en FastMoss
        </a>
      )}

      {domain && <FeedbackPanel domain={domain} section="tiktok_shop" existingFeedback={feedback} />}
    </div>
  );
}
