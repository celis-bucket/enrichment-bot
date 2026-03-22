'use client';

import { WorkflowStep } from '@/lib/types';

interface WorkflowReportProps {
  steps: WorkflowStep[];
  totalRuntimeSec?: number | null;
  costEstimateUsd?: number | null;
}

const STATUS_CONFIG: Record<string, { icon: string; color: string; bg: string }> = {
  ok:      { icon: 'OK',   color: 'text-melonn-green',   bg: 'bg-melonn-green-50' },
  warn:    { icon: 'WARN', color: 'text-melonn-orange',  bg: 'bg-melonn-orange-50' },
  fail:    { icon: 'FAIL', color: 'text-red-600',        bg: 'bg-red-50' },
  skip:    { icon: 'SKIP', color: 'text-melonn-navy/40', bg: 'bg-melonn-surface' },
  running: { icon: '...',  color: 'text-melonn-purple',  bg: 'bg-melonn-purple-50' },
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function WorkflowReport({ steps, totalRuntimeSec, costEstimateUsd }: WorkflowReportProps) {
  if (!steps || steps.length === 0) return null;

  const displaySteps = steps.filter(s => s.step !== 'Total' && s.status !== 'running');
  const okCount = displaySteps.filter(s => s.status === 'ok').length;
  const warnCount = displaySteps.filter(s => s.status === 'warn').length;
  const failCount = displaySteps.filter(s => s.status === 'fail').length;

  return (
    <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
      {/* Summary header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading uppercase tracking-wide">
          Execution Log
        </h3>
        <div className="flex items-center gap-3 text-xs">
          {totalRuntimeSec != null && (
            <span className="font-mono text-melonn-navy/40">
              {totalRuntimeSec.toFixed(1)}s
            </span>
          )}
          {costEstimateUsd != null && (
            <span className="font-mono text-melonn-navy/40">
              ${costEstimateUsd.toFixed(2)}
            </span>
          )}
        </div>
      </div>

      {/* Status summary badges */}
      <div className="flex gap-2 mb-3">
        <span className="text-xs px-2 py-0.5 rounded-full bg-melonn-green-50 text-melonn-green font-medium">
          {okCount} OK
        </span>
        {warnCount > 0 && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-melonn-orange-50 text-melonn-orange font-medium">
            {warnCount} WARN
          </span>
        )}
        {failCount > 0 && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-600 font-medium">
            {failCount} FAIL
          </span>
        )}
        <span className="text-xs px-2 py-0.5 rounded-full bg-melonn-surface text-melonn-navy/40 font-medium">
          {displaySteps.length} steps
        </span>
      </div>

      {/* Step list */}
      <div className="space-y-1">
        {displaySteps.map((step, i) => {
          const cfg = STATUS_CONFIG[step.status] || STATUS_CONFIG.skip;
          return (
            <div
              key={i}
              className="flex items-start gap-2 py-1.5 px-2 rounded-xl text-sm hover:bg-melonn-surface transition-colors"
            >
              <span className={`inline-block w-10 text-center text-xs font-bold rounded-lg px-1 py-0.5 ${cfg.color} ${cfg.bg}`}>
                {cfg.icon}
              </span>

              <span className="font-medium text-melonn-navy min-w-[160px] shrink-0">
                {step.step}
              </span>

              <span className="text-melonn-navy/50 flex-1 text-xs leading-5" title={step.detail || ''}>
                {step.detail || ''}
              </span>

              <span className="text-xs font-mono text-melonn-navy/40 shrink-0">
                {formatDuration(step.duration_ms)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
