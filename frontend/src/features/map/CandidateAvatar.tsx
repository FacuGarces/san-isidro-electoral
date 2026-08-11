import type { Candidato } from "../../lib/api";
import { resolveFotoUrl } from "../../lib/format";

function initials(nombre: string): string {
  return nombre
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

interface Props {
  candidato: Candidato | null | undefined;
  size?: number;
  ringColor?: string;
}

export function CandidateAvatar({ candidato, size = 40, ringColor }: Props) {
  if (!candidato) return null;
  const style = { width: size, height: size, minWidth: size, borderColor: ringColor ?? "var(--color-line-strong)" };
  if (candidato.foto) {
    return (
      <img
        src={resolveFotoUrl(candidato.foto)}
        alt={candidato.nombre}
        title={candidato.nombre}
        style={style}
        className="rounded-full border-2 object-cover"
      />
    );
  }
  return (
    <div
      style={{ ...style, fontSize: size * 0.34 }}
      title={candidato.nombre}
      className="flex items-center justify-center rounded-full border-2 bg-surface-2 font-bold text-ink-muted"
    >
      {initials(candidato.nombre)}
    </div>
  );
}
