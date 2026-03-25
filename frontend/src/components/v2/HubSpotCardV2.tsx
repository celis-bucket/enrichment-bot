'use client';

import type { FeedbackItem } from '@/lib/types';
import { FeedbackPanel } from '../FeedbackPanel';

interface HubSpotCardV2Props {
  hubspotCompanyId?: string | null;
  hubspotCompanyUrl?: string | null;
  hubspotDealCount?: number | null;
  hubspotDealStage?: string | null;
  hubspotContactExists?: number | null;
  domain?: string;
  feedback?: FeedbackItem[];
}

export function HubSpotCardV2({
  hubspotCompanyId,
  hubspotCompanyUrl,
  hubspotDealCount,
  hubspotDealStage,
  hubspotContactExists,
  domain = '',
  feedback = [],
}: HubSpotCardV2Props) {
  const found = hubspotCompanyId != null;

  const statusLabel = found ? 'En CRM' : 'No encontrada';
  const statusColor = found
    ? 'bg-melonn-green-50 text-melonn-green'
    : 'bg-melonn-surface text-melonn-navy/50';

  return (
    <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading">HubSpot CRM</h3>
        <span className={`text-xs px-3 py-1 rounded-full font-medium ${statusColor}`}>
          {statusLabel}
        </span>
      </div>

      {found ? (
        <div className="space-y-2.5">
          {/* Deal count & stage */}
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
              <span className="text-xs text-melonn-navy/50">Etapa más avanzada</span>
              <span className="text-xs font-medium text-melonn-navy">{hubspotDealStage}</span>
            </div>
          )}

          {hubspotContactExists != null && (
            <div className="flex items-center justify-between py-1.5 border-t border-melonn-purple-50/50">
              <span className="text-xs text-melonn-navy/50">Contacto en CRM</span>
              <span className={`text-xs font-medium ${hubspotContactExists ? 'text-melonn-green' : 'text-melonn-navy/50'}`}>
                {hubspotContactExists ? 'Sí' : 'No'}
              </span>
            </div>
          )}

          {hubspotCompanyUrl && (
            <a
              href={hubspotCompanyUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full text-center text-sm text-melonn-purple hover:text-melonn-purple-light transition-colors py-1"
            >
              Ver en HubSpot
            </a>
          )}
        </div>
      ) : (
        <p className="text-sm text-melonn-navy/40">Esta empresa no está en HubSpot</p>
      )}

      {domain && <FeedbackPanel domain={domain} section="hubspot" existingFeedback={feedback} />}
    </div>
  );
}
