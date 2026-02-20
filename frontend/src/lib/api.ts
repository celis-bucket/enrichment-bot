/**
 * API client for the Enrichment Agent backend
 */

import type { EnrichmentResults, EnrichmentV2Results, PipelineStep, DuplicateCheckResult } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ===== V1 (legacy) =====

export async function analyzeUrl(url: string): Promise<EnrichmentResults> {
  const response = await fetch(`${API_BASE}/api/v1/enrichment/analyze-sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Analysis failed' }));
    throw new Error(error.detail || `HTTP ${response.status}: Analysis failed`);
  }

  return response.json();
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

// ===== V2 (SSE Streaming) =====

export async function analyzeUrlV2(
  url: string,
  onStep: (step: PipelineStep) => void,
  onResult: (result: EnrichmentV2Results) => void,
  onError: (error: string) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v2/enrichment/analyze-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Analysis failed' }));
    throw new Error(error.detail || `HTTP ${response.status}: Analysis failed`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse SSE events from buffer
    const lines = buffer.split('\n');
    buffer = lines.pop() || ''; // Keep incomplete line in buffer

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const jsonStr = line.slice(6).trim();
      if (!jsonStr) continue;

      try {
        const msg = JSON.parse(jsonStr);

        if (msg.type === 'step') {
          onStep({
            step: msg.step,
            status: msg.status,
            duration_ms: msg.duration_ms,
            detail: msg.detail,
          });
        } else if (msg.type === 'result') {
          onResult(msg.data);
        } else if (msg.type === 'error') {
          onError(msg.detail || 'Unknown pipeline error');
        }
      } catch {
        // Skip malformed JSON lines
      }
    }
  }
}

export async function checkDuplicate(domain: string): Promise<DuplicateCheckResult> {
  try {
    const response = await fetch(
      `${API_BASE}/api/v2/enrichment/check-duplicate?domain=${encodeURIComponent(domain)}`
    );
    if (!response.ok) return { exists: false };
    return response.json();
  } catch {
    return { exists: false };
  }
}
