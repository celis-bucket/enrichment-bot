'use client';

import type { EnrichmentV2Results, FeedbackItem } from '@/lib/types';
import { FeedbackPanel } from '../FeedbackPanel';

interface RetailChannelsCardV2Props {
  results: EnrichmentV2Results;
  domain?: string;
  feedback?: FeedbackItem[];
}

function BoolBadge({ value, label }: { value?: boolean | null; label: string }) {
  if (value == null) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full font-medium ${
        value
          ? 'bg-melonn-green-50 text-melonn-green'
          : 'bg-gray-100 text-gray-400'
      }`}
    >
      {value ? '✓' : '✗'} {label}
    </span>
  );
}

const COL_MARKETPLACES = [
  { key: 'on_mercadolibre' as const, label: 'MercadoLibre' },
  { key: 'on_amazon' as const, label: 'Amazon' },
  { key: 'on_rappi' as const, label: 'Rappi' },
];

const MEX_MARKETPLACES = [
  { key: 'on_mercadolibre' as const, label: 'MercadoLibre' },
  { key: 'on_amazon' as const, label: 'Amazon' },
  { key: 'on_walmart' as const, label: 'Walmart' },
  { key: 'on_liverpool' as const, label: 'Liverpool' },
  { key: 'on_coppel' as const, label: 'Coppel' },
];

export function RetailChannelsCardV2({ results, domain = '', feedback = [] }: RetailChannelsCardV2Props) {
  const hasAnyData = results.has_distributors != null
    || results.has_own_stores != null
    || results.has_multibrand_stores != null
    || results.on_mercadolibre != null;

  if (!hasAnyData) {
    return (
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-2">Canales Retail</h3>
        <p className="text-sm text-melonn-navy/40">No hay datos de retail disponibles</p>
      </div>
    );
  }

  const marketplaces = results.geography === 'MEX' ? MEX_MARKETPLACES : COL_MARKETPLACES;
  const storeCount = results.geography === 'MEX'
    ? results.own_store_count_mex
    : results.own_store_count_col;

  return (
    <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading">Canales Retail</h3>
        {results.retail_confidence != null && (
          <span className="text-xs text-melonn-navy/40">
            Confianza: {Math.round(results.retail_confidence * 100)}%
          </span>
        )}
      </div>

      <div className="space-y-4">
        {/* Distribuidores */}
        <div>
          <p className="text-xs text-melonn-navy/50 mb-1.5">Distribuidores / Mayoristas</p>
          <BoolBadge value={results.has_distributors} label="Distribuye" />
        </div>

        {/* Tiendas Propias */}
        <div>
          <p className="text-xs text-melonn-navy/50 mb-1.5">Tiendas Propias</p>
          <div className="flex items-center gap-2 flex-wrap">
            <BoolBadge value={results.has_own_stores} label="Tiene tiendas" />
            {results.has_own_stores && storeCount != null && storeCount > 0 && (
              <span className="text-xs text-melonn-navy/60 font-medium">
                {storeCount} tienda{storeCount !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>

        {/* Tiendas Multimarca */}
        <div>
          <p className="text-xs text-melonn-navy/50 mb-1.5">Tiendas Multimarca</p>
          <div className="flex flex-wrap gap-1.5">
            <BoolBadge value={results.has_multibrand_stores} label="Presente" />
            {results.multibrand_store_names?.map((store) => (
              <span
                key={store}
                className="text-xs px-2.5 py-1 bg-melonn-purple-50 text-melonn-purple rounded-full font-medium"
              >
                {store}
              </span>
            ))}
          </div>
        </div>

        {/* Marketplaces */}
        <div>
          <p className="text-xs text-melonn-navy/50 mb-1.5">Marketplaces</p>
          <div className="flex flex-wrap gap-1.5">
            {marketplaces.map(({ key, label }) => (
              <BoolBadge key={key} value={results[key]} label={label} />
            ))}
          </div>
        </div>
      </div>

      {domain && <FeedbackPanel domain={domain} section="retail" existingFeedback={feedback} />}
    </div>
  );
}
