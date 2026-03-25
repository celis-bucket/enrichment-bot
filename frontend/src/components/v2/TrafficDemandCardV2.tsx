'use client';

import type { FeedbackItem } from '@/lib/types';
import { FeedbackPanel } from '../FeedbackPanel';

interface TrafficDemandCardV2Props {
  estimatedMonthlyVisits?: number | null;
  trafficConfidence?: number | null;
  signalsUsed?: string | null;
  brandDemandScore?: number | null;
  siteSerpCoverageScore?: number | null;
  googleConfidence?: number | null;
  domain?: string;
  feedback?: FeedbackItem[];
}

function formatVisits(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function getTrafficTier(visits: number): { label: string; emoji: string; color: string; bgColor: string } {
  if (visits >= 100_000) {
    return {
      label: 'Espectacular',
      emoji: '🔥',
      color: 'text-melonn-green',
      bgColor: 'bg-melonn-green-50',
    };
  }
  if (visits >= 50_000) {
    return {
      label: 'Buena',
      emoji: '👍',
      color: 'text-melonn-orange',
      bgColor: 'bg-melonn-orange-50',
    };
  }
  return {
    label: 'Regular',
    emoji: '📊',
    color: 'text-melonn-navy/60',
    bgColor: 'bg-melonn-surface',
  };
}

export function TrafficDemandCardV2({
  estimatedMonthlyVisits,
  domain = '',
  feedback = [],
}: TrafficDemandCardV2Props) {
  if (estimatedMonthlyVisits == null) {
    return (
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-2">Tráfico Web</h3>
        <p className="text-sm text-melonn-navy/40">No hay datos de tráfico disponibles</p>
        {domain && <FeedbackPanel domain={domain} section="traffic" existingFeedback={feedback} />}
      </div>
    );
  }

  const tier = getTrafficTier(estimatedMonthlyVisits);

  return (
    <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading">Tráfico Web</h3>
        <span className={`text-xs px-3 py-1 rounded-full font-medium ${tier.bgColor} ${tier.color}`}>
          {tier.emoji} {tier.label}
        </span>
      </div>

      <div className="text-center mb-3">
        <span className="text-3xl font-bold text-melonn-navy font-heading">
          {formatVisits(estimatedMonthlyVisits)}
        </span>
        <p className="text-xs text-melonn-navy/50 mt-1">Visitas mensuales estimadas</p>
      </div>

      {domain && <FeedbackPanel domain={domain} section="traffic" existingFeedback={feedback} />}
    </div>
  );
}
