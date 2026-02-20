'use client';

import { WorkflowStep } from '@/lib/types';

interface WorkflowReportProps {
  steps: WorkflowStep[];
}

const STATUS_CONFIG: Record<string, { icon: string; color: string; bg: string }> = {
  ok:   { icon: 'OK',   color: 'text-green-700',  bg: 'bg-green-100' },
  warn: { icon: 'WARN', color: 'text-yellow-700', bg: 'bg-yellow-100' },
  fail: { icon: 'FAIL', color: 'text-red-700',    bg: 'bg-red-100' },
  skip: { icon: 'SKIP', color: 'text-gray-500',   bg: 'bg-gray-100' },
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function WorkflowReport({ steps }: WorkflowReportProps) {
  if (!steps || steps.length === 0) return null;

  const totalStep = steps.find(s => s.step === 'Total');
  const displaySteps = steps.filter(s => s.step !== 'Total');

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          Workflow Execution Log
        </h3>
        {totalStep && (
          <span className="text-xs font-mono text-gray-500">
            Total: {formatDuration(totalStep.duration_ms)}
          </span>
        )}
      </div>

      <div className="space-y-1">
        {displaySteps.map((step, i) => {
          const cfg = STATUS_CONFIG[step.status] || STATUS_CONFIG.skip;
          return (
            <div
              key={i}
              className="flex items-start gap-2 py-1.5 px-2 rounded text-sm hover:bg-gray-50"
            >
              <span className={`inline-block w-10 text-center text-xs font-bold rounded px-1 py-0.5 ${cfg.color} ${cfg.bg}`}>
                {cfg.icon}
              </span>

              <span className="font-medium text-gray-800 min-w-[180px] shrink-0">
                {step.step}
              </span>

              <span className="text-gray-500 flex-1 truncate text-xs leading-5" title={step.detail || ''}>
                {step.detail || ''}
              </span>

              <span className="text-xs font-mono text-gray-400 shrink-0">
                {formatDuration(step.duration_ms)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
