'use client';

interface TeamSelectorProps {
  members: string[];
  value: string;
  onChange: (owner: string) => void;
}

export function TeamSelector({ members, value, onChange }: TeamSelectorProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="px-4 py-2 rounded-lg border border-gray-200 bg-white text-sm font-medium
                 text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-melonn-purple
                 focus:border-melonn-purple min-w-[220px]"
    >
      <option value="">Selecciona tu nombre</option>
      {members.map((m) => (
        <option key={m} value={m}>{m}</option>
      ))}
    </select>
  );
}
