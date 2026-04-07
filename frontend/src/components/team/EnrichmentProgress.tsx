'use client';

interface EnrichmentProgressProps {
  total: number;
  enrichedPct: number;
  worthEnrichment: number;
}

export function EnrichmentProgress({ total, enrichedPct, worthEnrichment }: EnrichmentProgressProps) {
  if (total === 0) return null;

  const enrichedCount = Math.round(enrichedPct * total / 100);
  const barColor = enrichedPct >= 70 ? 'bg-melonn-green' : enrichedPct >= 40 ? 'bg-melonn-orange' : 'bg-red-500';

  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
        Enrichment Completo
      </h3>
      <div className="w-full bg-gray-100 rounded-full h-5 overflow-hidden">
        <div
          className={`${barColor} h-5 rounded-full flex items-center justify-center text-white text-xs font-semibold transition-all duration-500`}
          style={{ width: `${Math.max(enrichedPct, 5)}%` }}
        >
          {enrichedPct >= 15 ? `${enrichedPct}%` : ''}
        </div>
      </div>
      <div className="flex justify-between mt-2 text-xs text-gray-500">
        <span>{enrichedCount} de {total} leads con full enrichment</span>
        {worthEnrichment > 0 && (
          <span className="text-melonn-orange font-medium">{worthEnrichment} pendientes</span>
        )}
      </div>
    </div>
  );
}
