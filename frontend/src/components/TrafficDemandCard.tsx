'use client';

interface TrafficDemandCardProps {
  estimatedMonthlyVisits?: number | null;
  trafficConfidence?: number | null;
  signalsUsed?: string | null;
  brandDemandScore?: number | null;
  siteSerpCoverageScore?: number | null;
  googleConfidence?: number | null;
}

function formatVisits(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function ConfidenceBadge({ value }: { value: number | null | undefined }) {
  if (value == null) return null;
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? 'bg-melonn-green-50 text-melonn-green'
    : pct >= 40 ? 'bg-melonn-orange-50 text-melonn-orange'
    : 'bg-red-50 text-red-600';
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>
      {pct}%
    </span>
  );
}

function ScoreBar({ score, label }: { score: number; label: string }) {
  const pct = Math.round(score * 100);
  const barColor = pct >= 70 ? 'bg-melonn-green' : pct >= 40 ? 'bg-melonn-orange' : 'bg-red-400';

  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-melonn-navy/50">{label}</span>
        <span className="font-medium text-melonn-navy">{pct}/100</span>
      </div>
      <div className="h-1.5 bg-melonn-purple-100 rounded-full">
        <div className={`h-1.5 rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function TrafficDemandCard({
  estimatedMonthlyVisits,
  trafficConfidence,
  signalsUsed,
  brandDemandScore,
  siteSerpCoverageScore,
  googleConfidence,
}: TrafficDemandCardProps) {
  const hasTraffic = estimatedMonthlyVisits != null;
  const hasDemand = brandDemandScore != null || siteSerpCoverageScore != null;

  if (!hasTraffic && !hasDemand) {
    return (
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-2">Traffic & Demand</h3>
        <p className="text-sm text-melonn-navy/40">No traffic or demand data available</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading">Traffic & Demand</h3>
        <ConfidenceBadge value={trafficConfidence} />
      </div>

      {hasTraffic && (
        <div className="text-center mb-3">
          <span className="text-3xl font-bold text-melonn-navy font-heading">
            {formatVisits(estimatedMonthlyVisits!)}
          </span>
          <p className="text-xs text-melonn-navy/50 mt-1">Estimated Monthly Visits</p>
          {signalsUsed && (
            <p className="text-xs text-melonn-navy/30 mt-0.5">Signals: {signalsUsed}</p>
          )}
        </div>
      )}

      {hasDemand && (
        <div className="space-y-2.5 mt-3">
          {brandDemandScore != null && (
            <ScoreBar score={brandDemandScore} label="Brand Demand" />
          )}
          {siteSerpCoverageScore != null && (
            <ScoreBar score={siteSerpCoverageScore} label="SERP Coverage" />
          )}
          {googleConfidence != null && (
            <div className="flex justify-between text-xs mt-1">
              <span className="text-melonn-navy/30">Google confidence</span>
              <ConfidenceBadge value={googleConfidence} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
