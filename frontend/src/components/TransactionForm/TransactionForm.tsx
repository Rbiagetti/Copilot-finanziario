import { useState } from "react";
import { createTransaction } from "../../api/client";
import { PlusCircle } from "lucide-react";
import toast from "react-hot-toast";

const CATEGORIES = [
  { value: "cibo", emoji: "🍕", label: "Cibo" },
  { value: "trasporti", emoji: "🚗", label: "Trasporti" },
  { value: "casa", emoji: "🏠", label: "Casa" },
  { value: "salute", emoji: "💊", label: "Salute" },
  { value: "svago", emoji: "🎭", label: "Svago" },
  { value: "abbigliamento", emoji: "👕", label: "Abbigliamento" },
  { value: "lavoro", emoji: "💼", label: "Lavoro" },
  { value: "abbonamenti", emoji: "📱", label: "Abbonamenti" },
  { value: "formazione", emoji: "🎓", label: "Formazione" },
  { value: "altro", emoji: "❓", label: "Altro" },
];

interface Props {
  onAdded?: () => void;
}

export default function TransactionForm({ onAdded }: Props) {
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("cibo");
  const [description, setDescription] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const numAmount = parseFloat(amount);
    if (!numAmount || numAmount <= 0) {
      toast.error("Inserisci un importo valido");
      return;
    }

    setSubmitting(true);
    try {
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

  return (
    <form className="transaction-form" onSubmit={handleSubmit}>
      <h3>Nuova spesa</h3>

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
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
      </div>

      <div className="form-group">
        <label>Categoria</label>
        <div className="category-grid">
          {CATEGORIES.map((c) => (
            <button
              key={c.value}
              type="button"
              className={`cat-btn ${category === c.value ? "active" : ""}`}
              onClick={() => setCategory(c.value)}
            >
              <span>{c.emoji}</span>
              <span>{c.label}</span>
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
  );
}
