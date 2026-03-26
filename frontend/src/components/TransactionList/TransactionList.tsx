import { useEffect, useState, useCallback } from "react";
import { getTransactions, deleteTransaction, getTransactionCount } from "../../api/client";
import type { Transaction } from "../../api/client";
import { Trash2, RefreshCw, Search, X } from "lucide-react";
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
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [summary, setSummary] = useState<{ count: number; total: number } | null>(null);

  const buildParams = useCallback(() => {
    const params: Record<string, string> = {};
    if (filter) params.category = filter;
    if (search) params.search = search;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    return params;
  }, [filter, search, dateFrom, dateTo]);

  const load = useCallback(() => {
    setLoading(true);
    const params = buildParams();
    Promise.allSettled([
      getTransactions(params),
      getTransactionCount(params),
    ])
      .then(([txRes, countRes]) => {
        if (txRes.status === "fulfilled") setTxs(txRes.value.data);
        if (countRes.status === "fulfilled") setSummary(countRes.value.data);
      })
      .finally(() => setLoading(false));
  }, [buildParams]);

  useEffect(() => { load(); }, [load]);

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput), 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  const clearFilters = () => {
    setFilter("");
    setSearch("");
    setSearchInput("");
    setDateFrom("");
    setDateTo("");
  };

  const hasFilters = filter || search || dateFrom || dateTo;

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
            <button className="btn-icon" onClick={load} title="Aggiorna">
              <RefreshCw size={16} />
            </button>
          </div>
        </div>

        {/* Filtri */}
        <div className="tx-filters">
          <div className="search-box">
            <Search size={14} className="search-icon" />
            <input
              type="text"
              placeholder="Cerca per descrizione o categoria..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="search-input"
            />
            {searchInput && (
              <button className="search-clear" onClick={() => { setSearchInput(""); setSearch(""); }}>
                <X size={12} />
              </button>
            )}
          </div>

          <div className="filter-row">
            <select value={filter} onChange={(e) => setFilter(e.target.value)} className="filter-select">
              <option value="">Tutte le categorie</option>
              {Object.entries(EMOJI_MAP).map(([k, v]) => (
                <option key={k} value={k}>{v} {k}</option>
              ))}
            </select>

            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="filter-date"
              title="Da"
            />
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="filter-date"
              title="A"
            />

            {hasFilters && (
              <button className="btn-clear-filters" onClick={clearFilters} title="Rimuovi filtri">
                <X size={14} /> Rimuovi
              </button>
            )}
          </div>

          {summary && (
            <div className="tx-summary">
              <span>{summary.count} transazioni</span>
              <span className="tx-summary-total">Totale: <strong>€{summary.total.toFixed(2)}</strong></span>
            </div>
          )}
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
