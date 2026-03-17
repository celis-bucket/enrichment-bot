'use client';

import { useState } from 'react';
import type { EnrichmentV2Results } from '@/lib/types';
import { CompanyOverviewCard } from './CompanyOverviewCard';
import { CatalogCard } from './CatalogCard';
import { TrafficDemandCard } from './TrafficDemandCard';
import { ContactCard } from './ContactCard';
import { MetaAdsCard } from './MetaAdsCard';
import { PredictionCard } from './PredictionCard';
import { WorkflowReport } from './WorkflowReport';

interface ResultsDisplayProps {
  results: EnrichmentV2Results;
}

function ScoreBadge({ score, label }: { score: number | null | undefined; label: string }) {
  if (score == null) return null;
  const color = score >= 70 ? 'bg-melonn-green-50 text-melonn-green'
    : score >= 40 ? 'bg-melonn-orange-50 text-melonn-orange'
    : 'bg-red-50 text-red-600';

  return (
    <div className="flex flex-col items-center">
      <span className={`text-lg font-bold px-3 py-1 rounded-full font-heading ${color}`}>{score}</span>
      <span className="text-xs text-melonn-navy/50 mt-1">{label}</span>
    </div>
  );
}

export function ResultsDisplay({ results }: ResultsDisplayProps) {
  const [showLog, setShowLog] = useState(false);

  return (
    <div className="w-full max-w-5xl mx-auto space-y-4">
      {/* Header: Company name + domain */}
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <h2 className="text-xl font-bold text-melonn-navy font-heading">
          {results.company_name || results.domain || 'Unknown'}
        </h2>
        {results.domain && results.company_name && (
          <p className="text-sm text-melonn-navy/50 mt-1">{results.domain}</p>
        )}
        <div className="flex gap-3 mt-2">
          {results.platform && (
            <span className="text-xs px-3 py-1 bg-melonn-purple-50 text-melonn-purple rounded-full font-medium">
              {results.platform}
            </span>
          )}
          {results.category && (
            <span className="text-xs px-3 py-1 bg-melonn-cyan-50 text-melonn-cyan rounded-full font-medium">
              {results.category}
            </span>
          )}
        </div>
      </div>

      {/* Company Overview (full-width) */}
      <CompanyOverviewCard
        geography={results.geography}
        geographyConfidence={results.geography_confidence}
        platform={results.platform}
        platformConfidence={results.platform_confidence}
        category={results.category}
        categoryConfidence={results.category_confidence}
        categoryEvidence={results.category_evidence}
        fulfillmentProvider={results.fulfillment_provider}
        fulfillmentConfidence={results.fulfillment_confidence}
        toolCoveragePct={results.tool_coverage_pct}
        totalRuntimeSec={results.total_runtime_sec}
        costEstimateUsd={results.cost_estimate_usd}
      />

      {/* Data Grid - 2 columns on desktop */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Instagram */}
        {(results.instagram_url || results.ig_followers != null) && (
          <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
            <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-3">Instagram</h3>
            <div className="flex items-center justify-between">
              <div>
                {results.instagram_url && (
                  <a href={results.instagram_url} target="_blank" rel="noopener noreferrer"
                     className="text-sm text-melonn-purple hover:text-melonn-purple-light transition-colors">
                    {results.instagram_url.replace('https://www.instagram.com/', '@').replace(/\/$/, '')}
                  </a>
                )}
                {results.ig_followers != null && (
                  <p className="text-sm text-melonn-navy/70 mt-1">
                    <span className="font-medium text-melonn-navy">{results.ig_followers.toLocaleString()}</span> followers
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

        {/* Product Catalog */}
        <CatalogCard
          productCount={results.product_count}
          avgPrice={results.avg_price}
          priceRangeMin={results.price_range_min}
          priceRangeMax={results.price_range_max}
          currency={results.currency}
        />

        {/* Traffic & Demand */}
        <TrafficDemandCard
          estimatedMonthlyVisits={results.estimated_monthly_visits}
          trafficConfidence={results.traffic_confidence}
          signalsUsed={results.signals_used}
          brandDemandScore={results.brand_demand_score}
          siteSerpCoverageScore={results.site_serp_coverage_score}
          googleConfidence={results.google_confidence}
        />

        {/* META Ads */}
        <MetaAdsCard
          activeAdsCount={results.meta_active_ads_count}
          adLibraryUrl={results.meta_ad_library_url}
        />

        {/* Contact & Company (Apollo) */}
        <ContactCard
          contacts={results.contacts}
          contactName={results.contact_name}
          contactEmail={results.contact_email}
          companyLinkedin={results.company_linkedin}
          numberEmployes={results.number_employes}
        />

        {/* Orders Prediction */}
        <PredictionCard prediction={results.prediction} />
      </div>

      {/* Workflow Log (expandable) */}
      {results.workflow_log && results.workflow_log.length > 0 && (
        <div>
          <button
            onClick={() => setShowLog(!showLog)}
            className="text-xs text-melonn-navy/40 hover:text-melonn-navy/60 transition-colors"
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
