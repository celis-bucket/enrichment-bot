'use client';

const TIER_CONFIG: { key: string; label: string; color: string }[] = [
  { key: 'Extraordinary', label: 'Extr.', color: 'bg-melonn-green' },
  { key: 'Very Good', label: 'V.Good', color: 'bg-blue-500' },
  { key: 'Good', label: 'Good', color: 'bg-melonn-orange' },
  { key: 'Low', label: 'Low', color: 'bg-gray-300' },
];

interface PotentialDistributionProps {
  distribution: Record<string, number>;
}

export function PotentialDistribution({ distribution }: PotentialDistributionProps) {
  const total = Object.values(distribution).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
        Distribucion Potencial
      </h3>
      {/* Stacked bar */}
      <div className="flex rounded-full overflow-hidden h-6 mb-2">
        {TIER_CONFIG.map(({ key, color }) => {
          const count = distribution[key] || 0;
          if (count === 0) return null;
          const pct = (count / total) * 100;
          return (
            <div
              key={key}
              className={`${color} flex items-center justify-center text-white text-xs font-semibold transition-all`}
              style={{ width: `${pct}%` }}
              title={`${key}: ${count}`}
            >
              {pct > 10 ? count : ''}
            </div>
          );
        })}
      </div>
      {/* Legend */}
      <div className="flex justify-between text-xs text-gray-500">
        {TIER_CONFIG.map(({ key, label, color }) => {
          const count = distribution[key] || 0;
          return (
            <div key={key} className="flex items-center gap-1">
              <span className={`w-2 h-2 rounded-full ${color}`} />
              <span>{label}</span>
              <span className="font-semibold text-gray-700">{count}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
