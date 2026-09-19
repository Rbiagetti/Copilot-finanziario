const BARS = 32;

interface Props {
  speaking: boolean;
}

// Barre "equalizer": ferme e basse in attesa, ballano mentre l'utente parla.
// Durata/ritardo per barra sono deterministici (nessun Math.random nel render).
export default function VoiceWaveform({ speaking }: Props) {
  return (
    <div className={`voice-wave${speaking ? " voice-wave--speaking" : ""}`} aria-hidden="true">
      {Array.from({ length: BARS }, (_, i) => (
        <span
          key={i}
          className="voice-bar"
          style={{
            animationDuration: `${0.5 + ((i * 7) % 5) * 0.13}s`,
            animationDelay: `${-((i * 37) % 11) * 0.09}s`,
          }}
        />
      ))}
    </div>
  );
}
