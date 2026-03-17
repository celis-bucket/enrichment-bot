'use client';

interface MetaAdsCardProps {
  activeAdsCount?: number | null;
  adLibraryUrl?: string | null;
}

export function MetaAdsCard({ activeAdsCount, adLibraryUrl }: MetaAdsCardProps) {
  if (activeAdsCount == null) {
    return (
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-2">META Ads</h3>
        <p className="text-sm text-melonn-navy/40">No META ads data available</p>
      </div>
    );
  }

  const hasAds = activeAdsCount > 0;
  const intensityLabel =
    activeAdsCount >= 100 ? 'Heavy advertiser'
    : activeAdsCount >= 20 ? 'Active advertiser'
    : activeAdsCount > 0 ? 'Light advertiser'
    : 'No active ads';
  const intensityColor =
    activeAdsCount >= 100 ? 'bg-melonn-purple-50 text-melonn-purple'
    : activeAdsCount >= 20 ? 'bg-melonn-green-50 text-melonn-green'
    : activeAdsCount > 0 ? 'bg-melonn-orange-50 text-melonn-orange'
    : 'bg-melonn-surface text-melonn-navy/50';

  return (
    <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading">META Ads</h3>
        <span className={`text-xs px-3 py-1 rounded-full font-medium ${intensityColor}`}>
          {intensityLabel}
        </span>
      </div>

      <div className="text-center mb-3">
        <span className="text-3xl font-bold text-melonn-navy font-heading">
          {activeAdsCount.toLocaleString()}
        </span>
        <p className="text-xs text-melonn-navy/50 mt-1">Active ads in Meta Ad Library</p>
      </div>

      {hasAds && adLibraryUrl && (
        <a
          href={adLibraryUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full text-center text-sm text-melonn-purple hover:text-melonn-purple-light transition-colors py-1"
        >
          View in Meta Ad Library
        </a>
      )}
    </div>
  );
}
