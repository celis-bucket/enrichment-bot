'use client'

import { getRiskBadgeClass, RISK_LABELS } from '@/lib/utils'

export default function RiskBadge({ level }: { level: string | null }) {
  if (!level) return <span className="badge badge-neutral">—</span>
  return (
    <span className={getRiskBadgeClass(level)}>
      {RISK_LABELS[level] || level}
    </span>
  )
}
