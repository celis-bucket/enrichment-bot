'use client';

import type { ApolloContact } from '@/lib/types';

interface ContactCardProps {
  contacts?: ApolloContact[];
  contactName?: string | null;
  contactEmail?: string | null;
  companyLinkedin?: string | null;
  numberEmployes?: number | null;
}

export function ContactCard({ contacts, contactName, contactEmail, companyLinkedin, numberEmployes }: ContactCardProps) {
  const hasContacts = contacts && contacts.length > 0;
  const hasFallback = contactName || contactEmail;
  const hasCompanyInfo = companyLinkedin || numberEmployes;

  if (!hasContacts && !hasFallback && !hasCompanyInfo) {
    return (
      <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-2">Contact & Company</h3>
        <p className="text-sm text-melonn-navy/40">No contact data available</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-melonn-navy font-heading mb-3">Contact & Company</h3>

      {/* Company info */}
      <div className="space-y-2 mb-3">
        {companyLinkedin && (
          <div className="flex items-center gap-2">
            <span className="text-melonn-navy/50 text-sm w-20 shrink-0">LinkedIn</span>
            <a href={companyLinkedin} target="_blank" rel="noopener noreferrer"
               className="text-sm text-melonn-purple hover:text-melonn-purple-light transition-colors truncate">
              {companyLinkedin.replace('https://www.linkedin.com/company/', '').replace(/\/$/, '')}
            </a>
          </div>
        )}
        {numberEmployes != null && (
          <div className="flex items-center gap-2">
            <span className="text-melonn-navy/50 text-sm w-20 shrink-0">Employees</span>
            <span className="text-sm font-medium text-melonn-navy">{numberEmployes.toLocaleString()}</span>
          </div>
        )}
      </div>

      {/* Contact list */}
      {hasContacts ? (
        <div className="space-y-3">
          {contacts.map((c, i) => (
            <div key={i} className="border-t border-melonn-purple-50/60 pt-2 first:border-t-0 first:pt-0">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-medium text-melonn-navy">{c.name}</span>
                {c.title && (
                  <span className="text-xs text-melonn-navy/40">{c.title}</span>
                )}
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1">
                {c.email && (
                  <a href={`mailto:${c.email}`} className="text-xs text-melonn-purple hover:text-melonn-purple-light transition-colors">
                    {c.email}
                  </a>
                )}
                {c.phone && (
                  <span className="text-xs text-melonn-navy/60">{c.phone}</span>
                )}
                {c.linkedin_url && (
                  <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer"
                     className="text-xs text-melonn-purple hover:text-melonn-purple-light transition-colors">
                    LinkedIn
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : hasFallback && (
        <div className="border-t border-melonn-purple-50/60 pt-2">
          {contactName && (
            <span className="text-sm font-medium text-melonn-navy">{contactName}</span>
          )}
          {contactEmail && (
            <a href={`mailto:${contactEmail}`} className="text-xs text-melonn-purple hover:text-melonn-purple-light transition-colors ml-2">
              {contactEmail}
            </a>
          )}
        </div>
      )}
    </div>
  );
}
