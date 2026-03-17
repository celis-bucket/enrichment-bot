import type { RiskLevel, Trend } from './types'

export const RISK_LABELS: Record<string, string> = {
  none: 'Ninguno',
  low: 'Bajo',
  medium: 'Medio',
  high: 'Alto',
  critical: 'Crítico',
}

export const TREND_LABELS: Record<string, string> = {
  worsening: 'Empeorando',
  stable: 'Estable',
  improving: 'Mejorando',
}

export const CATEGORY_LABELS: Record<string, string> = {
  DELAY: 'Demora',
  NON_DELIVERY: 'No entrega',
  DAMAGED: 'Daño',
  WRONG_ITEM: 'Producto equivocado',
  RETURN_REFUND: 'Devolución / Reembolso',
  POOR_SERVICE: 'Mal servicio',
}

export const SEVERITY_LABELS: Record<string, string> = {
  high: 'Alta',
  medium: 'Media',
  low: 'Baja',
}

export function getRiskBadgeClass(level: RiskLevel | string | null): string {
  switch (level) {
    case 'none':
    case 'low':
      return 'badge badge-success'
    case 'medium':
      return 'badge badge-warning'
    case 'high':
    case 'critical':
      return 'badge badge-error'
    default:
      return 'badge badge-neutral'
  }
}

export function getCategoryBadgeClass(category: string): string {
  switch (category) {
    case 'DELAY':
    case 'NON_DELIVERY':
      return 'badge badge-warning'
    case 'DAMAGED':
    case 'WRONG_ITEM':
      return 'badge badge-error'
    case 'RETURN_REFUND':
    case 'POOR_SERVICE':
      return 'badge badge-purple'
    default:
      return 'badge badge-neutral'
  }
}

export function getSeverityBadgeClass(severity: string): string {
  switch (severity) {
    case 'high':
      return 'badge badge-error'
    case 'medium':
      return 'badge badge-warning'
    case 'low':
      return 'badge badge-neutral'
    default:
      return 'badge badge-neutral'
  }
}

export function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  return date.toLocaleDateString('es-CO', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null) return '—'
  return n.toLocaleString('es-CO')
}

export function getTrendIcon(trend: Trend | string | null): string {
  switch (trend) {
    case 'worsening':
      return '↑'
    case 'improving':
      return '↓'
    case 'stable':
      return '→'
    default:
      return '—'
  }
}

export function getTrendClass(trend: Trend | string | null): string {
  switch (trend) {
    case 'worsening':
      return 'trend-worsening'
    case 'improving':
      return 'trend-improving'
    case 'stable':
      return 'trend-stable'
    default:
      return ''
  }
}
