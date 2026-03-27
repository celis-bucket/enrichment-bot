'use client';

import type { EnrichmentV2Results } from '@/lib/types';
import { PotentialTierBadge } from '../PotentialTierBadge';
import { ScoreBar } from '../ScoreBar';

interface PotentialScoreCardV2Props {
  results: EnrichmentV2Results;
}

export function PotentialScoreCardV2({ results }: PotentialScoreCardV2Props) {
  if (results.overall_potential_score == null) {
    return null;
  }

  return (
    <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading">Potencial</h3>
        <PotentialTierBadge tier={results.potential_tier} />
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-melonn-navy/60">Overall</span>
          <ScoreBar score={results.overall_potential_score} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-melonn-navy/60">Ecommerce Size</span>
          <ScoreBar score={results.ecommerce_size_score} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-melonn-navy/60">Retail Size</span>
          <ScoreBar score={results.retail_size_score} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-melonn-navy/60">Combined Size</span>
          <ScoreBar score={results.combined_size_score} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-melonn-navy/60">Fit Score</span>
          <ScoreBar score={results.fit_score} />
        </div>
      </div>
    </div>
  );
}
