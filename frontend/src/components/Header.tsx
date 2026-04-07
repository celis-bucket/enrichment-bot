'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function Header() {
  const pathname = usePathname();

  return (
    <header className="bg-melonn-navy">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between">
        <div className="flex items-center gap-4 sm:gap-8 min-w-0 flex-1">
          <div className="shrink-0">
            <h1 className="text-base sm:text-xl font-bold text-white font-heading tracking-tight">
              Enrichment Agent
            </h1>
            <p className="text-[10px] sm:text-xs text-melonn-purple-light hidden sm:block">
              E-commerce lead intelligence
            </p>
          </div>
          <nav className="flex gap-1 overflow-x-auto scrollbar-hide">
            <Link
              href="/analyze-v2"
              className={`px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-colors shrink-0 ${
                pathname === '/analyze-v2' || pathname === '/'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Analizar
            </Link>
            <Link
              href="/history"
              className={`px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-colors shrink-0 ${
                pathname === '/history'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              History
            </Link>
            <Link
              href="/leads"
              className={`px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-colors shrink-0 ${
                pathname === '/leads'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Leads
            </Link>
            <Link
              href="/team"
              className={`px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-colors shrink-0 ${
                pathname === '/team'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Mi Pipeline
            </Link>
            <Link
              href="/potential"
              className={`px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-colors shrink-0 ${
                pathname === '/potential'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Potential
            </Link>
            <Link
              href="/retail"
              className={`px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-colors shrink-0 ${
                pathname === '/retail'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Retail
            </Link>
            <Link
              href="/tiktok"
              className={`px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-colors shrink-0 ${
                pathname === '/tiktok'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              TikTok
            </Link>
            <Link
              href="/conexion"
              className={`px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-colors shrink-0 ${
                pathname?.startsWith('/conexion')
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Llamada de conexion
            </Link>
          </nav>
        </div>
        <div className="w-3 h-3 rounded-full bg-melonn-green" />
      </div>
    </header>
  );
}
