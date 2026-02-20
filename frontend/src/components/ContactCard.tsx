'use client';

interface ContactCardProps {
  contactName?: string | null;
  contactEmail?: string | null;
  companyLinkedin?: string | null;
  numberEmployes?: number | null;
}

export function ContactCard({ contactName, contactEmail, companyLinkedin, numberEmployes }: ContactCardProps) {
  const hasData = contactName || contactEmail || companyLinkedin || numberEmployes;

  if (!hasData) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Contact & Company</h3>
        <p className="text-sm text-gray-400">No contact data available</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Contact & Company</h3>
      <div className="space-y-2">
        {contactName && (
          <div className="flex items-center gap-2">
            <span className="text-gray-400 text-sm w-20">Contact</span>
            <span className="text-sm font-medium text-gray-900">{contactName}</span>
          </div>
        )}
        {contactEmail && (
          <div className="flex items-center gap-2">
            <span className="text-gray-400 text-sm w-20">Email</span>
            <a href={`mailto:${contactEmail}`} className="text-sm text-blue-600 hover:underline">
              {contactEmail}
            </a>
          </div>
        )}
        {companyLinkedin && (
          <div className="flex items-center gap-2">
            <span className="text-gray-400 text-sm w-20">LinkedIn</span>
            <a href={companyLinkedin} target="_blank" rel="noopener noreferrer"
               className="text-sm text-blue-600 hover:underline truncate">
              {companyLinkedin.replace('https://www.linkedin.com/company/', '').replace(/\/$/, '')}
            </a>
          </div>
        )}
        {numberEmployes != null && (
          <div className="flex items-center gap-2">
            <span className="text-gray-400 text-sm w-20">Employees</span>
            <span className="text-sm font-medium text-gray-900">{numberEmployes.toLocaleString()}</span>
          </div>
        )}
      </div>
    </div>
  );
}
