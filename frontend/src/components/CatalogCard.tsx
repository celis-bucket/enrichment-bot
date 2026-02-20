'use client';

import { CatalogInfo } from '@/lib/types';

interface CatalogCardProps {
  catalog: CatalogInfo;
}

function formatPrice(price: number, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
    maximumFractionDigits: 0,
  }).format(price);
}

export function CatalogCard({ catalog }: CatalogCardProps) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Product Catalog</h3>
      <div className="mt-2">
        <p className="text-2xl font-bold text-gray-900">
          {catalog.product_count.toLocaleString()} <span className="text-base font-normal text-gray-500">products</span>
        </p>
        <div className="mt-3 grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-500">Average Price</p>
            <p className="text-lg font-semibold text-gray-900">
              {formatPrice(catalog.avg_price, catalog.currency)}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Price Range</p>
            <p className="text-lg font-semibold text-gray-900">
              {formatPrice(catalog.price_range.min, catalog.currency)} - {formatPrice(catalog.price_range.max, catalog.currency)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
