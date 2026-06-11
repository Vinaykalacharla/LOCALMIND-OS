interface StatCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  tone?: "default" | "brand" | "gold";
}

export default function StatCard({ label, value, subtext, tone = "default" }: StatCardProps) {
  return (
    <div className={`glow-card p-6 ${tone === 'brand' ? 'border-[var(--accent-dim)]' : tone === 'gold' ? 'border-[var(--warning-dim)]' : ''}`}>
      <div className="flex items-center gap-3">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${tone === 'brand' ? 'bg-[var(--accent-dim)] text-[var(--accent-bright)]' : tone === 'gold' ? 'bg-[var(--warning-dim)] text-[var(--warning)]' : 'bg-[var(--panel-soft)] text-[var(--text-muted)]'}`}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
          </svg>
        </div>
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
            {label}
          </div>
          <div className="mt-1 font-display text-2xl font-bold text-[var(--text-main)] tracking-tight">
            {value}
          </div>
        </div>
      </div>
      {subtext && (
        <div className="mt-4 border-t border-[var(--line)] pt-3 text-xs font-medium text-[var(--text-muted)]">
          {subtext}
        </div>
      )}
    </div>
  );
}
