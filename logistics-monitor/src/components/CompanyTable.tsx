'use client'

import { useState } from 'react'
import type { Company } from '@/lib/types'
import { formatDate, formatNumber } from '@/lib/utils'
import RiskBadge from './RiskBadge'
import TrendArrow from './TrendArrow'
import ScoreDelta from './ScoreDelta'

interface Props {
  companies: Company[]
}

type SortKey = 'risk_score' | 'ig_username' | 'complaints_found' | 'scanned_at'

export default function CompanyTable({ companies }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('risk_score')
  const [sortDesc, setSortDesc] = useState(true)
  const [filterLevel, setFilterLevel] = useState<string>('all')

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDesc(!sortDesc)
    } else {
      setSortKey(key)
      setSortDesc(true)
    }
  }

  const filtered = filterLevel === 'all'
    ? companies
    : companies.filter((c) => c.risk_level === filterLevel)

  const sorted = [...filtered].sort((a, b) => {
    let aVal = a[sortKey] ?? -1
    let bVal = b[sortKey] ?? -1
    if (typeof aVal === 'string') aVal = aVal.toLowerCase()
    if (typeof bVal === 'string') bVal = bVal.toLowerCase()
    if (aVal < bVal) return sortDesc ? 1 : -1
    if (aVal > bVal) return sortDesc ? -1 : 1
    return 0
  })

  const sortIcon = (key: SortKey) => {
    if (sortKey !== key) return ''
    return sortDesc ? ' ↓' : ' ↑'
  }

  return (
    <div>
      <div style={{ marginBottom: 'var(--space-4)', display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
        <button
          className={`btn btn-sm ${filterLevel === 'all' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setFilterLevel('all')}
        >
          Todas ({companies.length})
        </button>
        {['critical', 'high', 'medium', 'low', 'none'].map((level) => {
          const count = companies.filter((c) => c.risk_level === level).length
          if (count === 0) return null
          return (
            <button
              key={level}
              className={`btn btn-sm ${filterLevel === level ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setFilterLevel(level)}
            >
              {level} ({count})
            </button>
          )
        })}
      </div>

      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              <th onClick={() => handleSort('ig_username')} style={{ cursor: 'pointer' }}>
                Empresa{sortIcon('ig_username')}
              </th>
              <th onClick={() => handleSort('risk_score')} style={{ cursor: 'pointer' }}>
                Score{sortIcon('risk_score')}
              </th>
              <th>Nivel</th>
              <th>Tendencia</th>
              <th onClick={() => handleSort('complaints_found')} style={{ cursor: 'pointer' }}>
                Quejas{sortIcon('complaints_found')}
              </th>
              <th>Comentarios</th>
              <th>Followers</th>
              <th onClick={() => handleSort('scanned_at')} style={{ cursor: 'pointer' }}>
                Último scan{sortIcon('scanned_at')}
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((company) => (
              <tr
                key={company.company_id}
                className="company-row"
                onClick={() => window.location.href = `/empresa/${company.company_id}`}
              >
                <td>
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontWeight: 'var(--font-semibold)' }}>
                      {company.name}
                    </span>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
                      @{company.ig_username}
                    </span>
                  </div>
                </td>
                <td>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 'var(--font-semibold)' }}>
                    {company.risk_score ?? '—'}
                  </span>
                  {' '}
                  <ScoreDelta delta={company.score_delta} />
                </td>
                <td><RiskBadge level={company.risk_level} /></td>
                <td><TrendArrow trend={company.recency_trend} /></td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {company.complaints_found ?? '—'}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {formatNumber(company.comments_analyzed)}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {formatNumber(company.ig_followers)}
                </td>
                <td style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>
                  {formatDate(company.scanned_at)}
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 'var(--space-8)' }}>
                  {companies.length === 0
                    ? 'No hay empresas monitoreadas. Agrega empresas en Supabase.'
                    : 'No hay empresas con este filtro.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
