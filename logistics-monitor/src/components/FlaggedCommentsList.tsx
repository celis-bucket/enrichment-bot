'use client'

import type { FlaggedComment } from '@/lib/types'
import { CATEGORY_LABELS, SEVERITY_LABELS, getCategoryBadgeClass, getSeverityBadgeClass } from '@/lib/utils'

interface Props {
  comments: FlaggedComment[]
}

export default function FlaggedCommentsList({ comments }: Props) {
  if (comments.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--space-6)', color: 'var(--color-text-muted)' }}>
        No hay comentarios flaggeados.
      </div>
    )
  }

  return (
    <div>
      {comments.map((comment) => (
        <div key={comment.id} className={`comment-card severity-${comment.severity}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-2)' }}>
            <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
              <span className={getCategoryBadgeClass(comment.category)}>
                {CATEGORY_LABELS[comment.category] || comment.category}
              </span>
              <span className={getSeverityBadgeClass(comment.severity)}>
                {SEVERITY_LABELS[comment.severity] || comment.severity}
              </span>
            </div>
            {comment.likes > 0 && (
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
                ♥ {comment.likes}
              </span>
            )}
          </div>

          <p style={{ margin: '0 0 var(--space-2) 0', fontSize: 'var(--text-sm)', lineHeight: 'var(--leading-normal)' }}>
            {comment.text}
          </p>

          <div style={{ display: 'flex', gap: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
            <span>{comment.owner}</span>
            {comment.comment_timestamp && (
              <span>{new Date(comment.comment_timestamp).toLocaleDateString('es-CO')}</span>
            )}
            {comment.post_url && (
              <a
                href={comment.post_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'var(--melonn-purple)' }}
                onClick={(e) => e.stopPropagation()}
              >
                Ver post →
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
