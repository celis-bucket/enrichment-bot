'use client';

import { useState, useRef } from 'react';
import { Header } from '@/components/Header';
import { FeedbackPanel } from '@/components/FeedbackPanel';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || '';

interface StepEvent {
  step: string;
  status: string;
  duration_ms: number;
  detail: string;
}

interface RetailResult {
  has_distributors: boolean | null;
  has_own_stores: boolean | null;
  own_store_count_col: number | null;
  own_store_count_mex: number | null;
  has_multibrand_stores: boolean | null;
  multibrand_store_names: string[];
  on_mercadolibre: boolean | null;
  on_amazon: boolean | null;
  on_rappi: boolean | null;
  retail_confidence: number | null;
}

const STATUS_ICONS: Record<string, string> = {
  ok: '\u2705',
  warn: '\u26A0\uFE0F',
  fail: '\u274C',
  running: '\u23F3',
};

function BoolBadge({ value, label }: { value: boolean | null; label: string }) {
  if (value === null) return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm bg-gray-100 text-gray-400">
      {label}: N/A
    </span>
  );
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium ${
      value ? 'bg-melonn-green-50 text-green-700' : 'bg-gray-100 text-gray-500'
    }`}>
      {value ? '\u2705' : '\u2014'} {label}
    </span>
  );
}

export default function RetailPage() {
  const [domain, setDomain] = useState('');
  const [geography, setGeography] = useState('');
  const [steps, setSteps] = useState<StepEvent[]>([]);
  const [result, setResult] = useState<RetailResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [analyzedDomain, setAnalyzedDomain] = useState('');
  const abortRef = useRef<AbortController | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!domain.trim() || running) return;

    // Clean domain
    let cleanDomain = domain.trim().toLowerCase();
    cleanDomain = cleanDomain.replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/.*$/, '');

    setSteps([]);
    setResult(null);
    setError('');
    setRunning(true);
    setAnalyzedDomain(cleanDomain);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (API_KEY) headers['Authorization'] = `Bearer ${API_KEY}`;

      const response = await fetch(`${API_BASE}/api/v2/retail/analyze-stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ domain: cleanDomain, geography }),
        signal: controller.signal,
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const msg = JSON.parse(line.slice(6));
            if (msg.type === 'step') {
              setSteps(prev => [...prev, msg]);
            } else if (msg.type === 'result') {
              setResult(msg.data);
            } else if (msg.type === 'error') {
              setError(msg.detail);
            }
          } catch { /* skip malformed */ }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message);
      }
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="min-h-screen bg-melonn-surface">
      <Header />
      <main className="max-w-3xl mx-auto px-6 py-8">
        <h2 className="text-2xl font-bold text-melonn-navy font-heading mb-1">
          Retail Channel Evaluation
        </h2>
        <p className="text-sm text-gray-500 mb-6">
          Detect physical retail presence: distributors, own stores, department stores, and marketplaces.
        </p>

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-xl p-6 shadow-sm mb-6">
          <div className="flex gap-3">
            <input
              type="text"
              value={domain}
              onChange={e => setDomain(e.target.value)}
              placeholder="e.g. youaresavvy.com"
              className="flex-1 px-4 py-2.5 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-melonn-purple focus:border-transparent"
              disabled={running}
            />
            <select
              value={geography}
              onChange={e => setGeography(e.target.value)}
              className="px-3 py-2.5 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-melonn-purple"
              disabled={running}
            >
              <option value="">Both countries</option>
              <option value="COL">Colombia</option>
              <option value="MEX">Mexico</option>
            </select>
            <button
              type="submit"
              disabled={running || !domain.trim()}
              className="px-6 py-2.5 rounded-lg bg-melonn-purple text-white text-sm font-medium hover:bg-melonn-navy transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {running ? 'Analyzing...' : 'Analyze'}
            </button>
          </div>
        </form>

        {/* Pipeline Steps */}
        {steps.length > 0 && (
          <div className="bg-white rounded-xl p-6 shadow-sm mb-6">
            <h3 className="text-sm font-semibold text-melonn-navy mb-3">Pipeline</h3>
            <div className="space-y-1.5">
              {steps.map((s, i) => (
                <div key={i} className="flex items-center gap-3 text-sm font-mono">
                  <span className="w-5 text-center">{STATUS_ICONS[s.status] || '?'}</span>
                  <span className="w-48 text-gray-700 truncate">{s.step}</span>
                  <span className="w-16 text-right text-gray-400">{s.duration_ms}ms</span>
                  <span className="flex-1 text-gray-500 truncate">{s.detail}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="bg-white rounded-xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-bold text-melonn-navy font-heading">Results</h3>
              <span className="text-xs px-2.5 py-1 rounded-full bg-melonn-purple-50 text-melonn-purple font-medium">
                Confidence: {((result.retail_confidence ?? 0) * 100).toFixed(0)}%
              </span>
            </div>

            {/* Channel Grid */}
            <div className="grid grid-cols-1 gap-4">
              {/* Distributors */}
              <div className="border border-gray-100 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-melonn-navy">Distribuidores / Mayoristas</span>
                  <BoolBadge value={result.has_distributors} label={result.has_distributors ? 'Yes' : 'No'} />
                </div>
              </div>

              {/* Own Stores */}
              <div className="border border-gray-100 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-melonn-navy">Tiendas Propias</span>
                  <BoolBadge value={result.has_own_stores} label={result.has_own_stores ? 'Yes' : 'No'} />
                </div>
                {result.has_own_stores && (
                  <div className="mt-2 flex gap-4 text-sm text-gray-500">
                    {result.own_store_count_col != null && (
                      <span>COL: <strong className="text-melonn-navy">{result.own_store_count_col}</strong></span>
                    )}
                    {result.own_store_count_mex != null && (
                      <span>MEX: <strong className="text-melonn-navy">{result.own_store_count_mex}</strong></span>
                    )}
                  </div>
                )}
              </div>

              {/* Multi-brand Stores */}
              <div className="border border-gray-100 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-melonn-navy">Tiendas Multimarca</span>
                  <BoolBadge value={result.has_multibrand_stores} label={result.has_multibrand_stores ? 'Yes' : 'No'} />
                </div>
                {result.multibrand_store_names.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {result.multibrand_store_names.map(name => (
                      <span key={name} className="px-2.5 py-1 rounded-full bg-melonn-cyan-50 text-melonn-navy text-xs font-medium">
                        {name}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Marketplaces */}
              <div className="border border-gray-100 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-melonn-navy">Marketplaces</span>
                </div>
                <div className="flex gap-2">
                  <BoolBadge value={result.on_mercadolibre} label="MercadoLibre" />
                  <BoolBadge value={result.on_amazon} label="Amazon" />
                  <BoolBadge value={result.on_rappi} label="Rappi" />
                </div>
              </div>
            </div>

            {/* Feedback */}
            <FeedbackPanel domain={analyzedDomain} section="retail" />
          </div>
        )}
      </main>
    </div>
  );
}
