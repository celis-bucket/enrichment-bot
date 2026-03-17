'use client'

import { getTrendIcon, getTrendClass, TREND_LABELS } from '@/lib/utils'

export default function TrendArrow({ trend }: { trend: string | null }) {
  if (!trend) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>

  return (
    <span className={getTrendClass(trend)} title={TREND_LABELS[trend] || trend}>
      {getTrendIcon(trend)} {TREND_LABELS[trend] || trend}
    </span>
  )
}
