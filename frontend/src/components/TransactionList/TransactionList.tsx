import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { getTransactions, deleteTransaction, getTransactionCount, updateTransaction, exportTransactionsCsv } from "../../api/client";
import type { Transaction } from "../../api/client";
import { Trash2, RefreshCw, Search, X, Pencil, Download, Repeat } from "lucide-react";
import toast from "react-hot-toast";
import TransactionForm from "../TransactionForm/TransactionForm";
import { useAppStore } from "../../store/appStore";

const EMOJI_MAP: Record<string, string> = {
  cibo: "🍕", trasporti: "🚗", casa: "🏠", salute: "💊",
  svago: "🎭", abbigliamento: "👕", lavoro: "💼",
  abbonamenti: "📱", formazione: "🎓", altro: "❓",
  intrattenimento: "🎭", shopping: "🛍️",
};

const CATEGORIES = ["cibo","trasporti","casa","salute","svago","abbigliamento","lavoro","abbonamenti","formazione","altro"];

interface EditState {
  tx: Transaction;
  amount: string;
  category: string;
  description: string;
  date: string;
  tags: string;
  is_recurring: boolean;
}

export default function TransactionList() {
  const [txs, setTxs] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [daysRange, setDaysRange] = useState<number>(30); // da 1 a 365
  const [sortBy, setSortBy] = useState<string>("date_desc");
  const [summary, setSummary] = useState<{ count: number; total: number } | null>(null);
  const [editState, setEditState] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);

  const buildParams = useCallback(() => {
    const params: Record<string, string> = {};
    if (filter) params.category = filter;
    if (search) params.search = search;
    if (daysRange < 365) {
      const d = new Date();
      d.setDate(d.getDate() - daysRange);
      params.date_from = d.toISOString().slice(0, 10);
    }
    return params;
  }, [filter, search, daysRange]);

  const load = useCallback(() => {
    setLoading(true);
    const params = buildParams();
    Promise.allSettled([getTransactions(params), getTransactionCount(params)])
      .then(([txRes, countRes]) => {
        if (txRes.status === "fulfilled") setTxs(txRes.value.data);
        if (countRes.status === "fulfilled") setSummary(countRes.value.data);
      })
      .finally(() => setLoading(false));
  }, [buildParams]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput), 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  // DRILLDOWN: Carica filtri dalla Dashboard
  const { dashboardFilter, setDashboardFilter } = useAppStore();
  const drilldownApplied = useRef(false);
  useEffect(() => {
    if (Object.keys(dashboardFilter).length > 0 && !drilldownApplied.current) {
      drilldownApplied.current = true;
      if (dashboardFilter.category) setFilter(dashboardFilter.category);
      if (dashboardFilter.tags) setSearchInput(dashboardFilter.tags);
      setDashboardFilter({});
    }
    if (Object.keys(dashboardFilter).length === 0) {
      drilldownApplied.current = false;
    }
  }, [dashboardFilter, setDashboardFilter]);

  const clearFilters = () => {
    setFilter(""); setSearch(""); setSearchInput(""); setDaysRange(365); setSortBy("date_desc");
  };
  const hasFilters = filter || search || daysRange < 365 || sortBy !== "date_desc";

  const sortedTxs = useMemo(() => {
    const arr = [...txs];
    arr.sort((a, b) => {
      if (sortBy === "date_desc") return new Date(b.date).getTime() - new Date(a.date).getTime();
      if (sortBy === "date_asc") return new Date(a.date).getTime() - new Date(b.date).getTime();
      if (sortBy === "amount_desc") return b.amount - a.amount;
      if (sortBy === "amount_asc") return a.amount - b.amount;
      return 0;
    });
    return arr;
  }, [txs, sortBy]);

  const handleDelete = async (id: number) => {
    if (!confirm("Eliminare questa transazione?")) return;
    try {
      await deleteTransaction(id);
      toast.success("Transazione eliminata");
      load();
    } catch { toast.error("Errore nell'eliminazione"); }
  };

  const openEdit = (tx: Transaction) => {
    setEditState({
      tx,
      amount: String(tx.amount),
      category: tx.category,
      description: tx.description || "",
      date: tx.date,
      tags: tx.tags || "",
      is_recurring: tx.is_recurring ?? false,
    });
  };

  const handleSave = async () => {
    if (!editState) return;
    setSaving(true);
    try {
      await updateTransaction(editState.tx.id, {
        amount: parseFloat(editState.amount),
        category: editState.category,
        description: editState.description,
        date: editState.date,
        tags: editState.tags || undefined,
        is_recurring: editState.is_recurring,
      });
      toast.success("Salvato");
      setEditState(null);
      load();
    } catch { toast.error("Errore nel salvataggio"); }
    finally { setSaving(false); }
  };

  const toggleRecurring = async (tx: Transaction) => {
    try {
      await updateTransaction(tx.id, { is_recurring: !tx.is_recurring });
      load();
    } catch { toast.error("Errore"); }
  };

  return (
    <div className="transactions-page animate-in">
      <TransactionForm onAdded={load} />

      <div className="transactions-list">
        <div className="list-header">
          <h3>Transazioni</h3>
          <div className="list-controls">
            <button className="btn-icon" onClick={() => exportTransactionsCsv(buildParams())} title="Esporta CSV">
              <Download size={16} />
            </button>
            <button className="btn-icon" onClick={load} title="Aggiorna">
              <RefreshCw size={16} />
            </button>
          </div>
        </div>

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

          <div className="filter-row" style={{alignItems: 'center', gap: '1rem', flexWrap: 'wrap'}}>
            <select value={filter} onChange={(e) => setFilter(e.target.value)} className="filter-select">
              <option value="">Tutte Categorie</option>
              {Object.entries(EMOJI_MAP).map(([k, v]) => (
                <option key={k} value={k}>{v} {k}</option>
              ))}
            </select>
            
            <select value={daysRange} onChange={(e) => setDaysRange(Number(e.target.value))} className="filter-select">
              <option value="365">Periodo: Tutto</option>
              <option value="1">Oggi</option>
              <option value="7">Ultimi 7 gg</option>
              <option value="30">Ultimi 30 gg</option>
              <option value="90">Ultimi 90 gg</option>
            </select>

            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="filter-select">
              <option value="date_desc">Più recenti</option>
              <option value="date_asc">Meno recenti</option>
              <option value="amount_desc">Importo più alto</option>
              <option value="amount_asc">Importo più basso</option>
            </select>

            {hasFilters && (
              <button className="btn-clear-filters" onClick={clearFilters} title="Resetta filtri">
                <X size={14} />
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
            {sortedTxs.map((tx) => (
              <div key={tx.id} className={`tx-row ${tx.is_recurring ? "tx-recurring" : ""}`}>
                <span className="tx-emoji">{EMOJI_MAP[tx.category] || "❓"}</span>
                <div className="tx-info">
                  <div className="tx-info-top">
                    <span className="tx-category">{tx.category}</span>
                    {tx.is_recurring && <span className="badge-recurring" title="Ricorrente"><Repeat size={11} /> ricorrente</span>}
                    {tx.tags && tx.tags.split(",").map(t => t.trim()).filter(Boolean).map(tag => (
                      <span key={tag} className="badge-tag">{tag}</span>
                    ))}
                  </div>
                  <span className="tx-desc">{tx.description || "—"}</span>
                </div>
                <span className="tx-date">{tx.date}</span>
                <span className="tx-amount">€{tx.amount.toFixed(2)}</span>
                <div className="tx-actions">
                  <button className={`btn-icon ${tx.is_recurring ? "active-recurring" : ""}`} onClick={() => toggleRecurring(tx)} title="Segna come ricorrente">
                    <Repeat size={13} />
                  </button>
                  <button className="btn-icon" onClick={() => openEdit(tx)} title="Modifica">
                    <Pencil size={13} />
                  </button>
                  <button className="btn-icon danger" onClick={() => handleDelete(tx.id)} title="Elimina">
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* EDIT MODAL */}
      {editState && (
        <div className="modal-overlay" onClick={() => setEditState(null)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Modifica transazione</h3>
              <button className="btn-icon" onClick={() => setEditState(null)}>✕</button>
            </div>
            <div className="edit-form">
              <div className="form-group">
                <label>Importo (€)</label>
                <input type="number" step="0.01" value={editState.amount}
                  onChange={(e) => setEditState({ ...editState, amount: e.target.value })} />
              </div>
              <div className="form-group">
                <label>Categoria</label>
                <select value={editState.category}
                  onChange={(e) => setEditState({ ...editState, category: e.target.value })}>
                  {CATEGORIES.map(c => <option key={c} value={c}>{EMOJI_MAP[c]} {c}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Descrizione</label>
                <input type="text" value={editState.description}
                  onChange={(e) => setEditState({ ...editState, description: e.target.value })} />
              </div>
              <div className="form-group">
                <label>Data</label>
                <input type="date" value={editState.date}
                  onChange={(e) => setEditState({ ...editState, date: e.target.value })} />
              </div>
              <div className="form-group">
                <label>Tag (separati da virgola)</label>
                <input type="text" placeholder="es. lavoro, deducibile, regalo"
                  value={editState.tags}
                  onChange={(e) => setEditState({ ...editState, tags: e.target.value })} />
              </div>
              <div className="form-group-check">
                <input type="checkbox" id="recurring-check" checked={editState.is_recurring}
                  onChange={(e) => setEditState({ ...editState, is_recurring: e.target.checked })} />
                <label htmlFor="recurring-check">Ricorrente mensile</label>
              </div>
              <button className="btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? "Salvataggio..." : "Salva modifiche"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
