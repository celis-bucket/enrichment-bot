'use client';

import type { PipelineStep } from '@/lib/types';

interface PipelineProgressProps {
  steps: PipelineStep[];
}

const STATUS_CONFIG = {
  running: { icon: '⏳', color: 'text-melonn-purple', bg: 'bg-melonn-purple-50', label: 'Running' },
  ok:      { icon: '✓',  color: 'text-melonn-green', bg: 'bg-melonn-green-50', label: 'Done' },
  warn:    { icon: '⚠',  color: 'text-melonn-orange', bg: 'bg-melonn-orange-50', label: 'Warning' },
  fail:    { icon: '✗',  color: 'text-red-600', bg: 'bg-red-50', label: 'Failed' },
  skip:    { icon: '–',  color: 'text-melonn-navy/40', bg: 'bg-melonn-surface', label: 'Skipped' },
};

function formatDuration(ms?: number): string {
  if (!ms || ms === 0) return '';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function capitalizeStep(step: string): string {
  return step.charAt(0).toUpperCase() + step.slice(1);
}

export function PipelineProgress({ steps }: PipelineProgressProps) {
  if (steps.length === 0) return null;

  const totalMs = steps.reduce((sum, s) => sum + (s.duration_ms || 0), 0);
  const hasRunning = steps.some((s) => s.status === 'running');

  return (
    <div className="w-full max-w-3xl mx-auto">
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-melonn-navy font-heading">Pipeline Progress</h3>
          {totalMs > 0 && (
            <span className="text-xs text-melonn-navy/40 font-mono">{formatDuration(totalMs)} elapsed</span>
          )}
        </div>

        <div className="space-y-1">
          {steps.map((step, i) => {
            const config = STATUS_CONFIG[step.status] || STATUS_CONFIG.running;
            return (
              <div
                key={`${step.step}-${i}`}
                className={`flex items-center gap-3 px-3 py-1.5 rounded-xl ${config.bg}`}
              >
                <span className={`w-5 text-center font-bold ${config.color}`}>
                  {step.status === 'running' ? (
                    <span className="inline-block animate-spin">↻</span>
                  ) : (
                    config.icon
                  )}
                </span>
                <span className={`flex-1 text-sm ${step.status === 'running' ? 'font-medium' : ''} ${config.color}`}>
                  {capitalizeStep(step.step)}
                </span>
                {step.duration_ms !== undefined && step.duration_ms > 0 && (
                  <span className="text-xs text-melonn-navy/40 font-mono">{formatDuration(step.duration_ms)}</span>
                )}
              </div>
            );
          })}
        </div>

        {hasRunning && (
          <div className="mt-3 flex items-center gap-2">
            <div className="h-1.5 flex-1 bg-melonn-surface rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-melonn-purple to-melonn-green rounded-full transition-all duration-500 animate-pulse"
                style={{ width: '100%' }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
