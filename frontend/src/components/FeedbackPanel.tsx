'use client';

import { useState } from 'react';
import type { FeedbackItem } from '@/lib/types';
import { submitFeedback } from '@/lib/api';

interface FeedbackPanelProps {
  domain: string;
  section: string;
  existingFeedback?: FeedbackItem[];
}

export function FeedbackPanel({ domain, section, existingFeedback = [] }: FeedbackPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [comment, setComment] = useState('');
  const [suggestedValue, setSuggestedValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [localFeedback, setLocalFeedback] = useState<FeedbackItem[]>([]);

  const allFeedback = [...localFeedback, ...existingFeedback];
  const sectionFeedback = allFeedback.filter(f => f.section === section);

  const handleSubmit = async () => {
    if (!comment.trim()) return;
    setSaving(true);
    try {
      await submitFeedback(domain, section, comment.trim(), suggestedValue.trim() || undefined);
      setLocalFeedback(prev => [{
        domain,
        section,
        comment: comment.trim(),
        suggested_value: suggestedValue.trim() || null,
        created_by: 'you',
        created_at: new Date().toISOString(),
      }, ...prev]);
      setComment('');
      setSuggestedValue('');
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error('Failed to submit feedback:', e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 text-xs text-melonn-navy/30 hover:text-melonn-purple transition-colors"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        {sectionFeedback.length > 0
          ? `${sectionFeedback.length} comment${sectionFeedback.length > 1 ? 's' : ''}`
          : 'Add feedback'}
      </button>

      {isOpen && (
        <div className="mt-2 bg-melonn-surface rounded-xl p-3 space-y-3">
          {/* Existing feedback */}
          {sectionFeedback.length > 0 && (
            <div className="space-y-2">
              {sectionFeedback.map((f, i) => (
                <div key={f.id || i} className="bg-white rounded-lg p-2.5 border border-melonn-purple-50/50">
                  <p className="text-sm text-melonn-navy">{f.comment}</p>
                  {f.suggested_value && (
                    <p className="text-xs text-melonn-purple mt-1">
                      Suggested: <span className="font-medium">{f.suggested_value}</span>
                    </p>
                  )}
                  <p className="text-xs text-melonn-navy/30 mt-1">
                    {f.created_by} &middot; {f.created_at ? new Date(f.created_at).toLocaleDateString() : ''}
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* New feedback form */}
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="What's wrong or could be improved?"
            className="w-full text-sm border border-melonn-purple-50 rounded-lg p-2 resize-none focus:outline-none focus:ring-1 focus:ring-melonn-purple/30 text-melonn-navy placeholder:text-melonn-navy/30"
            rows={2}
          />
          <input
            type="text"
            value={suggestedValue}
            onChange={(e) => setSuggestedValue(e.target.value)}
            placeholder="Correct value (optional)"
            className="w-full text-sm border border-melonn-purple-50 rounded-lg p-2 focus:outline-none focus:ring-1 focus:ring-melonn-purple/30 text-melonn-navy placeholder:text-melonn-navy/30"
          />
          <div className="flex items-center gap-2">
            <button
              onClick={handleSubmit}
              disabled={!comment.trim() || saving}
              className="text-xs px-4 py-1.5 bg-melonn-purple text-white rounded-lg font-medium hover:bg-melonn-purple-light transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Submit'}
            </button>
            {saved && (
              <span className="text-xs text-melonn-green font-medium">Saved!</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
