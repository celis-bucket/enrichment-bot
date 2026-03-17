'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import type { Company, Scan, FlaggedComment } from '@/lib/types'
import { formatNumber, formatDate, RISK_LABELS, TREND_LABELS } from '@/lib/utils'
import RiskBadge from '@/components/RiskBadge'
import TrendArrow from '@/components/TrendArrow'
import ScoreDelta from '@/components/ScoreDelta'
import HistoryChart from '@/components/HistoryChart'
import CategoryBreakdown from '@/components/CategoryBreakdown'
import FlaggedCommentsList from '@/components/FlaggedCommentsList'

export default function CompanyDetailPage() {
  const params = useParams()
  const companyId = params.id as string

  const [company, setCompany] = useState<Company | null>(null)
  const [scans, setScans] = useState<Scan[]>([])
  const [comments, setComments] = useState<FlaggedComment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchData() {
      try {
        // Fetch company with latest scan
        const { data: companyData, error: companyError } = await supabase
          .from('company_latest_scan')
          .select('*')
          .eq('company_id', companyId)
          .single()

        if (companyError) throw companyError
        setCompany(companyData)

        // Fetch scan history
        const { data: scanData, error: scanError } = await supabase
          .from('scans')
          .select('*')
          .eq('company_id', companyId)
          .order('scanned_at', { ascending: false })
          .limit(24)

        if (scanError) throw scanError
        setScans(scanData || [])

        // Fetch flagged comments for latest scan
        if (companyData?.scan_id) {
          const { data: commentData, error: commentError } = await supabase
            .from('flagged_comments')
            .select('*')
            .eq('scan_id', companyData.scan_id)
            .order('likes', { ascending: false })

          if (commentError) throw commentError
          setComments(commentData || [])
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error cargando datos')
      } finally {
        setLoading(false)
      }
    }

    if (companyId) fetchData()
  }, [companyId])

  if (loading) {
    return (
      <div>
        <a href="/" className="btn btn-ghost btn-sm" style={{ marginBottom: 'var(--space-4)' }}>
          ← Volver
        </a>
        <div className="skeleton" style={{ height: '40px', width: '300px', marginBottom: 'var(--space-4)' }} />
        <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
          {[1, 2, 3].map((i) => (
            <div key={i} className="stat-card">
              <div className="skeleton" style={{ height: '60px' }} />
            </div>
          ))}
        </div>
        <div className="card" style={{ marginTop: 'var(--space-6)' }}>
          <div className="card-body"><div className="skeleton" style={{ height: '300px' }} /></div>
        </div>
      </div>
    )
  }

  if (error || !company) {
    return (
      <div>
        <a href="/" className="btn btn-ghost btn-sm" style={{ marginBottom: 'var(--space-4)' }}>
          ← Volver
        </a>
        <div className="alert alert-error">
          {error || 'Empresa no encontrada'}
        </div>
      </div>
    )
  }

  const scoreClass = !company.risk_score ? 'score-none'
    : company.risk_score <= 25 ? 'score-low'
    : company.risk_score <= 50 ? 'score-medium'
    : company.risk_score <= 75 ? 'score-high'
    : 'score-critical'

  return (
    <div>
      <a href="/" className="btn btn-ghost btn-sm" style={{ marginBottom: 'var(--space-4)' }}>
        ← Volver al dashboard
      </a>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-6)' }}>
        <div>
          <h1 style={{ fontSize: 'var(--text-3xl)', fontWeight: 'var(--font-bold)', marginBottom: 'var(--space-1)' }}>
            {company.name}
          </h1>
          <div style={{ display: 'flex', gap: 'var(--space-4)', alignItems: 'center', color: 'var(--color-text-secondary)' }}>
            <a
              href={company.ig_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'var(--melonn-purple)' }}
            >
              @{company.ig_username}
            </a>
            <span>{formatNumber(company.ig_followers)} followers</span>
            <span className="badge badge-neutral">{company.country}</span>
          </div>
        </div>
        {company.scanned_at && (
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
            Último scan: {formatDate(company.scanned_at)}
          </span>
        )}
      </div>

      {/* Stats cards */}
      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 'var(--space-6)' }}>
        <div className="stat-card-featured">
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-1)' }}>
            Risk Score
          </div>
          <div className={`score-display ${scoreClass}`}>
            {company.risk_score ?? '—'}
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center', marginTop: 'var(--space-1)' }}>
            <RiskBadge level={company.risk_level} />
            <ScoreDelta delta={company.score_delta} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-1)' }}>
            Tendencia
          </div>
          <div style={{ fontSize: 'var(--text-xl)', fontWeight: 'var(--font-semibold)' }}>
            <TrendArrow trend={company.recency_trend} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-1)' }}>
            Quejas Detectadas
          </div>
          <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 'var(--font-bold)', fontFamily: 'var(--font-mono)' }}>
            {company.complaints_found ?? 0}
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
            de {formatNumber(company.comments_analyzed)} comentarios
          </div>
        </div>

        <div className="stat-card">
          <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-1)' }}>
            Tasa de Quejas
          </div>
          <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 'var(--font-bold)', fontFamily: 'var(--font-mono)' }}>
            {company.complaint_rate_pct ?? 0}%
          </div>
        </div>
      </div>

      {/* Summary */}
      {company.summary && (
        <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
          <div className="card-header">
            <h2 className="card-title">Resumen</h2>
          </div>
          <div className="card-body">
            <p style={{ margin: 0, lineHeight: 'var(--leading-relaxed)', color: 'var(--color-text-secondary)' }}>
              {company.summary}
            </p>
          </div>
        </div>
      )}

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 'var(--space-6)', marginBottom: 'var(--space-6)' }}>
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Historial de Risk Score</h2>
          </div>
          <div className="card-body">
            <HistoryChart scans={scans} />
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Categorías</h2>
          </div>
          <div className="card-body">
            <CategoryBreakdown breakdown={company.category_breakdown} />
          </div>
        </div>
      </div>

      {/* Flagged comments */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">
            Comentarios Flaggeados ({comments.length})
          </h2>
        </div>
        <div className="card-body">
          <FlaggedCommentsList comments={comments} />
        </div>
      </div>
    </div>
  )
}
