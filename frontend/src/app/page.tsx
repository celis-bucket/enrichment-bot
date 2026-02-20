'use client';

import { useEnrichment } from '@/hooks/useEnrichment';
import { EnrichmentForm } from '@/components/EnrichmentForm';
import { PipelineProgress } from '@/components/PipelineProgress';
import { ErrorDisplay } from '@/components/ErrorDisplay';
import { ResultsDisplay } from '@/components/ResultsDisplay';
import { DuplicateWarning } from '@/components/DuplicateWarning';

export default function Home() {
  const {
    results, steps, isLoading, error, duplicate,
    analyze, confirmAnalyze, dismissDuplicate, reset,
  } = useEnrichment();

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Enrichment Flow V2
          </h1>
          <p className="mt-2 text-gray-600">
            Enrich e-commerce leads with social, contact, and orders estimation data
          </p>
        </div>

        {/* Form */}
        <div className="flex justify-center mb-8">
          <EnrichmentForm onSubmit={analyze} isLoading={isLoading} />
        </div>

        {/* Content Area */}
        <div className="flex flex-col items-center gap-6">
          {/* Pipeline Progress (during loading) */}
          {isLoading && <PipelineProgress steps={steps} />}

          {/* Progress steps remain visible after completion if results are shown */}
          {!isLoading && steps.length > 0 && !results && (
            <PipelineProgress steps={steps} />
          )}

          {/* Error */}
          {error && <ErrorDisplay error={error} onRetry={reset} />}

          {/* Results */}
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
