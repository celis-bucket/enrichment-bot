'use client';

import type { DuplicateCheckResult } from '@/lib/types';

interface DuplicateWarningProps {
  duplicate: DuplicateCheckResult;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DuplicateWarning({ duplicate, onConfirm, onCancel }: DuplicateWarningProps) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-xl p-6 max-w-md mx-4">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">⚠️</span>
          <h3 className="text-lg font-semibold text-melonn-navy font-heading">Domain Already Analyzed</h3>
        </div>

        <p className="text-sm text-melonn-navy/70 mb-1">
          <span className="font-medium text-melonn-navy">{duplicate.domain}</span> was already analyzed
          {duplicate.last_analyzed && ` on ${duplicate.last_analyzed}`}.
        </p>
        <p className="text-sm text-melonn-navy/50 mb-6">
          Do you want to run the enrichment again? A new row will be added to the sheet.
        </p>

        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-5 py-2 text-sm text-melonn-navy bg-melonn-surface rounded-full hover:bg-melonn-purple-50 transition-colors font-heading"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-5 py-2 text-sm text-white bg-melonn-green rounded-full hover:bg-melonn-green/90 transition-colors font-heading font-semibold"
          >
            Run Again
          </button>
        </div>
      </div>
    </div>
  );
}
