'use client';

import { useEnrichment } from '@/hooks/useEnrichment';
import { EnrichmentForm } from '@/components/EnrichmentForm';
import { PipelineProgress } from '@/components/PipelineProgress';
import { ErrorDisplay } from '@/components/ErrorDisplay';
import { ResultsDisplay } from '@/components/ResultsDisplay';
import { DuplicateWarning } from '@/components/DuplicateWarning';
import { Header } from '@/components/Header';

export default function Home() {
  const {
    results, steps, isLoading, error, duplicate,
    analyze, confirmAnalyze, dismissDuplicate, reset,
  } = useEnrichment();

  return (
    <div className="min-h-screen bg-melonn-surface">
      <Header />

      <main className="max-w-5xl mx-auto px-6 py-8">
        {/* Form */}
        <div className="flex justify-center mb-8">
          <EnrichmentForm onSubmit={analyze} isLoading={isLoading} />
        </div>

        {/* Content Area */}
        <div className="flex flex-col items-center gap-6">
          {isLoading && <PipelineProgress steps={steps} />}
          {!isLoading && steps.length > 0 && !results && (
            <PipelineProgress steps={steps} />
          )}
          {error && <ErrorDisplay error={error} onRetry={reset} />}
          {results && !isLoading && <ResultsDisplay results={results} />}
        </div>

        {/* Duplicate Warning Modal */}
        {duplicate && duplicate.exists && (
          <DuplicateWarning
            duplicate={duplicate}
            onConfirm={confirmAnalyze}
            onCancel={dismissDuplicate}
          />
        )}
      </main>
    </div>
  );
}
