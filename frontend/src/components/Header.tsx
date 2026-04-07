'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { refreshLeadData } from '@/lib/api';

export function Header() {
  const pathname = usePathname();
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState('');

  const handleRefreshHubSpot = async () => {
    setRefreshing(true);
    setRefreshMsg('Iniciando refresh...');
    try {
      await refreshLeadData(
        (detail) => setRefreshMsg(detail),
        () => { setRefreshMsg('Refresh completado'); },
        (err) => { setRefreshMsg(`Error: ${err}`); },
      );
    } catch (err) {
      setRefreshMsg(`Error: ${err}`);
    } finally {
      setTimeout(() => { setRefreshing(false); setRefreshMsg(''); }, 3000);
    }
  };

  return (
    <header className="bg-melonn-navy">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 sm:gap-6 min-w-0 flex-1">
          <div className="shrink-0">
            <h1 className="text-base sm:text-xl font-bold text-white font-heading tracking-tight">
              Enrichment Agent
            </h1>
            <p className="text-[10px] sm:text-xs text-melonn-purple-light hidden sm:block">
              E-commerce lead intelligence
            </p>
          </div>
          <nav className="flex gap-0.5 overflow-x-auto [scrollbar-width:none] [-webkit-overflow-scrolling:touch] [&::-webkit-scrollbar]:hidden">
            <Link
              href="/analyze-v2"
              className={`px-2 sm:px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors shrink-0 ${
                pathname === '/analyze-v2' || pathname === '/'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Analizar
            </Link>
            <Link
              href="/history"
              className={`px-2 sm:px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors shrink-0 ${
                pathname === '/history'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              History
            </Link>
            <Link
              href="/leads"
              className={`px-2 sm:px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors shrink-0 ${
                pathname === '/leads'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Leads
            </Link>
            <Link
              href="/team"
              className={`px-2 sm:px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors shrink-0 ${
                pathname === '/team'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Mi Pipeline
            </Link>
            <Link
              href="/potential"
              className={`px-2 sm:px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors shrink-0 ${
                pathname === '/potential'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Potential
            </Link>
            <Link
              href="/retail"
              className={`px-2 sm:px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors shrink-0 ${
                pathname === '/retail'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Retail
            </Link>
            <Link
              href="/tiktok"
              className={`px-2 sm:px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors shrink-0 ${
                pathname === '/tiktok'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              TikTok
            </Link>
            <Link
              href="/conexion"
              className={`px-2 sm:px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors shrink-0 ${
                pathname?.startsWith('/conexion')
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Conexion
            </Link>
          </nav>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          {refreshMsg && (
            <span className="text-[10px] text-melonn-purple-light max-w-[200px] truncate hidden sm:block">{refreshMsg}</span>
          )}
          <button
            onClick={handleRefreshHubSpot}
            disabled={refreshing}
            title="Actualizar datos de HubSpot (stages, owners, actividad) para leads existentes"
            className="px-2.5 py-1.5 rounded-md text-xs font-medium border border-melonn-purple-light text-melonn-purple-light
                       hover:bg-melonn-navy-light transition-colors disabled:opacity-50 whitespace-nowrap"
          >
            {refreshing ? 'Refreshing...' : 'Refresh HubSpot'}
          </button>
          <div className="w-3 h-3 rounded-full bg-melonn-green" />
        </div>
      </div>
    </header>
  );
}
