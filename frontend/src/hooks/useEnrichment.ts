'use client';

import { useState, useCallback } from 'react';
import { analyzeUrlV2, checkDuplicate } from '@/lib/api';
import type { EnrichmentV2Results, PipelineStep, DuplicateCheckResult } from '@/lib/types';

interface UseEnrichmentReturn {
  results: EnrichmentV2Results | null;
  steps: PipelineStep[];
  isLoading: boolean;
  error: string | null;
  duplicate: DuplicateCheckResult | null;
  analyze: (url: string) => Promise<void>;
  confirmAnalyze: () => Promise<void>;
  dismissDuplicate: () => void;
  reset: () => void;
}

export function useEnrichment(): UseEnrichmentReturn {
  const [results, setResults] = useState<EnrichmentV2Results | null>(null);
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<DuplicateCheckResult | null>(null);
  const [pendingUrl, setPendingUrl] = useState<string | null>(null);

  const runPipeline = useCallback(async (url: string) => {
    setIsLoading(true);
    setError(null);
    setResults(null);
    setSteps([]);
    setDuplicate(null);

    try {
      await analyzeUrlV2(
        url,
        (step) => {
          setSteps((prev) => {
            // Update existing step if it was "running", otherwise add new
            const idx = prev.findIndex((s) => s.step === step.step);
            if (idx >= 0) {
              const updated = [...prev];
              updated[idx] = step;
              return updated;
            }
            return [...prev, step];
          });
        },
        (result) => {
          setResults(result);
        },
        (err) => {
          setError(err);
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const analyze = useCallback(async (url: string) => {
    // Extract domain for duplicate check
    let domain = url.trim();
    // Simple domain extraction: remove protocol and path
    domain = domain.replace(/^https?:\/\//, '').split('/')[0].toLowerCase();

    // Check for duplicates first
    const dupResult = await checkDuplicate(domain);
    if (dupResult.exists) {
      setDuplicate(dupResult);
      setPendingUrl(url);
      return;
    }

    // No duplicate — run immediately
    await runPipeline(url);
  }, [runPipeline]);

  const confirmAnalyze = useCallback(async () => {
    if (pendingUrl) {
      setDuplicate(null);
      await runPipeline(pendingUrl);
      setPendingUrl(null);
    }
  }, [pendingUrl, runPipeline]);

  const dismissDuplicate = useCallback(() => {
    setDuplicate(null);
    setPendingUrl(null);
  }, []);

  const reset = useCallback(() => {
    setResults(null);
    setSteps([]);
    setError(null);
    setDuplicate(null);
    setPendingUrl(null);
  }, []);

  return { results, steps, isLoading, error, duplicate, analyze, confirmAnalyze, dismissDuplicate, reset };
}
