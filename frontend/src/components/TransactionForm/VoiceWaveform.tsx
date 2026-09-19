import { useEffect, useRef } from "react";

const BARS = 32;
const IDLE_LEVEL = 0.35;

interface Props {
  // Timestamp (performance.now) dell'ultimo risultato vocale; 0 = ancora nessuno.
  activityRef: React.RefObject<number>;
  // Tempo in cui l'"energia" cala da piena a zero dopo l'ultimo risultato.
  decayMs: number;
}

// Barre "equalizer" con un'ampiezza continua invece di due stati on/off: a ogni risultato
// vocale l'energia torna piena e poi cala linearmente in decayMs; il livello visibile la
// insegue con attacco rapido e rilascio lento. Una pausa breve tra due parole non fa
// crollare le barre, e quando la registrazione si chiude per silenzio sono già a riposo.
// Il livello va nella custom property --level via rAF (nessun re-render React).
export default function VoiceWaveform({ activityRef, decayMs }: Props) {
  const waveRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = waveRef.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.style.setProperty("--level", "0.6");
      return;
    }
    let level = IDLE_LEVEL;
    let raf = 0;
    const tick = () => {
      const last = activityRef.current;
      const energy = last ? Math.max(0, 1 - (performance.now() - last) / decayMs) : 0;
      const target = IDLE_LEVEL + (1 - IDLE_LEVEL) * energy;
      level += (target - level) * (target > level ? 0.3 : 0.1);
      el.style.setProperty("--level", level.toFixed(3));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [activityRef, decayMs]);

  return (
    <div ref={waveRef} className="voice-wave" aria-hidden="true">
      {Array.from({ length: BARS }, (_, i) => (
        <span key={i} className="voice-bar">
          <i
            style={
              {
                animationDuration: `${0.5 + ((i * 7) % 5) * 0.13}s`,
                animationDelay: `${-((i * 37) % 11) * 0.09}s`,
                "--peak": 0.45 + ((i * 13) % 7) * 0.09,
              } as React.CSSProperties
            }
          />
        </span>
      ))}
    </div>
  );
}
