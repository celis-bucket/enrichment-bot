'use client'

import type { Company } from '@/lib/types'

interface Props {
  companies: Company[]
}

export default function AlertsBanner({ companies }: Props) {
  const alerts = companies.filter(
    (c) =>
      c.risk_level === 'high' ||
      c.risk_level === 'critical' ||
      c.recency_trend === 'worsening'
  )

  if (alerts.length === 0) return null

  const critical = alerts.filter((c) => c.risk_level === 'critical' || c.risk_level === 'high')
  const worsening = alerts.filter((c) => c.recency_trend === 'worsening' && c.risk_level !== 'high' && c.risk_level !== 'critical')

  return (
    <div className="alert alert-error" style={{ marginBottom: 'var(--space-6)' }}>
      <div style={{ fontWeight: 'var(--font-semibold)', marginBottom: 'var(--space-2)' }}>
        ⚠ {alerts.length} empresa{alerts.length > 1 ? 's' : ''} requiere{alerts.length === 1 ? '' : 'n'} atención
      </div>
      {critical.length > 0 && (
        <div style={{ marginBottom: 'var(--space-1)' }}>
          <strong>Score alto:</strong>{' '}
          {critical.map((c) => (
            <a
              key={c.company_id}
              href={`/empresa/${c.company_id}`}
              style={{ color: 'inherit', textDecoration: 'underline', marginRight: 'var(--space-3)' }}
            >
              @{c.ig_username} ({c.risk_score})
            </a>
          ))}
        </div>
      )}
      {worsening.length > 0 && (
        <div>
          <strong>Tendencia empeorando:</strong>{' '}
          {worsening.map((c) => (
            <a
              key={c.company_id}
              href={`/empresa/${c.company_id}`}
              style={{ color: 'inherit', textDecoration: 'underline', marginRight: 'var(--space-3)' }}
            >
              @{c.ig_username}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
