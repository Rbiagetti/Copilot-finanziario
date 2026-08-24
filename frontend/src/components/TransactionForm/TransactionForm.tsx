import { useState, useEffect, useRef } from "react";
import { createTransaction, parseNatural } from "../../api/client";
import { PlusCircle, Mic, MicOff, MessageSquare, Keyboard } from "lucide-react";
import toast from "react-hot-toast";
import { useAppStore } from "../../store/appStore";
import { voiceService } from "../../utils/voiceService";
import { CategoryIcon } from "../../lib/categoryIcons";

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
    };
  }, []);

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

  const toggleVoice = () => {
    if (voiceService.isListening()) {
      voiceService.stop();
      setRecording(false);
      return;
    }

    // Inizia ad accumulare dal testo già presente nel campo
    confirmedTextRef.current = nlText.trimEnd() ? nlText.trimEnd() + " " : "";

    voiceService.start({
      onResult: (transcript, isFinal) => {
        // Mostra: testo confermato precedente + transcript corrente (interim o final)
        setNlText(confirmedTextRef.current + transcript);
        if (isFinal) {
          // Aggiungi al confermato così l'auto-restart non perde nulla
          confirmedTextRef.current += transcript + " ";
        }
      },
      onError: (err) => {
        setRecording(false);
        toast.error(`Errore vocale: ${err}`);
      },
      onEnd: () => {
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
              onChange={(e) => setNlText(e.target.value)}
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
                  <CategoryIcon category={c} size={19} />
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
