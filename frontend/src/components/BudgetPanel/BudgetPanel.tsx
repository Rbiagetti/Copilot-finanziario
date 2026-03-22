import { useEffect, useState } from "react";
import { getBudgetStatus, createBudget, deleteBudget, updateBudget } from "../../api/client";
import type { BudgetStatus } from "../../api/client";
import { PlusCircle, AlertTriangle, CheckCircle, XCircle, Trash2, Pencil } from "lucide-react";
import toast from "react-hot-toast";

const CATEGORIES = [
  { value: "cibo", emoji: "\u{1F355}", label: "Cibo" },
  { value: "trasporti", emoji: "\u{1F697}", label: "Trasporti" },
  { value: "casa", emoji: "\u{1F3E0}", label: "Casa" },
  { value: "salute", emoji: "\u{1F48A}", label: "Salute" },
  { value: "svago", emoji: "\u{1F3AD}", label: "Svago" },
  { value: "abbigliamento", emoji: "\u{1F455}", label: "Abbigliamento" },
  { value: "lavoro", emoji: "\u{1F4BC}", label: "Lavoro" },
  { value: "abbonamenti", emoji: "\u{1F4F1}", label: "Abbonamenti" },
  { value: "formazione", emoji: "\u{1F393}", label: "Formazione" },
  { value: "altro", emoji: "\u2753", label: "Altro" },
];

const getEmoji = (cat: string) => CATEGORIES.find((c) => c.value === cat)?.emoji || "\u2753";

interface BudgetStatusWithId extends BudgetStatus {
  id?: number;
}

export default function BudgetPanel() {
  const [budgets, setBudgets] = useState<BudgetStatusWithId[]>([]);
  const [loading, setLoading] = useState(true);
  const [newCat, setNewCat] = useState("cibo");
  const [newAmount, setNewAmount] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editAmount, setEditAmount] = useState("");

  const load = () => {
    setLoading(true);
    getBudgetStatus()
      .then((res) => setBudgets(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const amount = parseFloat(newAmount);
    if (!amount || amount < 10) {
      toast.error("Inserisci un budget di almeno \u20AC10");
      return;
    }
    try {
      await createBudget({ category: newCat, amount });
      toast.success(`Budget ${newCat}: \u20AC${amount}`);
      setNewAmount("");
      load();
    } catch {
      toast.error("Errore nel salvataggio");
    }
  };

  const handleDelete = async (b: BudgetStatusWithId) => {
    if (!confirm(`Eliminare il budget per ${b.category}?`)) return;
    try {
      await deleteBudget(b.id!);
      toast.success(`Budget ${b.category} eliminato`);
      load();
    } catch {
      toast.error("Errore nell'eliminazione");
    }
  };

  const statusIcon = (s: string) => {
    if (s === "over") return <XCircle size={18} className="text-red" />;
    if (s === "warning") return <AlertTriangle size={18} className="text-yellow" />;
    return <CheckCircle size={18} className="text-green" />;
  };

  return (
    <div className="budget-page">
      <h2>Budget mensili</h2>

      <form className="budget-form" onSubmit={handleAdd}>
        <select value={newCat} onChange={(e) => setNewCat(e.target.value)}>
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>{c.emoji} {c.label}</option>
          ))}
        </select>
        <input
          type="number"
          step="5"
          min="10"
          placeholder="es. 200"
          value={newAmount}
          onChange={(e) => setNewAmount(e.target.value)}
          required
        />
        <button type="submit" className="btn-primary">
          <PlusCircle size={16} /> Aggiungi
        </button>
      </form>

      {loading ? (
        <div className="loading">Caricamento...</div>
      ) : budgets.length === 0 ? (
        <div className="empty-budget">
          <p>Nessun budget impostato</p>
          <p className="empty-hint">Imposta un budget per ogni categoria per tenere sotto controllo le spese</p>
        </div>
      ) : (
        <div className="budget-list">
          {budgets.map((b) => (
            <div key={b.category} className={`budget-card ${b.status}`}>
              <div className="budget-header">
                {statusIcon(b.status)}
                <span className="budget-emoji">{getEmoji(b.category)}</span>
                <span className="budget-cat capitalize">{b.category}</span>
                <span className="budget-pct">{b.percentage}%</span>
                <button
                  type="button"
                  className="btn-icon danger"
                  onClick={() => handleDelete(b)}
                  title="Elimina budget"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <div className="budget-bar">
                <div
                  className="budget-fill"
                  style={{ width: `${Math.min(b.percentage, 100)}%` }}
                />
              </div>
              <div className="budget-details">
                <span>&euro;{b.spent.toFixed(2)} / &euro;{b.budget.toFixed(2)}</span>
                <span>
                  {b.remaining >= 0
                    ? `\u20AC${b.remaining.toFixed(2)} rimasti`
                    : `\u20AC${Math.abs(b.remaining).toFixed(2)} sforato`}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
