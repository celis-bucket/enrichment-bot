'use client';

import type { PipelineStep } from '@/lib/types';

interface PipelineProgressProps {
  steps: PipelineStep[];
}

const STATUS_CONFIG = {
  running: { icon: '⏳', color: 'text-blue-600', bg: 'bg-blue-50', label: 'Running' },
  ok:      { icon: '✓',  color: 'text-green-600', bg: 'bg-green-50', label: 'Done' },
  warn:    { icon: '⚠',  color: 'text-yellow-600', bg: 'bg-yellow-50', label: 'Warning' },
  fail:    { icon: '✗',  color: 'text-red-600', bg: 'bg-red-50', label: 'Failed' },
  skip:    { icon: '–',  color: 'text-gray-400', bg: 'bg-gray-50', label: 'Skipped' },
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
    <div className="w-full max-w-2xl mx-auto">
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700">Pipeline Progress</h3>
          {totalMs > 0 && (
            <span className="text-xs text-gray-400">{formatDuration(totalMs)} elapsed</span>
          )}
        </div>

        <div className="space-y-1">
          {steps.map((step, i) => {
            const config = STATUS_CONFIG[step.status] || STATUS_CONFIG.running;
            return (
              <div
                key={`${step.step}-${i}`}
                className={`flex items-center gap-3 px-3 py-1.5 rounded ${config.bg}`}
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
                  <span className="text-xs text-gray-400">{formatDuration(step.duration_ms)}</span>
                )}
              </div>
            );
          })}
        </div>

        {hasRunning && (
          <div className="mt-3 flex items-center gap-2">
            <div className="h-1 flex-1 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-500 animate-pulse"
                style={{ width: '100%' }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
