'use client';

import { GeographyInfo } from '@/lib/types';

interface GeographyCardProps {
  geography: GeographyInfo;
}

export function GeographyCard({ geography }: GeographyCardProps) {
  const confidencePercent = Math.round(geography.confidence * 100);

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Geography</h3>
      <div className="mt-2">
        <p className="text-2xl font-bold text-gray-900">
          {geography.primary_country || geography.countries[0] || 'Unknown'}
        </p>
        {geography.countries.length > 1 && (
          <p className="mt-1 text-sm text-gray-500">
            Also operates in: {geography.countries.filter(c => c !== geography.primary_country).join(', ')}
          </p>
        )}
        <div className="mt-2 flex items-center gap-2">
          <div className="flex-1 bg-gray-200 rounded-full h-2">
            <div
              className="bg-green-600 h-2 rounded-full transition-all"
              style={{ width: `${confidencePercent}%` }}
            />
          </div>
          <span className="text-sm text-gray-600">{confidencePercent}%</span>
        </div>
      </div>
    </div>
  );
}
