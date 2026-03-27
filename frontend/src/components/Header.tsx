'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function Header() {
  const pathname = usePathname();

  return (
    <header className="bg-melonn-navy">
      <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <div>
            <h1 className="text-xl font-bold text-white font-heading tracking-tight">
              Enrichment Agent
            </h1>
            <p className="text-xs text-melonn-purple-light">
              E-commerce lead intelligence
            </p>
          </div>
          <nav className="flex gap-1">
            <Link
              href="/analyze-v2"
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                pathname === '/analyze-v2' || pathname === '/'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Analizar
            </Link>
            <Link
              href="/history"
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                pathname === '/history'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              History
            </Link>
            <Link
              href="/leads"
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                pathname === '/leads'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Leads
            </Link>
            <Link
              href="/potential"
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                pathname === '/potential'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Potential
            </Link>
            <Link
              href="/retail"
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                pathname === '/retail'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              Retail
            </Link>
            <Link
              href="/tiktok"
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                pathname === '/tiktok'
                  ? 'bg-melonn-purple text-white'
                  : 'text-melonn-purple-light hover:text-white hover:bg-melonn-navy-light'
              }`}
            >
              TikTok
            </Link>
          </nav>
        </div>
        <div className="w-3 h-3 rounded-full bg-melonn-green" />
      </div>
    </header>
  );
}
