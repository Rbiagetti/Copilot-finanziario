import { useEffect, useState } from "react";
import { getTransactions, deleteTransaction, Transaction } from "../../api/client";
import { Trash2, RefreshCw } from "lucide-react";
import toast from "react-hot-toast";
import TransactionForm from "../TransactionForm/TransactionForm";

const EMOJI_MAP: Record<string, string> = {
  cibo: "🍕", trasporti: "🚗", casa: "🏠", salute: "💊",
  svago: "🎭", abbigliamento: "👕", lavoro: "💼",
  abbonamenti: "📱", formazione: "🎓", altro: "❓",
  intrattenimento: "🎭", shopping: "🛍️",
};

export default function TransactionList() {
  const [txs, setTxs] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  const load = () => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (filter) params.category = filter;
    getTransactions(params)
      .then((res) => setTxs(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [filter]);

  const handleDelete = async (id: number) => {
    try {
      await deleteTransaction(id);
      toast.success("Transazione eliminata");
      load();
    } catch {
      toast.error("Errore nell'eliminazione");
    }
  };

  return (
    <div className="transactions-page">
      <TransactionForm onAdded={load} />

      <div className="transactions-list">
        <div className="list-header">
          <h3>Transazioni</h3>
          <div className="list-controls">
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="">Tutte le categorie</option>
              {Object.entries(EMOJI_MAP).map(([k, v]) => (
                <option key={k} value={k}>{v} {k}</option>
              ))}
            </select>
            <button className="btn-icon" onClick={load} title="Aggiorna">
              <RefreshCw size={16} />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="loading">Caricamento...</div>
        ) : txs.length === 0 ? (
          <div className="empty">Nessuna transazione trovata</div>
        ) : (
          <div className="tx-table">
            {txs.map((tx) => (
              <div key={tx.id} className="tx-row">
                <span className="tx-emoji">{EMOJI_MAP[tx.category] || "❓"}</span>
                <div className="tx-info">
                  <span className="tx-category">{tx.category}</span>
                  <span className="tx-desc">{tx.description || "—"}</span>
                </div>
                <span className="tx-date">{tx.date}</span>
                <span className="tx-amount">&euro;{tx.amount.toFixed(2)}</span>
                <button
                  className="btn-icon danger"
                  onClick={() => handleDelete(tx.id)}
                  title="Elimina"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
