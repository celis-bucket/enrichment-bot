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
  analyze: (url: string, geography: string) => Promise<void>;
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
  const [pendingGeography, setPendingGeography] = useState<string | null>(null);

  const runPipeline = useCallback(async (url: string, geography: string) => {
    setIsLoading(true);
    setError(null);
    setResults(null);
    setSteps([]);
    setDuplicate(null);

    try {
      await analyzeUrlV2(
        url,
        geography,
        (step) => {
          setSteps((prev) => {
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

  const analyze = useCallback(async (url: string, geography: string) => {
    let domain = url.trim();
    domain = domain.replace(/^https?:\/\//, '').split('/')[0].toLowerCase();

    const dupResult = await checkDuplicate(domain);
    if (dupResult.exists) {
      setDuplicate(dupResult);
      setPendingUrl(url);
      setPendingGeography(geography);
      return;
    }

    await runPipeline(url, geography);
  }, [runPipeline]);

  const confirmAnalyze = useCallback(async () => {
    if (pendingUrl && pendingGeography) {
      setDuplicate(null);
      await runPipeline(pendingUrl, pendingGeography);
      setPendingUrl(null);
      setPendingGeography(null);
    }
  }, [pendingUrl, pendingGeography, runPipeline]);

  const dismissDuplicate = useCallback(() => {
    setDuplicate(null);
    setPendingUrl(null);
    setPendingGeography(null);
  }, []);

  const reset = useCallback(() => {
    setResults(null);
    setSteps([]);
    setError(null);
    setDuplicate(null);
    setPendingUrl(null);
    setPendingGeography(null);
  }, []);

  return { results, steps, isLoading, error, duplicate, analyze, confirmAnalyze, dismissDuplicate, reset };
}
