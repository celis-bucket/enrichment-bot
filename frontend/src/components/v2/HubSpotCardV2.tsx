'use client';

import { useState, useEffect } from 'react';
import type { FeedbackItem, HubSpotDetail } from '@/lib/types';
import { getHubSpotDetail } from '@/lib/api';
import { FeedbackPanel } from '../FeedbackPanel';

interface HubSpotCardV2Props {
  hubspotCompanyId?: string | null;
  hubspotCompanyUrl?: string | null;
  hubspotDealCount?: number | null;
  hubspotDealStage?: string | null;
  hubspotContactExists?: number | null;
  hubspotLifecycleLabel?: string | null;
  hubspotLastContacted?: string | null;
  domain?: string;
  feedback?: FeedbackItem[];
}

function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const diff = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  if (days === 0) return 'Hoy';
  if (days === 1) return 'Ayer';
  if (days < 30) return `Hace ${days} días`;
  const months = Math.floor(days / 30);
  if (months < 12) return `Hace ${months} ${months === 1 ? 'mes' : 'meses'}`;
  const years = Math.floor(months / 12);
  return `Hace ${years} ${years === 1 ? 'año' : 'años'}`;
}

function fmtDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('es-CO', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

function fmtAmount(amount: string | null | undefined): string {
  if (!amount) return '—';
  const n = parseFloat(amount);
  if (isNaN(n)) return amount;
  if (n >= 1000) return `$${(n / 1000).toFixed(0)}K`;
  return `$${n.toLocaleString('es-CO')}`;
}

// ===== MODAL =====

function HubSpotModal({ companyId, onClose }: { companyId: string; onClose: () => void }) {
  const [data, setData] = useState<HubSpotDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHubSpotDetail(companyId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [companyId]);

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />
      <div className="fixed top-0 right-0 h-full w-[480px] max-w-full bg-white shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            <h3 className="font-bold text-melonn-navy font-heading">
              {data?.company_name || 'HubSpot'}
            </h3>
            <p className="text-xs text-gray-400">Historial en HubSpot CRM</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">
            ×
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <p className="text-sm text-gray-400 text-center py-12">Cargando historial...</p>
          ) : error ? (
            <p className="text-sm text-red-400 text-center py-12">{error}</p>
          ) : data ? (
            <>
              {/* Resumen */}
              <Section title="Resumen">
                <Row label="Etapa de vida" value={
                  data.lifecycle_label ? (
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      data.lifecycle_stage === 'customer'
                        ? 'bg-melonn-green-50 text-melonn-green'
                        : 'bg-melonn-purple-50 text-melonn-purple'
                    }`}>{data.lifecycle_label}</span>
                  ) : undefined
                } />
                {data.lifecycle_stage === 'customer' && (
                  <Row label="" value={
                    <span className="text-xs font-medium text-melonn-green">Ya es cliente de Melonn</span>
                  } />
                )}
                <Row label="Estado del lead" value={data.lead_status} />
                <Row label="Creada en HubSpot" value={fmtDate(data.created_at)} />
                <Row label="Propietario" value={data.owner_name} />
                {data.owner_email && (
                  <Row label="Email propietario" value={data.owner_email} />
                )}
              </Section>

              {/* Actividad */}
              <Section title="Actividad">
                <Row label="Último contacto" value={
                  data.last_contacted ? (
                    <span>
                      <span className="font-medium text-melonn-navy">{timeAgo(data.last_contacted)}</span>
                      <span className="text-gray-400 ml-1">({fmtDate(data.last_contacted)})</span>
                    </span>
                  ) : undefined
                } />
                <Row label="Última actividad" value={
                  data.last_activity ? (
                    <span>
                      <span className="font-medium text-melonn-navy">{timeAgo(data.last_activity)}</span>
                      <span className="text-gray-400 ml-1">({fmtDate(data.last_activity)})</span>
                    </span>
                  ) : undefined
                } />
                <Row label="Total actividades" value={data.total_activities > 0 ? String(data.total_activities) : undefined} />
                <Row label="Actividades de contacto" value={data.contact_activities > 0 ? String(data.contact_activities) : undefined} />
              </Section>

              {/* Negocios */}
              <Section title={`Negocios (${data.deal_count})`}>
                {data.deals.length === 0 ? (
                  <p className="text-xs text-gray-400 py-1">Sin negocios asociados</p>
                ) : (
                  data.deals.map((deal) => (
                    <div key={deal.id} className="py-2 border-b border-gray-100 last:border-0">
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-xs font-medium text-melonn-navy">{deal.name}</p>
                          <p className="text-xs text-gray-400">{deal.pipeline}</p>
                        </div>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          deal.stage.includes('ganado') || deal.stage.includes('Activo')
                            ? 'bg-melonn-green-50 text-melonn-green'
                            : deal.stage.includes('erdido') || deal.stage.includes('rechazad')
                            ? 'bg-red-50 text-red-500'
                            : 'bg-melonn-orange-50 text-melonn-orange'
                        }`}>{deal.stage}</span>
                      </div>
                      <div className="flex gap-4 mt-1">
                        <span className="text-xs text-gray-400">Monto: <span className="text-melonn-navy">{fmtAmount(deal.amount)}</span></span>
                        <span className="text-xs text-gray-400">Cierre: <span className="text-melonn-navy">{fmtDate(deal.closedate)}</span></span>
                      </div>
                    </div>
                  ))
                )}
              </Section>

              {/* Contactos */}
              <Section title={`Contactos en HubSpot (${data.associated_contacts_count})`}>
                {data.contacts.length === 0 ? (
                  <p className="text-xs text-gray-400 py-1">Sin contactos asociados</p>
                ) : (
                  data.contacts.map((c, i) => (
                    <div key={i} className="py-1.5 border-b border-gray-100 last:border-0">
                      <p className="text-xs font-medium text-melonn-navy">{c.name || '—'}</p>
                      {c.title && <p className="text-xs text-gray-400">{c.title}</p>}
                      {c.email && <p className="text-xs text-gray-500">{c.email}</p>}
                    </div>
                  ))
                )}
                {data.associated_contacts_count > data.contacts.length && (
                  <p className="text-xs text-gray-400 pt-1">
                    +{data.associated_contacts_count - data.contacts.length} más en HubSpot
                  </p>
                )}
              </Section>

              {/* Link */}
              {data.hubspot_url && (
                <a
                  href={data.hubspot_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block w-full text-center text-sm text-white bg-melonn-purple hover:bg-melonn-purple/90
                             rounded-lg py-2.5 mt-4 font-medium transition-colors"
                >
                  Abrir en HubSpot
                </a>
              )}
            </>
          ) : null}
        </div>
      </div>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-melonn-purple mb-1">{title}</h4>
      <div className="bg-gray-50 rounded-lg px-3 py-1">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  if (value == null || value === '' || value === '—') return null;
  return (
    <div className="flex justify-between items-start py-1.5 border-b border-gray-50 last:border-0">
      <span className="text-xs text-gray-400 shrink-0 w-44">{label}</span>
      <span className="text-xs text-melonn-navy text-right break-all">{value}</span>
    </div>
  );
}

// ===== CARD =====

export function HubSpotCardV2({
  hubspotCompanyId,
  hubspotCompanyUrl,
  hubspotDealCount,
  hubspotDealStage,
  hubspotContactExists,
  hubspotLifecycleLabel,
  hubspotLastContacted,
  domain = '',
  feedback = [],
}: HubSpotCardV2Props) {
  const [showModal, setShowModal] = useState(false);
  const found = hubspotCompanyId != null;

  const isCustomer = hubspotLifecycleLabel === 'Cliente';

  const statusLabel = isCustomer ? 'Cliente' : found ? (hubspotLifecycleLabel || 'En CRM') : 'No encontrada';
  const statusColor = isCustomer
    ? 'bg-melonn-green-50 text-melonn-green'
    : found
    ? 'bg-melonn-purple-50 text-melonn-purple'
    : 'bg-melonn-surface text-melonn-navy/50';

  return (
    <>
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-melonn-navy font-heading">HubSpot CRM</h3>
          <span className={`text-xs px-3 py-1 rounded-full font-medium ${statusColor}`}>
            {statusLabel}
          </span>
        </div>

        {found ? (
          <div className="space-y-2.5">
            {isCustomer && (
              <div className="bg-melonn-green-50 rounded-lg px-3 py-2 text-center">
                <p className="text-xs font-medium text-melonn-green">Ya es cliente de Melonn</p>
              </div>
            )}

            <div className="text-center">
              <span className="text-3xl font-bold text-melonn-navy font-heading">
                {hubspotDealCount ?? 0}
              </span>
              <p className="text-xs text-melonn-navy/50 mt-1">
                {hubspotDealCount === 1 ? 'Negocio asociado' : 'Negocios asociados'}
              </p>
            </div>

            {hubspotDealStage && (
              <div className="flex items-center justify-between py-1.5 border-t border-melonn-purple-50/50">
                <span className="text-xs text-melonn-navy/50">Etapa</span>
                <span className="text-xs font-medium text-melonn-navy">{hubspotDealStage}</span>
              </div>
            )}

            {hubspotLastContacted && (
              <div className="flex items-center justify-between py-1.5 border-t border-melonn-purple-50/50">
                <span className="text-xs text-melonn-navy/50">Último contacto</span>
                <span className="text-xs font-medium text-melonn-navy">{timeAgo(hubspotLastContacted)}</span>
              </div>
            )}

            <button
              onClick={() => setShowModal(true)}
              className="w-full text-center text-sm text-melonn-purple hover:text-melonn-purple-light
                         transition-colors py-1.5 border border-melonn-purple/20 rounded-lg
                         hover:bg-melonn-purple-50/30 font-medium"
            >
              Ver historial completo
            </button>
          </div>
        ) : (
          <p className="text-sm text-melonn-navy/40">Esta empresa no está en HubSpot</p>
        )}

        {domain && <FeedbackPanel domain={domain} section="hubspot" existingFeedback={feedback} />}
      </div>

      {showModal && hubspotCompanyId && (
        <HubSpotModal companyId={hubspotCompanyId} onClose={() => setShowModal(false)} />
      )}
    </>
  );
}
