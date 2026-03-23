interface StatCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  tone?: "default" | "brand" | "gold";
}

function toneClasses(tone: StatCardProps["tone"]): string {
  if (tone === "brand") {
    return "border-sky-300/15 bg-sky-300/5";
  }

  if (tone === "gold") {
    return "border-amber-300/15 bg-amber-300/5";
  }

  return "border-white/8 bg-white/[0.025]";
}

export default function StatCard({ label, value, subtext, tone = "default" }: StatCardProps) {
  return (
    <div className={`rounded-[20px] border p-5 shadow-panel backdrop-blur-xl ${toneClasses(tone)}`}>
      <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-zinc-400">{label}</div>
      <div className="mt-4 font-display text-3xl font-semibold text-white">{value}</div>
      {subtext ? <div className="mt-2 max-w-xs text-sm leading-6 text-zinc-400">{subtext}</div> : null}
    </div>
  );
}
