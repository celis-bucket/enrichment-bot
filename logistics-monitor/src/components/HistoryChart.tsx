'use client'

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Area, AreaChart } from 'recharts'
import type { Scan } from '@/lib/types'

interface Props {
  scans: Scan[]
}

export default function HistoryChart({ scans }: Props) {
  if (scans.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--space-8)', color: 'var(--color-text-muted)' }}>
        No hay datos históricos disponibles.
      </div>
    )
  }

  const data = scans
    .filter((s) => s.status === 'completed')
    .sort((a, b) => new Date(a.scanned_at).getTime() - new Date(b.scanned_at).getTime())
    .map((s) => ({
      date: new Date(s.scanned_at).toLocaleDateString('es-CO', { day: 'numeric', month: 'short' }),
      score: s.risk_score ?? 0,
      complaints: s.complaints_found ?? 0,
    }))

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#4D2AAD" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#4D2AAD" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12, fill: 'var(--color-text-secondary)' }}
            tickLine={false}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 12, fill: 'var(--color-text-secondary)' }}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              fontSize: 'var(--text-sm)',
            }}
            formatter={(value: number, name: string) => [
              value,
              name === 'score' ? 'Risk Score' : 'Quejas',
            ]}
          />
          <ReferenceLine y={25} stroke="#00C77C" strokeDasharray="3 3" strokeOpacity={0.5} />
          <ReferenceLine y={50} stroke="#FFC800" strokeDasharray="3 3" strokeOpacity={0.5} />
          <ReferenceLine y={75} stroke="#EF4444" strokeDasharray="3 3" strokeOpacity={0.5} />
          <Area
            type="monotone"
            dataKey="score"
            stroke="#4D2AAD"
            strokeWidth={2}
            fill="url(#scoreGradient)"
            dot={{ fill: '#4D2AAD', strokeWidth: 0, r: 4 }}
            activeDot={{ r: 6, fill: '#BA80FF' }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
