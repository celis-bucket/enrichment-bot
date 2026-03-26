/**
 * API client for the Enrichment Agent backend
 */

import type {
  EnrichmentV2Results,
  PipelineStep,
  DuplicateCheckResult,
  CompanyListResponse,
  FeedbackItem,
  HubSpotDetail,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || '';

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  if (API_KEY) {
    headers['Authorization'] = `Bearer ${API_KEY}`;
  }
  return headers;
}

export async function analyzeUrlV2(
  url: string,
  onStep: (step: PipelineStep) => void,
  onResult: (result: EnrichmentV2Results) => void,
  onError: (error: string) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v2/enrichment/analyze-stream`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
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
      `${API_BASE}/api/v2/enrichment/check-duplicate?domain=${encodeURIComponent(domain)}`,
      { headers: authHeaders() }
    );
    if (!response.ok) return { exists: false };
    return response.json();
  } catch {
    return { exists: false };
  }
}

export async function getCompanies(params?: {
  page?: number;
  limit?: number;
  search?: string;
  category?: string;
  geography?: string;
  potential_tier?: string;
  sort_by?: string;
}): Promise<CompanyListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set('page', String(params.page));
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.search) searchParams.set('search', params.search);
  if (params?.category) searchParams.set('category', params.category);
  if (params?.geography) searchParams.set('geography', params.geography);
  if (params?.potential_tier) searchParams.set('potential_tier', params.potential_tier);
  if (params?.sort_by) searchParams.set('sort_by', params.sort_by);

  const response = await fetch(
    `${API_BASE}/api/v2/enrichment/companies?${searchParams.toString()}`,
    { headers: authHeaders() }
  );
  if (!response.ok) {
    return { companies: [], total: 0, page: 1, limit: 25 };
  }
  return response.json();
}

export async function getCompany(domain: string): Promise<EnrichmentV2Results> {
  const response = await fetch(
    `${API_BASE}/api/v2/enrichment/companies/${encodeURIComponent(domain)}`,
    { headers: authHeaders() }
  );
  if (!response.ok) {
    throw new Error(`Company not found: ${domain}`);
  }
  return response.json();
}

export async function getHubSpotDetail(companyId: string): Promise<HubSpotDetail> {
  const response = await fetch(
    `${API_BASE}/api/v2/enrichment/hubspot/${encodeURIComponent(companyId)}`,
    { headers: authHeaders() }
  );
  if (!response.ok) {
    throw new Error(`HubSpot detail not found: ${companyId}`);
  }
  return response.json();
}

export async function submitFeedback(
  domain: string,
  section: string,
  comment: string,
  suggestedValue?: string,
  createdBy?: string,
): Promise<{ id: string; saved: boolean }> {
  const response = await fetch(
    `${API_BASE}/api/v2/enrichment/${encodeURIComponent(domain)}/feedback`,
    {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        section,
        comment,
        suggested_value: suggestedValue || null,
        created_by: createdBy || 'anonymous',
      }),
    }
  );
  if (!response.ok) {
    throw new Error(`Failed to submit feedback: HTTP ${response.status}`);
  }
  return response.json();
}

export async function getFeedback(domain: string): Promise<FeedbackItem[]> {
  try {
    const response = await fetch(
      `${API_BASE}/api/v2/enrichment/${encodeURIComponent(domain)}/feedback`,
      { headers: authHeaders() }
    );
    if (!response.ok) return [];
    const data = await response.json();
    return data.feedback || [];
  } catch {
    return [];
  }
}
