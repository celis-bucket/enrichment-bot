'use client';

import { useState, FormEvent } from 'react';

interface EnrichmentFormProps {
  onSubmit: (url: string) => void;
  isLoading: boolean;
}

export function EnrichmentForm({ onSubmit, isLoading }: EnrichmentFormProps) {
  const [url, setUrl] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (url.trim()) {
      onSubmit(url.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl">
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Enter URL or brand name (e.g., armatura.com.co or Armatura Colombia)"
          className="flex-1 px-4 py-3 border-2 border-melonn-purple-100 rounded-xl focus:outline-none focus:ring-2 focus:ring-melonn-purple/30 focus:border-melonn-purple text-melonn-navy placeholder:text-melonn-navy/40 font-body transition-colors"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !url.trim()}
          className="px-6 py-3 bg-melonn-green text-white font-semibold rounded-full hover:bg-melonn-green/90 disabled:bg-melonn-surface disabled:text-melonn-navy/40 disabled:cursor-not-allowed transition-colors font-heading"
        >
          {isLoading ? 'Analyzing...' : 'Analyze'}
        </button>
      </div>
    </form>
  );
}
