'use client';

import { PlatformInfo } from '@/lib/types';

interface PlatformCardProps {
  platform: PlatformInfo;
}

export function PlatformCard({ platform }: PlatformCardProps) {
  const confidencePercent = Math.round(platform.confidence * 100);

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Platform</h3>
      <div className="mt-2">
        <p className="text-2xl font-bold text-gray-900">{platform.name}</p>
        <div className="mt-2 flex items-center gap-2">
          <div className="flex-1 bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all"
              style={{ width: `${confidencePercent}%` }}
            />
          </div>
          <span className="text-sm text-gray-600">{confidencePercent}%</span>
        </div>
        {platform.version && (
          <p className="mt-2 text-sm text-gray-500">Version: {platform.version}</p>
        )}
      </div>
    </div>
  );
}
