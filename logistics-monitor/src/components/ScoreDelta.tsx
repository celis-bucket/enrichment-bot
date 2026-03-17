'use client'

export default function ScoreDelta({ delta }: { delta: number | null }) {
  if (delta == null) return null

  let className = 'delta-zero'
  let prefix = ''

  if (delta > 0) {
    className = 'delta-positive'
    prefix = '+'
  } else if (delta < 0) {
    className = 'delta-negative'
  }

  return (
    <span
      className={className}
      style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)' }}
    >
      {prefix}{delta}
    </span>
  )
}
