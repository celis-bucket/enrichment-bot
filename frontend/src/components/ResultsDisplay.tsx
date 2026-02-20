'use client';

import { useState } from 'react';
import type { EnrichmentV2Results } from '@/lib/types';
import { ContactCard } from './ContactCard';
import { PredictionCard } from './PredictionCard';
import { WorkflowReport } from './WorkflowReport';

interface ResultsDisplayProps {
  results: EnrichmentV2Results;
}

function ScoreBadge({ score, label }: { score: number | null | undefined; label: string }) {
  if (score == null) return null;
  const color = score >= 70 ? 'bg-green-100 text-green-800'
    : score >= 40 ? 'bg-yellow-100 text-yellow-800'
    : 'bg-red-100 text-red-800';

  return (
    <div className="flex flex-col items-center">
      <span className={`text-lg font-bold px-3 py-1 rounded-full ${color}`}>{score}</span>
      <span className="text-xs text-gray-500 mt-1">{label}</span>
    </div>
  );
}

export function ResultsDisplay({ results }: ResultsDisplayProps) {
  const [showLog, setShowLog] = useState(false);

  return (
    <div className="w-full max-w-2xl mx-auto space-y-4">
      {/* Header: Company name + domain */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h2 className="text-xl font-bold text-gray-900">
          {results.company_name || results.domain || 'Unknown'}
        </h2>
        {results.domain && results.company_name && (
          <p className="text-sm text-gray-500 mt-1">{results.domain}</p>
        )}
        <div className="flex gap-3 mt-2">
          {results.platform && (
            <span className="text-xs px-2 py-1 bg-indigo-100 text-indigo-700 rounded-full font-medium">
              {results.platform}
            </span>
          )}
          {results.category && (
            <span className="text-xs px-2 py-1 bg-purple-100 text-purple-700 rounded-full font-medium">
              {results.category}
            </span>
          )}
        </div>
      </div>

      {/* Instagram */}
      {(results.instagram_url || results.ig_followers != null) && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Instagram</h3>
          <div className="flex items-center justify-between">
            <div>
              {results.instagram_url && (
                <a href={results.instagram_url} target="_blank" rel="noopener noreferrer"
                   className="text-sm text-blue-600 hover:underline">
                  {results.instagram_url.replace('https://www.instagram.com/', '@').replace(/\/$/, '')}
                </a>
              )}
              {results.ig_followers != null && (
                <p className="text-sm text-gray-600 mt-1">
                  <span className="font-medium">{results.ig_followers.toLocaleString()}</span> followers
                </p>
              )}
            </div>
            <div className="flex gap-4">
              <ScoreBadge score={results.ig_size_score} label="Size" />
              <ScoreBadge score={results.ig_health_score} label="Health" />
            </div>
          </div>
        </div>
      )}

      {/* Contact & Company (Apollo) */}
      <ContactCard
        contactName={results.contact_name}
        contactEmail={results.contact_email}
        companyLinkedin={results.company_linkedin}
        numberEmployes={results.number_employes}
      />

      {/* Orders Prediction */}
      <PredictionCard prediction={results.prediction} />

      {/* Workflow Log (expandable) */}
      {results.workflow_log && results.workflow_log.length > 0 && (
        <div>
          <button
            onClick={() => setShowLog(!showLog)}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            {showLog ? '▾ Hide' : '▸ Show'} execution log ({results.workflow_log.length} steps)
          </button>
          {showLog && (
            <div className="mt-2">
              <WorkflowReport steps={results.workflow_log} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
