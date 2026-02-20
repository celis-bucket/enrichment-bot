'use client';

import { SocialMediaInfo } from '@/lib/types';

interface SocialLinksCardProps {
  socialMedia: SocialMediaInfo;
}

const socialIcons: Record<string, string> = {
  instagram: 'M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z',
  facebook: 'M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z',
  tiktok: 'M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z',
  youtube: 'M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z',
  linkedin: 'M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z',
};

const socialColors: Record<string, string> = {
  instagram: 'text-pink-600',
  facebook: 'text-blue-600',
  tiktok: 'text-black',
  youtube: 'text-red-600',
  linkedin: 'text-blue-700',
};

export function SocialLinksCard({ socialMedia }: SocialLinksCardProps) {
  const { instagram, facebook, tiktok, youtube, linkedin } = socialMedia;

  // Helper to get score color
  const getScoreColor = (score: number) => {
    if (score >= 70) return 'text-green-600 bg-green-50 border-green-200';
    if (score >= 40) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-red-600 bg-red-50 border-red-200';
  };

  // Check if any social links exist
  const hasLinks = instagram || facebook || tiktok || youtube || linkedin;

  if (!hasLinks) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Social Media</h3>
        <p className="mt-2 text-gray-400">No social media links found</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-4">Social Media</h3>

      {/* Instagram with metrics (if available) */}
      {instagram && instagram.followers ? (
        <div className="mb-4 p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg border border-purple-100">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <svg className="w-6 h-6 text-pink-600" fill="currentColor" viewBox="0 0 24 24">
                <path d={socialIcons.instagram} />
              </svg>
              <span className="font-semibold text-gray-900">Instagram</span>
              {instagram.is_verified && (
                <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              )}
            </div>

            {/* IG Score Badges */}
            <div className="flex gap-2">
              {instagram.ig_size_score != null && (
                <div className={`px-3 py-2 rounded-lg border-2 ${getScoreColor(instagram.ig_size_score)}`}>
                  <div className="text-xl font-bold">{instagram.ig_size_score}/100</div>
                  <div className="text-xs font-medium uppercase">Size</div>
                </div>
              )}
              {instagram.ig_health_score != null && (
                <div className={`px-3 py-2 rounded-lg border-2 ${getScoreColor(instagram.ig_health_score)}`}>
                  <div className="text-xl font-bold">{instagram.ig_health_score}/100</div>
                  <div className="text-xs font-medium uppercase">Health</div>
                </div>
              )}
            </div>
          </div>

          {/* Inline Metrics */}
          <div className="flex items-center gap-4 text-sm text-gray-700">
            <div>
              <span className="font-semibold">{instagram.followers?.toLocaleString()}</span>
              <span className="text-gray-500"> followers</span>
            </div>
            <span className="text-gray-300">•</span>
            <div>
              <span className="font-semibold">{instagram.engagement_rate?.toFixed(2)}%</span>
              <span className="text-gray-500"> engagement</span>
            </div>
          </div>

          {/* Additional Insights (if available) */}
          {(instagram.product_tags_count !== null || instagram.avg_days_between_posts !== null) && (
            <div className="mt-2 pt-2 border-t border-purple-100 flex gap-4 text-xs text-gray-600">
              {instagram.product_tags_count !== null && instagram.product_tags_count > 0 && (
                <div>📦 {instagram.product_tags_count} tagged products</div>
              )}
              {instagram.avg_days_between_posts !== null && (
                <div>📅 Posts every {instagram.avg_days_between_posts.toFixed(1)} days</div>
              )}
            </div>
          )}

          <a
            href={instagram.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-block text-sm text-purple-600 hover:text-purple-800 font-medium"
          >
            View Profile →
          </a>
        </div>
      ) : instagram ? (
        // Instagram link exists but no metrics
        <div className="mb-2">
          <a
            href={instagram.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors text-pink-600"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d={socialIcons.instagram} />
            </svg>
            <span className="text-sm font-medium">Instagram</span>
            <span className="ml-auto text-xs text-gray-500">Metrics unavailable</span>
          </a>
        </div>
      ) : null}

      {/* Other social platforms (Facebook, TikTok, etc.) - simple links */}
      <div className="flex flex-wrap gap-2">
        {facebook && (
          <a href={facebook.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors text-blue-600">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d={socialIcons.facebook} /></svg>
            <span className="text-sm font-medium">Facebook</span>
          </a>
        )}
        {tiktok && (
          <a href={tiktok.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors text-black">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d={socialIcons.tiktok} /></svg>
            <span className="text-sm font-medium">TikTok</span>
          </a>
        )}
        {youtube && (
          <a href={youtube.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors text-red-600">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d={socialIcons.youtube} /></svg>
            <span className="text-sm font-medium">YouTube</span>
          </a>
        )}
        {linkedin && (
          <a href={linkedin.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors text-blue-700">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d={socialIcons.linkedin} /></svg>
            <span className="text-sm font-medium">LinkedIn</span>
          </a>
        )}
      </div>
    </div>
  );
}
