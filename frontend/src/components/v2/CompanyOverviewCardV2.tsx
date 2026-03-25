'use client';

import { useState } from 'react';
import type { FeedbackItem } from '@/lib/types';
import { FeedbackPanel } from '../FeedbackPanel';

interface CompanyOverviewCardV2Props {
  geography?: string | null;
  geographyConfidence?: number | null;
  platform?: string | null;
  platformConfidence?: number | null;
  category?: string | null;
  categoryConfidence?: number | null;
  categoryEvidence?: string | null;
  toolCoveragePct?: number | null;
  totalRuntimeSec?: number | null;
  costEstimateUsd?: number | null;
  domain?: string;
  feedback?: FeedbackItem[];
}

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-melonn-purple-50/50 last:border-0">
      <span className="text-xs text-melonn-navy/50">{label}</span>
      <span className="text-sm font-medium text-melonn-navy">{value}</span>
    </div>
  );
}

const GEO_LABELS: Record<string, string> = {
  COL: 'Colombia',
  MEX: 'Mexico',
  UNKNOWN: 'Desconocido',
};

export function CompanyOverviewCardV2({
  geography,
  platform,
  category,
  categoryEvidence,
  toolCoveragePct,
  totalRuntimeSec,
  costEstimateUsd,
  domain = '',
  feedback = [],
}: CompanyOverviewCardV2Props) {
  const [showEvidence, setShowEvidence] = useState(false);

  const hasData = geography || platform || category || toolCoveragePct != null;

  if (!hasData) return null;

  return (
    <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-2">Resumen de la Empresa</h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
        <div>
          <InfoRow label="País" value={GEO_LABELS[geography || ''] || geography} />
          <InfoRow label="Plataforma" value={platform} />
          <InfoRow label="Categoría" value={category} />
        </div>
        <div>
          {toolCoveragePct != null && (
            <div className="flex items-center justify-between py-1.5 border-b border-melonn-purple-50/50 last:border-0">
              <span className="text-xs text-melonn-navy/50">Cobertura de datos</span>
              <span className="text-sm font-medium text-melonn-navy">{Math.round(toolCoveragePct * 100)}%</span>
            </div>
          )}
          {totalRuntimeSec != null && (
            <div className="flex items-center justify-between py-1.5">
              <span className="text-xs text-melonn-navy/50">Tiempo de ejecución</span>
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
            {showEvidence ? '▾ Ocultar' : '▸ Ver'} evidencia de categoría
          </button>
          {showEvidence && (
            <p className="mt-1 text-xs text-melonn-navy/60 bg-melonn-surface rounded-lg p-3">
              {categoryEvidence}
            </p>
          )}
        </div>
      )}

      {domain && <FeedbackPanel domain={domain} section="overview" existingFeedback={feedback} />}
    </div>
  );
}
