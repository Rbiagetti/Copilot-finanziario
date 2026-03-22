import { useEffect, useState } from "react";
import { getBudgetStatus, createBudget, BudgetStatus } from "../../api/client";
import { PlusCircle, AlertTriangle, CheckCircle, XCircle } from "lucide-react";
import toast from "react-hot-toast";

const CATEGORIES = [
  "cibo", "trasporti", "casa", "salute", "svago",
  "abbigliamento", "lavoro", "abbonamenti", "formazione", "altro",
];

export default function BudgetPanel() {
  const [budgets, setBudgets] = useState<BudgetStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [newCat, setNewCat] = useState("cibo");
  const [newAmount, setNewAmount] = useState("");

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
    if (!amount || amount <= 0) return;
    try {
      await createBudget({ category: newCat, amount });
      toast.success(`Budget ${newCat}: €${amount}`);
      setNewAmount("");
      load();
    } catch {
      toast.error("Errore");
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
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <input
          type="number"
          step="0.01"
          min="1"
          placeholder="Budget €"
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
        <div className="empty">Nessun budget impostato</div>
      ) : (
        <div className="budget-list">
          {budgets.map((b) => (
            <div key={b.category} className={`budget-card ${b.status}`}>
              <div className="budget-header">
                {statusIcon(b.status)}
                <span className="budget-cat capitalize">{b.category}</span>
                <span className="budget-pct">{b.percentage}%</span>
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
                    ? `€${b.remaining.toFixed(2)} rimasti`
                    : `€${Math.abs(b.remaining).toFixed(2)} sforato`}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
