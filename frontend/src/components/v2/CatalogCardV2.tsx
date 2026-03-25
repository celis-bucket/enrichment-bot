'use client';

import type { FeedbackItem } from '@/lib/types';
import { FeedbackPanel } from '../FeedbackPanel';

interface CatalogCardV2Props {
  productCount?: number | null;
  avgPrice?: number | null;
  priceRangeMin?: number | null;
  priceRangeMax?: number | null;
  currency?: string | null;
  domain?: string;
  feedback?: FeedbackItem[];
}

function formatPrice(value: number, currency: string): string {
  try {
    const locale = currency === 'COP' ? 'es-CO' : currency === 'MXN' ? 'es-MX' : 'en-US';
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  } catch {
    return `${currency} ${value.toLocaleString()}`;
  }
}

export function CatalogCardV2({ productCount, avgPrice, priceRangeMin, priceRangeMax, currency, domain = '', feedback = [] }: CatalogCardV2Props) {
  if (productCount == null) {
    return (
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-2">Catálogo de Productos</h3>
        <p className="text-sm text-melonn-navy/40">No hay datos de catálogo disponibles</p>
        {domain && <FeedbackPanel domain={domain} section="catalog" existingFeedback={feedback} />}
      </div>
    );
  }

  const scaleLabel =
    productCount >= 500 ? 'Catálogo grande'
    : productCount >= 50 ? 'Catálogo en crecimiento'
    : 'Catálogo pequeño';
  const scaleColor =
    productCount >= 500 ? 'bg-melonn-green-50 text-melonn-green'
    : productCount >= 50 ? 'bg-melonn-orange-50 text-melonn-orange'
    : 'bg-melonn-surface text-melonn-navy/50';

  const cur = currency || 'COP';

  return (
    <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading">Catálogo de Productos</h3>
        <span className={`text-xs px-3 py-1 rounded-full font-medium ${scaleColor}`}>
          {scaleLabel}
        </span>
      </div>

      <div className="text-center mb-3">
        <span className="text-3xl font-bold text-melonn-navy font-heading">
          {productCount.toLocaleString()}
        </span>
        <p className="text-xs text-melonn-navy/50 mt-1">Productos</p>
      </div>

      <div className="space-y-1.5">
        {avgPrice != null && (
          <div className="flex justify-between text-sm">
            <span className="text-melonn-navy/50">Precio promedio</span>
            <span className="font-medium text-melonn-navy">{formatPrice(avgPrice, cur)}</span>
          </div>
        )}
        {priceRangeMin != null && priceRangeMax != null && (
          <div className="flex justify-between text-sm">
            <span className="text-melonn-navy/50">Rango de precios</span>
            <span className="font-medium text-melonn-navy">
              {formatPrice(priceRangeMin, cur)} – {formatPrice(priceRangeMax, cur)}
            </span>
          </div>
        )}
      </div>

      {domain && <FeedbackPanel domain={domain} section="catalog" existingFeedback={feedback} />}
    </div>
  );
}
