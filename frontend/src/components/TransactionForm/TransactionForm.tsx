import { useState, useEffect, useRef } from "react";
import { createTransaction, parseNatural } from "../../api/client";
import { PlusCircle, Mic, MicOff, MessageSquare, Keyboard } from "lucide-react";
import toast from "react-hot-toast";
import { useAppStore } from "../../store/appStore";
import { voiceService } from "../../utils/voiceService";
import { CategoryIcon } from "../../lib/categoryIcons";
import VoiceWaveform from "./VoiceWaveform";

// Silenzio dopo l'ultimo risultato vocale prima di chiudere la registrazione, e attesa
// (con barra che si ritira) prima del salvataggio automatico se l'utente non tocca nulla.
const VOICE_SILENCE_MS = 1200;
const VOICE_SPEAKING_HOLD_MS = 600;
const AUTOSAVE_MS = 2000;

interface Props {
  onAdded?: () => void;
}

export default function TransactionForm({ onAdded }: Props) {
  const [mode, setMode] = useState<"manual" | "smart">("smart");
  // Manual mode
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("cibo");
  const [description, setDescription] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  // Smart mode (NL + voice)
  const [nlText, setNlText] = useState("");
  const [recording, setRecording] = useState(false);
  // Testo confermato (isFinal) accumulato tra sessioni di riconoscimento.
  // Necessario perché ogni auto-restart del service reinizia i result da 0.
  const confirmedTextRef = useRef("");
  const [submitting, setSubmitting] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [autosaveLeft, setAutosaveLeft] = useState<number | null>(null);
  const nlTextRef = useRef("");
  const submitRef = useRef<() => void>(() => {});
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const speakingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autosaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autosaveTickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => { nlTextRef.current = nlText; }, [nlText]);

  const { autoStartVoice, setAutoStartVoice, markTransactionsAsNew, categories, loadCategories } = useAppStore();

  useEffect(() => { loadCategories(); }, [loadCategories]);

  useEffect(() => {
    if (autoStartVoice) {
      setMode("smart");
      setAutoStartVoice(false);
      // Piccolo debounce per permettere il mount della view corretta
      setTimeout(() => {
        if (!recording) toggleVoice();
      }, 100);
    }
  }, [autoStartVoice]);

  // CLEANUP PRIVACY: Assicura che il mic si spenga se l'utente cambia pagina o chiude il componente
  useEffect(() => {
    return () => {
      voiceService.stop();
      clearVoiceTimers();
      cancelAutosave();
    };
  }, []);

  const clearVoiceTimers = () => {
    if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null; }
    if (speakingTimerRef.current) { clearTimeout(speakingTimerRef.current); speakingTimerRef.current = null; }
    setSpeaking(false);
  };

  const cancelAutosave = () => {
    if (autosaveTimerRef.current) { clearTimeout(autosaveTimerRef.current); autosaveTimerRef.current = null; }
    if (autosaveTickRef.current) { clearInterval(autosaveTickRef.current); autosaveTickRef.current = null; }
    setAutosaveLeft(null);
  };

  // Dopo la dettatura: countdown con barra che si ritira, poi come premere "Salva".
  // Qualsiasi interazione col campo (digitare, toccarlo, Annulla, riavviare il mic) lo cancella.
  const armAutosave = () => {
    cancelAutosave();
    const deadline = Date.now() + AUTOSAVE_MS;
    setAutosaveLeft(AUTOSAVE_MS);
    autosaveTickRef.current = setInterval(() => {
      setAutosaveLeft(Math.max(0, deadline - Date.now()));
    }, 100);
    autosaveTimerRef.current = setTimeout(() => {
      cancelAutosave();
      submitRef.current();
    }, AUTOSAVE_MS);
  };

  // Silenzio rilevato: chiude il microfono e, se c'è testo, avvia il countdown di salvataggio.
  const finishDictation = () => {
    clearVoiceTimers();
    voiceService.stop();
    setRecording(false);
    if (nlTextRef.current.trim()) armAutosave();
  };

  const handleVoiceActivity = () => {
    setSpeaking(true);
    if (speakingTimerRef.current) clearTimeout(speakingTimerRef.current);
    speakingTimerRef.current = setTimeout(() => setSpeaking(false), VOICE_SPEAKING_HOLD_MS);
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = setTimeout(finishDictation, VOICE_SILENCE_MS);
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const numAmount = parseFloat(amount);
    if (!numAmount || numAmount <= 0) {
      toast.error("Inserisci un importo valido");
      return;
    }
    // M-5: blocca date future
    if (date > new Date().toISOString().slice(0, 10)) {
      toast.error("La data non può essere nel futuro");
      return;
    }
    setSubmitting(true);
    try {
      markTransactionsAsNew();
      await createTransaction({
        amount: numAmount,
        category,
        description: description || undefined,
        date,
      });
      toast.success(`€${numAmount.toFixed(2)} salvato in ${category}`);
      setAmount("");
      setDescription("");
      onAdded?.();
    } catch {
      toast.error("Errore nel salvataggio");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSmartSubmit = async () => {
    cancelAutosave();
    clearVoiceTimers();
    if (!nlText.trim()) return;
    if (voiceService.isListening()) {
      voiceService.stop();
    }
    setSubmitting(true);
    try {
      const res = await parseNatural(nlText.trim());
      const tx = res.data;
      // A-6: valida importo post-parse — il backend può restituire 0 su testo ambiguo
      if (!tx.amount || tx.amount <= 0) {
        toast.error("Importo non trovato. Prova a essere più specifico (es. 'caffè 1.50')");
        return;
      }
      markTransactionsAsNew();
      toast.success(`€${tx.amount.toFixed(2)} salvato in ${tx.category} — "${tx.description}"`);
      setNlText("");
      onAdded?.();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Non riesco a capire, riprova";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => { submitRef.current = handleSmartSubmit; });

  useEffect(() => {
    if (mode !== "smart") {
      cancelAutosave();
      clearVoiceTimers();
    }
  }, [mode]);

  const toggleVoice = () => {
    cancelAutosave();
    if (voiceService.isListening()) {
      clearVoiceTimers();
      voiceService.stop();
      setRecording(false);
      return;
    }

    // Inizia ad accumulare dal testo già presente nel campo
    confirmedTextRef.current = nlText.trimEnd() ? nlText.trimEnd() + " " : "";

    voiceService.start({
      onResult: (transcript, isFinal) => {
        handleVoiceActivity();
        // Mostra: testo confermato precedente + transcript corrente (interim o final)
        setNlText(confirmedTextRef.current + transcript);
        if (isFinal) {
          // Aggiungi al confermato così l'auto-restart non perde nulla
          confirmedTextRef.current += transcript + " ";
        }
      },
      onError: (err) => {
        clearVoiceTimers();
        setRecording(false);
        toast.error(`Errore vocale: ${err}`);
      },
      onEnd: () => {
        clearVoiceTimers();
        setRecording(false);
        confirmedTextRef.current = ""; // reset per la prossima sessione vocale
      }
    });

    setRecording(true);
  };

  return (
    <div className="transaction-form">
      <div className="form-tabs">
        <button
          type="button"
          className={`form-tab ${mode === "smart" ? "active" : ""}`}
          onClick={() => setMode("smart")}
        >
          <MessageSquare size={16} /> Voce / Testo
        </button>
        <button
          type="button"
          className={`form-tab ${mode === "manual" ? "active" : ""}`}
          onClick={() => setMode("manual")}
        >
          <Keyboard size={16} /> Manuale
        </button>
      </div>

      {mode === "smart" ? (
        <div className="smart-input">
          <p className="smart-hint">
            Scrivi o detta la spesa in linguaggio naturale, es: "caffè 3 euro" o "benzina 50€"
          </p>
          <div className="smart-row">
            <input
              type="text"
              value={nlText}
              onChange={(e) => { cancelAutosave(); setNlText(e.target.value); }}
              onFocus={cancelAutosave}
              onKeyDown={(e) => e.key === "Enter" && handleSmartSubmit()}
              placeholder="es. pranzo 12 euro al bar"
              disabled={submitting}
            />
            <button
              type="button"
              className={`btn-voice ${recording ? "recording" : ""}`}
              onClick={toggleVoice}
              title={recording ? "Stop" : "Parla"}
            >
              {recording ? <MicOff size={20} /> : <Mic size={20} />}
            </button>
            <button
              type="button"
              className="btn-primary btn-smart-send"
              onClick={handleSmartSubmit}
              disabled={submitting || !nlText.trim()}
            >
              <PlusCircle size={18} />
              {submitting ? "..." : "Salva"}
            </button>
          </div>

          {recording && (
            <div className="voice-panel fade-in">
              <span className="voice-panel-label">
                <span className="glyph-dot glyph-dot-red" />
                {speaking ? "Ascolto" : "In attesa"}
              </span>
              <VoiceWaveform speaking={speaking} />
            </div>
          )}

          {autosaveLeft !== null && (
            <div className="voice-panel voice-panel--autosave fade-in">
              <div className="autosave-track">
                <div
                  className="autosave-fill"
                  style={{ width: `${(autosaveLeft / AUTOSAVE_MS) * 100}%` }}
                />
              </div>
              <span className="voice-panel-label">
                Salvo tra {Math.ceil(autosaveLeft / 1000)}s
              </span>
              <button type="button" className="autosave-cancel" onClick={cancelAutosave}>
                Annulla
              </button>
            </div>
          )}
        </div>
      ) : (
        <form onSubmit={handleManualSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label>Importo (&euro;)</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                required
              />
            </div>
            <div className="form-group">
              <label>Data</label>
              <input
                type="date"
                value={date}
                max={new Date().toISOString().slice(0, 10)}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label>Categoria</label>
            <div className="category-grid">
              {categories.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`cat-btn ${category === c ? "active" : ""}`}
                  onClick={() => setCategory(c)}
                >
                  <CategoryIcon category={c} size={16} />
                  <span className="capitalize">{c}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label>Nota (opzionale)</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="es. cena con amici"
            />
          </div>

          <button type="submit" className="btn-primary" disabled={submitting}>
            <PlusCircle size={18} />
            {submitting ? "Salvataggio..." : "Aggiungi spesa"}
          </button>
        </form>
      )}
    </div>
  );
}
