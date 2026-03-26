'use client';

export function ScoreBar({ score, max = 100 }: { score: number | null | undefined; max?: number }) {
  if (score == null) return <span className="text-gray-400 text-xs">--</span>;

  const pct = Math.min(100, Math.max(0, (score / max) * 100));

  let color = 'bg-gray-300';
  if (pct >= 80) color = 'bg-melonn-green';
  else if (pct >= 60) color = 'bg-blue-500';
  else if (pct >= 40) color = 'bg-melonn-orange';
  else color = 'bg-gray-300';

  return (
    <div className="flex items-center gap-1.5">
      <div className="w-16 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-600 font-medium w-6 text-right">{score}</span>
    </div>
  );
}
