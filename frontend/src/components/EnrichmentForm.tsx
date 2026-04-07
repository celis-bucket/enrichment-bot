'use client';

import { useState, FormEvent } from 'react';

interface EnrichmentFormProps {
  onSubmit: (url: string, geography: string) => void;
  isLoading: boolean;
}

export function EnrichmentForm({ onSubmit, isLoading }: EnrichmentFormProps) {
  const [url, setUrl] = useState('');
  const [geography, setGeography] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (url.trim() && geography) {
      onSubmit(url.trim(), geography);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl">
      <div className="flex flex-col gap-3">
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="URL o nombre de marca (ej: armatura.com.co)"
            className="flex-1 px-4 py-3 border-2 border-melonn-purple-100 rounded-xl focus:outline-none focus:ring-2 focus:ring-melonn-purple/30 focus:border-melonn-purple text-melonn-navy placeholder:text-melonn-navy/40 font-body transition-colors"
            disabled={isLoading}
          />
          <select
            value={geography}
            onChange={(e) => setGeography(e.target.value)}
            className="px-4 py-3 border-2 border-melonn-purple-100 rounded-xl focus:outline-none focus:ring-2 focus:ring-melonn-purple/30 focus:border-melonn-purple text-melonn-navy font-body transition-colors bg-white min-w-[160px]"
            disabled={isLoading}
          >
            <option value="" disabled>País...</option>
            <option value="COL">Colombia</option>
            <option value="MEX">México</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={isLoading || !url.trim() || !geography}
          className="px-6 py-3 bg-melonn-green text-white font-semibold rounded-full hover:bg-melonn-green/90 disabled:bg-melonn-surface disabled:text-melonn-navy/40 disabled:cursor-not-allowed transition-colors font-heading"
        >
          {isLoading ? 'Analizando...' : 'Analizar'}
        </button>
      </div>
    </form>
  );
}
