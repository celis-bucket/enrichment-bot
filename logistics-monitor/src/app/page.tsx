'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import type { Company } from '@/lib/types'
import CompanyTable from '@/components/CompanyTable'
import AlertsBanner from '@/components/AlertsBanner'

export default function DashboardPage() {
  const [companies, setCompanies] = useState<Company[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchData() {
      try {
        const { data, error: fetchError } = await supabase
          .from('company_latest_scan')
          .select('*')

        if (fetchError) throw fetchError
        setCompanies(data || [])
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error cargando datos')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  if (loading) {
    return (
      <div>
        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--font-bold)', marginBottom: 'var(--space-6)' }}>
          Monitor de Crisis Logística
        </h1>
        <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="stat-card">
              <div className="skeleton" style={{ height: '20px', width: '60%', marginBottom: 'var(--space-2)' }} />
              <div className="skeleton" style={{ height: '32px', width: '40%' }} />
            </div>
          ))}
        </div>
        <div className="card" style={{ marginTop: 'var(--space-6)' }}>
          <div className="card-body">
            <div className="skeleton" style={{ height: '200px' }} />
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="alert alert-error">
        <strong>Error:</strong> {error}
      </div>
    )
  }

  const totalCompanies = companies.length
  const avgScore = totalCompanies > 0
    ? Math.round(companies.reduce((sum, c) => sum + (c.risk_score ?? 0), 0) / totalCompanies)
    : 0
  const inCrisis = companies.filter((c) => (c.risk_score ?? 0) >= 50).length
  const worsening = companies.filter((c) => c.recency_trend === 'worsening').length
  const lastScanDate = companies.reduce((latest, c) => {
    if (!c.scanned_at) return latest
    return !latest || c.scanned_at > latest ? c.scanned_at : latest
  }, null as string | null)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-6)' }}>
        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 'var(--font-bold)' }}>
          Monitor de Crisis Logística
        </h1>
        {lastScanDate && (
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
            Último scan: {new Date(lastScanDate).toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' })}
          </span>
        )}
      </div>

      <AlertsBanner companies={companies} />

      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 'var(--space-6)' }}>
        <div className="stat-card">
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-1)' }}>
            Empresas Monitoreadas
          </div>
          <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 'var(--font-bold)', fontFamily: 'var(--font-mono)' }}>
            {totalCompanies}
          </div>
        </div>

        <div className="stat-card">
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-1)' }}>
            Score Promedio
          </div>
          <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 'var(--font-bold)', fontFamily: 'var(--font-mono)' }}>
            {avgScore}
          </div>
        </div>

        <div className={`stat-card ${inCrisis > 0 ? 'stat-card-featured' : ''}`}>
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-1)' }}>
            En Crisis ({'>'}50)
          </div>
          <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 'var(--font-bold)', fontFamily: 'var(--font-mono)', color: inCrisis > 0 ? 'var(--color-error)' : undefined }}>
            {inCrisis}
          </div>
        </div>

        <div className="stat-card">
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-1)' }}>
            Tendencia Empeorando
          </div>
          <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 'var(--font-bold)', fontFamily: 'var(--font-mono)', color: worsening > 0 ? 'var(--color-warning)' : undefined }}>
            {worsening}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Empresas</h2>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          <CompanyTable companies={companies} />
        </div>
      </div>
    </div>
  )
}
