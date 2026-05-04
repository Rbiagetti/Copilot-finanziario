import { useEffect, useState, useCallback, useMemo, memo } from "react";
import { useFocusTrap } from "../../hooks/useFocusTrap";
import { getTransactions, deleteTransaction, getTransactionCount, updateTransaction, exportTransactionsCsv } from "../../api/client";
import type { Transaction } from "../../api/client";
import { Trash2, RefreshCw, Search, X, Pencil, Download, Repeat, SlidersHorizontal, ChevronDown, CalendarDays } from "lucide-react";
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
  time: string;
  tags: string;
  is_recurring: boolean;
}

const TxRow = memo(({ tx, toggling, onEdit, onDelete, onToggle }: {
  tx: Transaction;
  toggling: number | null;
  onEdit: (tx: Transaction) => void;
  onDelete: (id: number) => void;
  onToggle: (tx: Transaction) => void;
}) => {
  return (
    <div className={`tx-row ${tx.is_recurring ? "tx-recurring" : ""}`}>
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
        <button
          className={`btn-icon ${tx.is_recurring ? "active-recurring" : ""}`}
          aria-label={tx.is_recurring ? "Rimuovi ricorrente" : "Segna come ricorrente"}
          title={tx.is_recurring ? "Rimuovi ricorrente" : "Segna come ricorrente"}
          onPointerDown={() => onToggle(tx)}
          disabled={toggling === tx.id}
        >
          <Repeat size={14} />
        </button>
        <button className="btn-icon" aria-label="Modifica transazione" title="Modifica" onPointerDown={() => onEdit(tx)}>
          <Pencil size={14} />
        </button>
        <button className="btn-icon danger" aria-label="Elimina transazione" title="Elimina" onPointerDown={() => onDelete(tx.id)}>
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
});

export default function TransactionList() {
  const [txs, setTxs] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [daysRange, setDaysRange] = useState<number>(30); // da 1 a 365
  const [sortBy, setSortBy] = useState<string>("date_desc");
  const [summary, setSummary] = useState<{ count: number; total: number } | null>(null);
  const [editState, setEditState] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [groupByDate, setGroupByDate] = useState(false);
  const modalRef = useFocusTrap(!!editState);

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
    setLoadError(false);
    const params = buildParams();
    // Timeout di sicurezza: se dopo 10s è ancora in loading, mostra errore + ricarica
    const safetyTimer = setTimeout(() => {
      setLoading(curr => { if (curr) { setLoadError(true); return false; } return curr; });
    }, 10000);
    Promise.allSettled([getTransactions(params), getTransactionCount(params)])
      .then(([txRes, countRes]) => {
        clearTimeout(safetyTimer);
        if (txRes.status === "fulfilled") setTxs(txRes.value.data);
        else setLoadError(true);
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
  const { invalidateDashboardCache, markTransactionsAsNew, dashboardFilter, setDashboardFilter } = useAppStore();

  // A-4: Al mount, consuma dashboardFilter se impostato dalla Dashboard
  useEffect(() => {
    const { category } = dashboardFilter;
    if (category) {
      setFilter(category);
      setDashboardFilter({}); // consuma e resetta il filtro dopo averlo applicato
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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

  // Raggruppa per data (usato solo quando groupByDate=true)
  const groupedByDate = useMemo(() => {
    if (!groupByDate) return [];
    const groups: { date: string; label: string; total: number; txs: typeof sortedTxs }[] = [];
    sortedTxs.forEach(tx => {
      const last = groups[groups.length - 1];
      if (last && last.date === tx.date) {
        last.txs.push(tx);
        last.total += tx.amount;
      } else {
        const d = new Date(tx.date + "T12:00:00");
        const label = d.toLocaleDateString("it-IT", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
        groups.push({ date: tx.date, label, total: tx.amount, txs: [tx] });
      }
    });
    return groups;
  }, [sortedTxs, groupByDate]);

  const handleDelete = async (id: number) => {
    if (!confirm("Eliminare questa transazione?")) return;
    try {
      invalidateDashboardCache();
      markTransactionsAsNew();
      await deleteTransaction(id);
      toast.success("Transazione eliminata");
      load();
    } catch { toast.error("Errore nell'eliminazione"); }
  };

  // ESC chiude il modale di edit
  useEffect(() => {
    if (!editState) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setEditState(null); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [editState]);

  const openEdit = (tx: Transaction) => {
    setEditState({
      tx,
      amount: String(tx.amount),
      category: tx.category,
      description: tx.description || "",
      date: tx.date,
      time: tx.time || "",
      tags: tx.tags || "",
      is_recurring: tx.is_recurring ?? false,
    });
  };

  const handleSave = async () => {
    if (!editState) return;
    const num = parseFloat(editState.amount);
    if (!num || num <= 0) {
      toast.error("Inserisci un importo valido (> 0)");
      return;
    }
    // M-5: blocca date future
    if (editState.date > new Date().toISOString().slice(0, 10)) {
      toast.error("La data non può essere nel futuro");
      return;
    }
    setSaving(true);
    try {
      invalidateDashboardCache();
      markTransactionsAsNew();
      await updateTransaction(editState.tx.id, {
        amount: parseFloat(editState.amount),
        category: editState.category,
        description: editState.description,
        date: editState.date,
        time: editState.time || undefined,
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
    if (toggling === tx.id) return;
    setToggling(tx.id);
    try {
      markTransactionsAsNew();
      await updateTransaction(tx.id, { is_recurring: !tx.is_recurring });
      load();
    } catch { toast.error("Errore nell'aggiornamento"); }
    finally { setToggling(null); }
  };

  return (
    <div className="transactions-page animate-in">
      <TransactionForm onAdded={load} />

      <div className="transactions-list">
        <div className="list-header">
          <h3>Transazioni</h3>
          <div className="list-controls">
            <button
              className={`btn-icon ${groupByDate ? "active-recurring" : ""}`}
              aria-label={groupByDate ? "Vista piatta" : "Raggruppa per data"}
              title={groupByDate ? "Vista piatta" : "Raggruppa per data"}
              onClick={() => setGroupByDate(g => !g)}
            >
              <CalendarDays size={16} />
            </button>
            <button
              className="btn-icon"
              aria-label="Esporta CSV"
              title="Esporta CSV"
              disabled={exporting}
              onClick={async () => {
                setExporting(true);
                try {
                  await exportTransactionsCsv(buildParams());
                  toast.success("CSV scaricato");
                } catch (err) {
                  toast.error("Errore durante l'export");
                  console.error(err);
                } finally {
                  setExporting(false);
                }
              }}
            >
              {exporting ? <RefreshCw size={16} className="spin" /> : <Download size={16} />}
            </button>
            <button className="btn-icon" aria-label="Aggiorna lista" title="Aggiorna" onClick={load}>
              <RefreshCw size={16} />
            </button>
          </div>
        </div>

        <div className="tx-filters">
          {/* Search sempre visibile */}
          <div className="tx-filters-top">
            <div className="search-box">
              <Search size={14} className="search-icon" />
              <input
                type="text"
                placeholder="Cerca spesa..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="search-input"
              />
              {searchInput && (
                <button className="search-clear" aria-label="Cancella ricerca" onClick={() => { setSearchInput(""); setSearch(""); }}>
                  <X size={12} />
                </button>
              )}
            </div>

            {/* Filtri collassabili identici alla Dashboard */}
            <div className={`filters-collapsible ${filtersOpen ? "open" : ""}`}>
              <button
                className="filters-toggle"
                onClick={() => setFiltersOpen(o => !o)}
                aria-expanded={filtersOpen}
                aria-label="Apri filtri"
              >
                <SlidersHorizontal size={14} />
                <span>Filtri</span>
                {hasFilters && (
                  <span className="filters-badge">
                    {(filter ? 1 : 0) + (daysRange < 365 ? 1 : 0) + (sortBy !== "date_desc" ? 1 : 0)}
                  </span>
                )}
                <ChevronDown size={14} className="filters-chevron" />
              </button>
              {filtersOpen && (
                <>
                <div className="filter-backdrop" onClick={() => setFiltersOpen(false)} />
                <div className="filters-panel filters-panel--right">
                  <div className="filter-row">
                    <select value={filter} onChange={(e) => setFilter(e.target.value)} className="filter-select" aria-label="Categoria">
                      <option value="">Tutte le categorie</option>
                      {Object.entries(EMOJI_MAP).map(([k, v]) => (
                        <option key={k} value={k}>{v} {k}</option>
                      ))}
                    </select>
                  </div>
                  <div className="filter-row">
                    <select value={daysRange} onChange={(e) => setDaysRange(Number(e.target.value))} className="filter-select" aria-label="Periodo">
                      <option value="365">Tutto il periodo</option>
                      <option value="1">Oggi</option>
                      <option value="7">Ultimi 7 giorni</option>
                      <option value="30">Ultimi 30 giorni</option>
                      <option value="90">Ultimi 90 giorni</option>
                    </select>
                  </div>
                  <div className="filter-row">
                    <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="filter-select" aria-label="Ordine">
                      <option value="date_desc">Più recenti prima</option>
                      <option value="date_asc">Meno recenti prima</option>
                      <option value="amount_desc">Importo più alto</option>
                      <option value="amount_asc">Importo più basso</option>
                    </select>
                  </div>
                  {hasFilters && (
                    <button className="filters-reset" onClick={() => { clearFilters(); setFiltersOpen(false); }}>
                      <X size={12} /> Reset filtri
                    </button>
                  )}
                </div>
                </>
              )}
            </div>
          </div>

          {summary && (
            <div className="tx-summary">
              <span>{summary.count} transazioni</span>
              <span className="tx-summary-total">Totale: <strong>€{summary.total.toFixed(2)}</strong></span>
            </div>
          )}
        </div>

        {loadError ? (
          <div style={{display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:"1rem", padding:"3rem"}}>
            <p style={{color:"var(--text-muted)", fontSize:"0.9rem"}}>Impossibile caricare le transazioni.</p>
            <button className="btn-primary" style={{padding:"0.6rem 1.5rem", width:"auto"}} onClick={() => window.location.reload()}>
              Ricarica pagina
            </button>
          </div>
        ) : loading ? (
          <div className="loading" style={{display:"flex", alignItems:"center", justifyContent:"center", gap:"0.75rem", padding:"3rem"}}>
            <span className="spin" style={{width:24, height:24, border:"2px solid var(--accent)", borderTopColor:"transparent", borderRadius:"50%", flexShrink:0}} />
            <span>Caricamento...</span>
          </div>
        ) : txs.length === 0 ? (
          <div className="tx-empty-state">
            {hasFilters ? (
              <>
                <p className="tx-empty-title">Nessuna transazione trovata</p>
                <p className="tx-empty-hint">Prova a modificare i filtri o</p>
                <button className="tx-empty-cta" onClick={clearFilters}>rimuovi i filtri attivi</button>
              </>
            ) : (
              <>
                <p className="tx-empty-title">Nessuna spesa ancora</p>
                <p className="tx-empty-hint">Inizia aggiungendo la tua prima transazione qui sopra ↑</p>
              </>
            )}
          </div>
        ) : groupByDate ? (
          <div className="tx-table">
            {groupedByDate.map(group => (
              <div key={group.date} className="tx-date-group">
                <div className="tx-date-header">
                  <span className="tx-date-label">{group.label}</span>
                  <span className="tx-date-total">€{group.total.toFixed(2)}</span>
                </div>
                {group.txs.map(tx => <TxRow key={tx.id} tx={tx} toggling={toggling} onEdit={openEdit} onDelete={handleDelete} onToggle={toggleRecurring} />)}
              </div>
            ))}
          </div>
        ) : (
          <div className="tx-table">
            {sortedTxs.map((tx) => (
              <TxRow key={tx.id} tx={tx} toggling={toggling} onEdit={openEdit} onDelete={handleDelete} onToggle={toggleRecurring} />
            ))}
          </div>
        )}
      </div>

      {/* EDIT MODAL */}
      {editState && (
        <div className="modal-overlay" onClick={() => setEditState(null)}>
          <div className="modal-box" ref={modalRef} role="dialog" aria-modal="true" aria-label="Modifica transazione" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Modifica transazione</h3>
              <button className="btn-icon" aria-label="Chiudi" onClick={() => setEditState(null)}><X size={16} /></button>
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
              <div className="form-row">
                <div className="form-group">
                  <label>Data</label>
                  <input type="date" value={editState.date}
                    max={new Date().toISOString().slice(0, 10)}
                    onChange={(e) => setEditState({ ...editState, date: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Orario</label>
                  <input type="time" value={editState.time}
                    onChange={(e) => setEditState({ ...editState, time: e.target.value })} />
                </div>
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
