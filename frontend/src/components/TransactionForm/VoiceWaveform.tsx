const BARS = 32;

interface Props {
  speaking: boolean;
}

// Barre "equalizer". Il ballo (elemento interno) gira sempre; l'ampiezza (barra esterna)
// sale in fretta quando si parla e scende piano quando si smette, così non si blocca di
// colpo. Durata/ritardo/picco per barra sono deterministici (nessun Math.random nel render).
export default function VoiceWaveform({ speaking }: Props) {
  return (
    <div className={`voice-wave${speaking ? " voice-wave--speaking" : ""}`} aria-hidden="true">
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
