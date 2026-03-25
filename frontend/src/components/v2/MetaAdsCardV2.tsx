'use client';

import type { FeedbackItem } from '@/lib/types';
import { FeedbackPanel } from '../FeedbackPanel';

interface MetaAdsCardV2Props {
  activeAdsCount?: number | null;
  adLibraryUrl?: string | null;
  domain?: string;
  feedback?: FeedbackItem[];
}

export function MetaAdsCardV2({ activeAdsCount, adLibraryUrl, domain = '', feedback = [] }: MetaAdsCardV2Props) {
  if (activeAdsCount == null) {
    return (
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-2">Anuncios en META</h3>
        <p className="text-sm text-melonn-navy/40">No hay datos de anuncios disponibles</p>
        {domain && <FeedbackPanel domain={domain} section="meta_ads" existingFeedback={feedback} />}
      </div>
    );
  }

  const hasAds = activeAdsCount > 0;
  const intensityLabel =
    activeAdsCount >= 100 ? 'Anunciante fuerte'
    : activeAdsCount >= 20 ? 'Anunciante activo'
    : activeAdsCount > 0 ? 'Anunciante ligero'
    : 'Sin anuncios activos';
  const intensityColor =
    activeAdsCount >= 100 ? 'bg-melonn-purple-50 text-melonn-purple'
    : activeAdsCount >= 20 ? 'bg-melonn-green-50 text-melonn-green'
    : activeAdsCount > 0 ? 'bg-melonn-orange-50 text-melonn-orange'
    : 'bg-melonn-surface text-melonn-navy/50';

  return (
    <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading">Anuncios en META</h3>
        <span className={`text-xs px-3 py-1 rounded-full font-medium ${intensityColor}`}>
          {intensityLabel}
        </span>
      </div>

      <div className="text-center mb-3">
        <span className="text-3xl font-bold text-melonn-navy font-heading">
          {activeAdsCount.toLocaleString()}
        </span>
        <p className="text-xs text-melonn-navy/50 mt-1">Anuncios activos en Meta Ad Library</p>
      </div>

      {hasAds && adLibraryUrl && (
        <a
          href={adLibraryUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full text-center text-sm text-melonn-purple hover:text-melonn-purple-light transition-colors py-1"
        >
          Ver en Meta Ad Library
        </a>
      )}

      {domain && <FeedbackPanel domain={domain} section="meta_ads" existingFeedback={feedback} />}
    </div>
  );
}
