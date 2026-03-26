import { useEffect, useState, useCallback } from "react";
import { getTransactions, deleteTransaction, getTransactionCount, updateTransaction, exportTransactionsCsv } from "../../api/client";
import type { Transaction } from "../../api/client";
import { Trash2, RefreshCw, Search, X, Pencil, Download, Repeat } from "lucide-react";
import toast from "react-hot-toast";
import TransactionForm from "../TransactionForm/TransactionForm";

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
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [summary, setSummary] = useState<{ count: number; total: number } | null>(null);
  const [editState, setEditState] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);

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

  const clearFilters = () => {
    setFilter(""); setSearch(""); setSearchInput(""); setDateFrom(""); setDateTo("");
  };
  const hasFilters = filter || search || dateFrom || dateTo;

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
    <div className="transactions-page">
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

          <div className="filter-row">
            <select value={filter} onChange={(e) => setFilter(e.target.value)} className="filter-select">
              <option value="">Tutte le categorie</option>
              {Object.entries(EMOJI_MAP).map(([k, v]) => (
                <option key={k} value={k}>{v} {k}</option>
              ))}
            </select>
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="filter-date" title="Da" />
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="filter-date" title="A" />
            {hasFilters && (
              <button className="btn-clear-filters" onClick={clearFilters}><X size={14} /> Rimuovi</button>
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
