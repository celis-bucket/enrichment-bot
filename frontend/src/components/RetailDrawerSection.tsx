'use client';

import type { EnrichmentV2Results } from '@/lib/types';

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
  { key: 'on_tiktok_shop' as const, label: 'TikTok Shop' },
];

function Badge({ value, label }: { value?: boolean | null; label: string }) {
  if (value == null) return null;
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] px-2 py-0.5 rounded-full font-medium ${
      value ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-400'
    }`}>
      {value ? '✓' : '✗'} {label}
    </span>
  );
}

export function RetailDrawerSection({ data }: { data: EnrichmentV2Results }) {
  const hasAny = data.has_distributors != null
    || data.has_own_stores != null
    || data.has_multibrand_stores != null
    || data.on_mercadolibre != null;

  if (!hasAny) return null;

  const marketplaces = data.geography === 'MEX' ? MEX_MARKETPLACES : COL_MARKETPLACES;

  return (
    <div className="mb-4">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-melonn-purple mb-1">Canales Retail</h4>
      <div className="bg-gray-50 rounded-lg px-3 py-2 space-y-2.5">
        {/* Distribuidores */}
        <div className="flex justify-between items-center py-1 border-b border-gray-100">
          <span className="text-xs text-gray-400">Distribuidores</span>
          <Badge value={data.has_distributors} label={data.has_distributors ? 'Si' : 'No'} />
        </div>

        {/* Tiendas Propias */}
        <div className="flex justify-between items-center py-1 border-b border-gray-100">
          <span className="text-xs text-gray-400">Tiendas Propias</span>
          <Badge value={data.has_own_stores} label={data.has_own_stores ? 'Si' : 'No'} />
        </div>

        {/* Multimarca */}
        {data.has_multibrand_stores != null && (
          <div className="py-1 border-b border-gray-100">
            <span className="text-xs text-gray-400">Multimarca</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {data.multibrand_store_names?.length ? (
                data.multibrand_store_names.map((s) => (
                  <span key={s} className="text-[10px] px-2 py-0.5 bg-green-50 text-green-600 rounded-full font-medium">
                    ✓ {s}
                  </span>
                ))
              ) : (
                <Badge value={data.has_multibrand_stores} label={data.has_multibrand_stores ? 'Si' : 'No'} />
              )}
            </div>
          </div>
        )}

        {/* Marketplaces */}
        <div className="py-1">
          <span className="text-xs text-gray-400">Marketplaces</span>
          <div className="flex flex-wrap gap-1 mt-1">
            {marketplaces.map(({ key, label }) => (
              <Badge key={key} value={data[key]} label={label} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
