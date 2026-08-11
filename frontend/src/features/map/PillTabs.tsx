interface Option<T extends string> {
  value: T;
  label: string;
  disabled?: boolean;
  title?: string;
}

interface Props<T extends string> {
  label: string;
  options: Option<T>[];
  value: T;
  onChange: (v: T) => void;
}

export function PillTabs<T extends string>({ label, options, value, onChange }: Props<T>) {
  return (
    <div>
      <div className="mb-1.5 text-[11px] font-semibold tracking-wide text-ink-faint uppercase">{label}</div>
      <div className="inline-flex gap-0.5 rounded-2xl border border-line bg-surface-2/60 p-1">
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            disabled={opt.disabled}
            title={opt.title}
            onClick={() => onChange(opt.value)}
            aria-pressed={value === opt.value}
            className={
              "cursor-pointer rounded-xl px-3.5 py-2 text-[13px] font-semibold transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-40 " +
              (value === opt.value
                ? "bg-brand text-white shadow-elevation-sm"
                : "text-ink-muted hover:bg-surface hover:text-ink hover:shadow-elevation-xs")
            }
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
