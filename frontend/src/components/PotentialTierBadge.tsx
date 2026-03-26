'use client';

const TIER_STYLES: Record<string, string> = {
  'Extraordinary': 'bg-melonn-green-50 text-melonn-green',
  'Very Good': 'bg-blue-50 text-blue-600',
  'Good': 'bg-melonn-orange-50 text-melonn-orange',
  'Low': 'bg-gray-100 text-gray-500',
};

export function PotentialTierBadge({ tier }: { tier: string | null | undefined }) {
  if (!tier) return <span className="text-gray-400 text-xs">--</span>;

  const style = TIER_STYLES[tier] || 'bg-gray-100 text-gray-500';

  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap ${style}`}>
      {tier}
    </span>
  );
}
