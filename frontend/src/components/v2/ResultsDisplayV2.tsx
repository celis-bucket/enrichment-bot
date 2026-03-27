'use client';

import { useState, useEffect } from 'react';
import type { EnrichmentV2Results, FeedbackItem } from '@/lib/types';
import { getFeedback } from '@/lib/api';
import { CompanyOverviewCardV2 } from './CompanyOverviewCardV2';
import { CatalogCardV2 } from './CatalogCardV2';
import { TrafficDemandCardV2 } from './TrafficDemandCardV2';
import { ContactCardV2 } from './ContactCardV2';
import { MetaAdsCardV2 } from './MetaAdsCardV2';
import { TikTokAdsCardV2 } from './TikTokAdsCardV2';
import { PredictionCardV2 } from './PredictionCardV2';
import { HubSpotCardV2 } from './HubSpotCardV2';
import { RetailChannelsCardV2 } from './RetailChannelsCardV2';
import { PotentialScoreCardV2 } from './PotentialScoreCardV2';
import { WorkflowReport } from '../WorkflowReport';
import { FeedbackPanel } from '../FeedbackPanel';

interface ResultsDisplayV2Props {
  results: EnrichmentV2Results;
}

export function ResultsDisplayV2({ results }: ResultsDisplayV2Props) {
  const [showLog, setShowLog] = useState(false);
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);
  const domain = results.domain || '';

  useEffect(() => {
    if (domain) {
      getFeedback(domain).then(setFeedback).catch(() => {});
    }
  }, [domain]);

  return (
    <div className="w-full max-w-5xl mx-auto space-y-4">
      {/* Header: Company name + domain */}
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <h2 className="text-xl font-bold text-melonn-navy font-heading">
          {results.company_name || results.domain || 'Desconocido'}
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
        <FeedbackPanel domain={domain} section="general" existingFeedback={feedback} />
      </div>

      {/* Company Overview (full-width) */}
      <CompanyOverviewCardV2
        geography={results.geography}
        geographyConfidence={results.geography_confidence}
        platform={results.platform}
        platformConfidence={results.platform_confidence}
        category={results.category}
        categoryConfidence={results.category_confidence}
        categoryEvidence={results.category_evidence}
        toolCoveragePct={results.tool_coverage_pct}
        totalRuntimeSec={results.total_runtime_sec}
        costEstimateUsd={results.cost_estimate_usd}
        domain={domain}
        feedback={feedback}
      />

      {/* Data Grid - 2 columns on desktop */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Redes Sociales - Instagram, Facebook, TikTok */}
        {(results.instagram_url || results.ig_followers != null || results.fb_followers != null || results.tiktok_followers != null) && (
          <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
            <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-3">Redes Sociales</h3>
            <div className="space-y-3">
              {(results.instagram_url || results.ig_followers != null) && (
                <div>
                  <p className="text-xs text-melonn-navy/50 mb-0.5">Instagram</p>
                  {results.instagram_url && (
                    <a href={results.instagram_url} target="_blank" rel="noopener noreferrer"
                       className="text-sm text-melonn-purple hover:text-melonn-purple-light transition-colors">
                      {results.instagram_url.replace('https://instagram.com/', '@').replace('https://www.instagram.com/', '@').replace(/\/$/, '')}
                    </a>
                  )}
                  {results.ig_followers != null && (
                    <p className="text-sm text-melonn-navy/70">
                      <span className="font-medium text-melonn-navy">{results.ig_followers.toLocaleString()}</span> seguidores
                    </p>
                  )}
                </div>
              )}
              {results.fb_followers != null && results.fb_followers > 0 && (
                <div className="flex items-center justify-between py-1.5 border-t border-melonn-purple-50/50">
                  <span className="text-xs text-melonn-navy/50">Facebook</span>
                  <span className="text-sm font-medium text-melonn-navy">{results.fb_followers.toLocaleString()} seguidores</span>
                </div>
              )}
              {results.tiktok_followers != null && results.tiktok_followers > 0 && (
                <div className="flex items-center justify-between py-1.5 border-t border-melonn-purple-50/50">
                  <span className="text-xs text-melonn-navy/50">TikTok</span>
                  <span className="text-sm font-medium text-melonn-navy">{results.tiktok_followers.toLocaleString()} seguidores</span>
                </div>
              )}
            </div>
            <FeedbackPanel domain={domain} section="instagram" existingFeedback={feedback} />
          </div>
        )}

        {/* Catálogo de Productos */}
        <CatalogCardV2
          productCount={results.product_count}
          avgPrice={results.avg_price}
          priceRangeMin={results.price_range_min}
          priceRangeMax={results.price_range_max}
          currency={results.currency}
          domain={domain}
          feedback={feedback}
        />

        {/* Tráfico Web */}
        <TrafficDemandCardV2
          estimatedMonthlyVisits={results.estimated_monthly_visits}
          trafficConfidence={results.traffic_confidence}
          signalsUsed={results.signals_used}
          brandDemandScore={results.brand_demand_score}
          siteSerpCoverageScore={results.site_serp_coverage_score}
          googleConfidence={results.google_confidence}
          domain={domain}
          feedback={feedback}
        />

        {/* Anuncios en META */}
        <MetaAdsCardV2
          activeAdsCount={results.meta_active_ads_count}
          adLibraryUrl={results.meta_ad_library_url}
          domain={domain}
          feedback={feedback}
        />

        {/* Anuncios en TikTok */}
        <TikTokAdsCardV2
          activeAdsCount={results.tiktok_active_ads_count}
          adLibraryUrl={results.tiktok_ads_library_url}
          domain={domain}
          feedback={feedback}
        />

        {/* Contactos y Empresa (Apollo) */}
        <ContactCardV2
          contacts={results.contacts}
          contactName={results.contact_name}
          contactEmail={results.contact_email}
          companyLinkedin={results.company_linkedin}
          numberEmployes={results.number_employes}
          domain={domain}
          feedback={feedback}
        />

        {/* HubSpot CRM */}
        <HubSpotCardV2
          hubspotCompanyId={results.hubspot_company_id}
          hubspotCompanyUrl={results.hubspot_company_url}
          hubspotDealCount={results.hubspot_deal_count}
          hubspotDealStage={results.hubspot_deal_stage}
          hubspotContactExists={results.hubspot_contact_exists}
          hubspotLifecycleLabel={results.hubspot_lifecycle_label}
          hubspotLastContacted={results.hubspot_last_contacted}
          domain={domain}
          feedback={feedback}
        />

        {/* Órdenes Estimadas */}
        <PredictionCardV2
          prediction={results.prediction}
          domain={domain}
          feedback={feedback}
        />

        {/* Canales Retail */}
        <RetailChannelsCardV2
          results={results}
          domain={domain}
          feedback={feedback}
        />
      </div>

      {/* Potential Score (full-width) */}
      <PotentialScoreCardV2 results={results} />

      {/* Workflow Log */}
      {results.workflow_log && results.workflow_log.length > 0 && (
        <div>
          <button
            onClick={() => setShowLog(!showLog)}
            className="text-xs text-melonn-navy/40 hover:text-melonn-navy/60 transition-colors"
          >
            {showLog ? '▾ Ocultar' : '▸ Mostrar'} registro de ejecución ({results.workflow_log.length} pasos)
          </button>
          {showLog && (
            <div className="mt-2">
              <WorkflowReport
                steps={results.workflow_log}
                totalRuntimeSec={results.total_runtime_sec}
                costEstimateUsd={results.cost_estimate_usd}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
