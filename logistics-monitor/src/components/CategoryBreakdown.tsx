'use client'

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { CategoryBreakdown as CategoryBreakdownType } from '@/lib/types'
import { CATEGORY_LABELS } from '@/lib/utils'

interface Props {
  breakdown: CategoryBreakdownType | null
}

const COLORS: Record<string, string> = {
  DELAY: '#FFC800',
  NON_DELIVERY: '#EF4444',
  DAMAGED: '#EF4444',
  WRONG_ITEM: '#4D2AAD',
  RETURN_REFUND: '#BA80FF',
  POOR_SERVICE: '#00DCD6',
}

export default function CategoryBreakdown({ breakdown }: Props) {
  if (!breakdown) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--space-6)', color: 'var(--color-text-muted)' }}>
        Sin datos de categorías.
      </div>
    )
  }

  const data = Object.entries(breakdown)
    .map(([key, value]) => ({
      category: CATEGORY_LABELS[key] || key,
      count: value,
      key,
    }))
    .filter((d) => d.count > 0)
    .sort((a, b) => b.count - a.count)

  if (data.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--space-6)', color: 'var(--color-text-muted)' }}>
        No se detectaron quejas logísticas.
      </div>
    )
  }

  return (
    <div style={{ height: '250px' }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, left: 100, bottom: 5 }}>
          <XAxis type="number" tick={{ fontSize: 12, fill: 'var(--color-text-secondary)' }} />
          <YAxis
            type="category"
            dataKey="category"
            tick={{ fontSize: 12, fill: 'var(--color-text-secondary)' }}
            width={95}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              fontSize: 'var(--text-sm)',
            }}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={20}>
            {data.map((entry) => (
              <Cell key={entry.key} fill={COLORS[entry.key] || '#4D2AAD'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
