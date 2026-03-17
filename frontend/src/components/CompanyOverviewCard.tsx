'use client';

import { useState } from 'react';

interface CompanyOverviewCardProps {
  geography?: string | null;
  geographyConfidence?: number | null;
  platform?: string | null;
  platformConfidence?: number | null;
  category?: string | null;
  categoryConfidence?: number | null;
  categoryEvidence?: string | null;
  fulfillmentProvider?: string | null;
  fulfillmentConfidence?: number | null;
  toolCoveragePct?: number | null;
  totalRuntimeSec?: number | null;
  costEstimateUsd?: number | null;
}

function ConfidencePill({ value }: { value: number | null | undefined }) {
  if (value == null) return null;
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? 'text-melonn-green' : pct >= 40 ? 'text-melonn-orange' : 'text-red-500';
  return <span className={`text-xs font-medium ${color}`}>{pct}%</span>;
}

function InfoRow({ label, value, confidence }: {
  label: string;
  value?: string | null;
  confidence?: number | null;
}) {
  if (!value) return null;
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-melonn-purple-50/50 last:border-0">
      <span className="text-xs text-melonn-navy/50">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-melonn-navy">{value}</span>
        <ConfidencePill value={confidence} />
      </div>
    </div>
  );
}

const GEO_LABELS: Record<string, string> = {
  COL: 'Colombia',
  MEX: 'Mexico',
  UNKNOWN: 'Unknown',
};

export function CompanyOverviewCard({
  geography,
  geographyConfidence,
  platform,
  platformConfidence,
  category,
  categoryConfidence,
  categoryEvidence,
  fulfillmentProvider,
  fulfillmentConfidence,
  toolCoveragePct,
  totalRuntimeSec,
  costEstimateUsd,
}: CompanyOverviewCardProps) {
  const [showEvidence, setShowEvidence] = useState(false);

  const hasData = geography || platformConfidence != null || categoryConfidence != null
    || fulfillmentProvider || toolCoveragePct != null;

  if (!hasData) return null;

  return (
    <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-2">Company Overview</h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
        <div>
          <InfoRow label="Geography" value={GEO_LABELS[geography || ''] || geography} confidence={geographyConfidence} />
          <InfoRow label="Platform" value={platform} confidence={platformConfidence} />
          <InfoRow label="Category" value={category} confidence={categoryConfidence} />
        </div>
        <div>
          <InfoRow label="Fulfillment" value={fulfillmentProvider} confidence={fulfillmentConfidence} />
          {toolCoveragePct != null && (
            <div className="flex items-center justify-between py-1.5 border-b border-melonn-purple-50/50 last:border-0">
              <span className="text-xs text-melonn-navy/50">Tool coverage</span>
              <span className="text-sm font-medium text-melonn-navy">{Math.round(toolCoveragePct * 100)}%</span>
            </div>
          )}
          {totalRuntimeSec != null && (
            <div className="flex items-center justify-between py-1.5">
              <span className="text-xs text-melonn-navy/50">Runtime</span>
              <span className="text-xs text-melonn-navy/70">
                {totalRuntimeSec.toFixed(1)}s
                {costEstimateUsd != null && ` · $${costEstimateUsd.toFixed(2)}`}
              </span>
            </div>
          )}
        </div>
      </div>

      {categoryEvidence && (
        <div className="mt-2">
          <button
            onClick={() => setShowEvidence(!showEvidence)}
            className="text-xs text-melonn-navy/40 hover:text-melonn-navy/60 transition-colors"
          >
            {showEvidence ? '▾ Hide' : '▸ Show'} category evidence
          </button>
          {showEvidence && (
            <p className="mt-1 text-xs text-melonn-navy/60 bg-melonn-surface rounded-lg p-3">
              {categoryEvidence}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
