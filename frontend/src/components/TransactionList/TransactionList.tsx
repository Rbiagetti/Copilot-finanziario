import { useEffect, useState, useCallback, useMemo, memo, useRef } from "react";
import { useFocusTrap } from "../../hooks/useFocusTrap";
import { useBodyScrollLock } from "../../hooks/useBodyScrollLock";
import { getTransactions, deleteTransaction, bulkDeleteTransactions, getTransactionCount, getTransactionDateBounds, updateTransaction, exportTransactionsCsv } from "../../api/client";
import type { Transaction } from "../../api/client";
import { Trash2, RefreshCw, Search, X, Pencil, Download, Repeat, ListFilter, ChevronDown, CalendarDays, CheckSquare, Square, ListChecks } from "lucide-react";
import toast from "react-hot-toast";
import TransactionForm from "../TransactionForm/TransactionForm";
import { useAppStore } from "../../store/appStore";
import { CategoryIcon } from "../../lib/categoryIcons";

const CATEGORIES = ["cibo","trasporti","casa","salute","svago","abbigliamento","lavoro","abbonamenti","formazione","altro"];

const MESI_SHORT = ["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"];

/** Costruisce l'elenco mesi (ascendente) da startY/startM al mese corrente incluso.
 *  Senza bounds reali (bootstrap prima della risposta API) ricade sul solo mese corrente. */
function buildMonthsRange(start: { y: number; m: number } | null): { y: number; m: number }[] {
  const now = new Date();
  const endY = now.getFullYear(), endM = now.getMonth() + 1;
  let y = start?.y ?? endY;
  let m = start?.m ?? endM;
  const out: { y: number; m: number }[] = [];
  while (y < endY || (y === endY && m <= endM)) {
    out.push({ y, m });
    m += 1;
    if (m > 12) { m = 1; y += 1; }
  }
  return out.length ? out : [{ y: endY, m: endM }];
}

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

const TxRow = memo(({ tx, toggling, onEdit, onDelete, onToggle, selectMode, selected, onToggleSelect }: {
  tx: Transaction;
  toggling: number | null;
  onEdit: (tx: Transaction) => void;
  onDelete: (id: number) => void;
  onToggle: (tx: Transaction) => void;
  selectMode: boolean;
  selected: boolean;
  onToggleSelect: (id: number) => void;
}) => {
  return (
    <div
      className={`tx-row ${tx.is_recurring ? "tx-recurring" : ""} ${selectMode ? "tx-row--selectable" : ""} ${selected ? "tx-row--selected" : ""}`}
      onClick={selectMode ? () => onToggleSelect(tx.id) : undefined}
    >
      {selectMode && (
        <button
          type="button"
          className="tx-select-check"
          aria-label={selected ? "Deseleziona" : "Seleziona"}
          onClick={(e) => { e.stopPropagation(); onToggleSelect(tx.id); }}
        >
          {selected ? <CheckSquare size={18} /> : <Square size={18} />}
        </button>
      )}
      <span className="tx-emoji"><CategoryIcon category={tx.category} size={17} /></span>
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
      {!selectMode && (
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
      )}
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
  const [dateBoundsStart, setDateBoundsStart] = useState<{ y: number; m: number } | null>(null);
  const MONTHS = useMemo(() => buildMonthsRange(dateBoundsStart), [dateBoundsStart]);
  const [monthRange, setMonthRange] = useState<[number, number]>([0, MONTHS.length - 1]); // indici in MONTHS, default = tutta la finestra
  // true solo dopo un'interazione REALE dell'utente con lo slider (drag/tap/tastiera).
  // Prima capivamo "l'utente ha ristretto la selezione" confrontando gli indici con un
  // ref mutato dentro l'updater di setState — ambiguo (indistinguibile da "range pieno
  // per coincidenza") e fragile con StrictMode. Con un flag esplicito la ricalibrazione
  // sotto sa sempre con certezza se deve forzare "tutto il periodo" oppure no.
  const userNarrowedRef = useRef(false);

  // Al mount, recupera la data della prima transazione reale: lo slider deve coprire
  // "dal primo mese con dati a oggi", non una finestra fissa arbitraria (es. 24 mesi
  // anche se i dati partono da pochi mesi fa non ha senso farlo partire da più indietro).
  useEffect(() => {
    getTransactionDateBounds()
      .then((res) => {
        const d = new Date(res.data.min_date);
        if (!isNaN(d.getTime())) setDateBoundsStart({ y: d.getFullYear(), m: d.getMonth() + 1 });
      })
      .catch(() => { /* fallback: resta il solo mese corrente */ });
  }, []);

  // Quando MONTHS cambia (arrivo dei bounds reali), il default resta "tutto il periodo"
  // finché l'utente non ha toccato lo slider di persona.
  useEffect(() => {
    if (!userNarrowedRef.current) setMonthRange([0, MONTHS.length - 1]);
  }, [MONTHS]);
  const [sortBy, setSortBy] = useState<string>("date_desc");
  const [summary, setSummary] = useState<{ count: number; total: number } | null>(null);
  const [editState, setEditState] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [groupByDate, setGroupByDate] = useState(false);
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const modalRef = useFocusTrap(!!editState);
  useBodyScrollLock(!!editState);
  const txFiltersBtnRef = useRef<HTMLButtonElement>(null);
  const txFiltersPanelRef = useRef<HTMLDivElement>(null);
  const rangeTrackRef = useRef<HTMLDivElement>(null);
  const draggingThumbRef = useRef<"min" | "max" | null>(null);

  // Slider periodo custom (pointer events, non nativo): due <input type=range> sovrapposti
  // sono inaffidabili su mobile/Safari (il trucco CSS pointer-events non è consistente),
  // quindi il drag è gestito a mano mappando la posizione X sul track a un indice mese.
  // monthSpan non è mai 0: con un solo mese disponibile (dati appena iniziati, o bounds
  // non ancora caricati) MONTHS.length-1 varrebbe 0 e ogni divisione per calcolare le
  // percentuali del thumb produrrebbe NaN → thumb "morti" e slider non trascinabile.
  const monthSpan = Math.max(1, MONTHS.length - 1);

  const monthIndexFromClientX = useCallback((clientX: number) => {
    const el = rangeTrackRef.current;
    if (!el) return 0;
    const rect = el.getBoundingClientRect();
    const frac = rect.width > 0 ? (clientX - rect.left) / rect.width : 0;
    const clamped = Math.min(1, Math.max(0, frac));
    return Math.round(clamped * monthSpan);
  }, [monthSpan]);

  const startDrag = (which: "min" | "max") => (e: React.PointerEvent) => {
    e.preventDefault();
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    draggingThumbRef.current = which;
  };
  const onDragMove = (e: React.PointerEvent) => {
    if (!draggingThumbRef.current) return;
    userNarrowedRef.current = true;
    const idx = monthIndexFromClientX(e.clientX);
    setMonthRange(([lo, hi]) =>
      draggingThumbRef.current === "min" ? [Math.min(idx, hi), hi] : [lo, Math.max(idx, lo)]
    );
  };
  const endDrag = () => { draggingThumbRef.current = null; };

  // Tap/click diretto sul track: sposta il cursore più vicino nel punto toccato
  const onTrackPointerDown = (e: React.PointerEvent) => {
    if (e.target !== e.currentTarget) return; // ignora se il tap è partito da un thumb
    userNarrowedRef.current = true;
    const idx = monthIndexFromClientX(e.clientX);
    setMonthRange(([lo, hi]) => {
      const which = Math.abs(idx - lo) <= Math.abs(idx - hi) ? "min" : "max";
      draggingThumbRef.current = which;
      return which === "min" ? [Math.min(idx, hi), hi] : [lo, Math.max(idx, lo)];
    });
  };

  const nudgeThumb = (which: "min" | "max", dir: 1 | -1) => {
    userNarrowedRef.current = true;
    setMonthRange(([lo, hi]) => {
      if (which === "min") return [Math.min(Math.max(lo + dir, 0), hi), hi];
      return [lo, Math.max(Math.min(hi + dir, MONTHS.length - 1), lo)];
    });
  };

  // Chiudi panel filtri al tap fuori — no backdrop, zero conflitti iOS/z-index
  useEffect(() => {
    if (!filtersOpen) return;
    const handler = (e: PointerEvent) => {
      const t = e.target as Node;
      if (txFiltersBtnRef.current?.contains(t)) return;
      if (txFiltersPanelRef.current?.contains(t)) return;
      setFiltersOpen(false);
    };
    document.addEventListener("pointerdown", handler, { capture: true });
    return () => document.removeEventListener("pointerdown", handler, { capture: true });
  }, [filtersOpen]);

  const buildParams = useCallback(() => {
    const params: Record<string, string> = {};
    if (filter) params.category = filter;
    if (search) params.search = search;
    const isFullRange = monthRange[0] === 0 && monthRange[1] === MONTHS.length - 1;
    if (!isFullRange) {
      const from = MONTHS[Math.min(monthRange[0], MONTHS.length - 1)] ?? MONTHS[0];
      const to = MONTHS[Math.min(monthRange[1], MONTHS.length - 1)] ?? MONTHS[0];
      params.date_from = `${from.y}-${String(from.m).padStart(2, "0")}-01`;
      const lastDay = new Date(to.y, to.m, 0).getDate(); // giorno 0 del mese dopo = ultimo giorno del mese corrente
      params.date_to = `${to.y}-${String(to.m).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`;
    }
    return params;
  }, [filter, search, monthRange, MONTHS]);

  // Contatore di sequenza: ogni drag dello slider aggiorna monthRange ad ogni pixel,
  // quindi buildParams/load cambiano identità e partono fetch multipli in rapida
  // successione. Senza guardia, una risposta VECCHIA che arriva DOPO una più recente
  // (rete/ordine non garantiti) può sovrascrivere lo stato buono con un falso errore —
  // è la causa dell'errore "Impossibile caricare le transazioni" intermittente mentre
  // si trascina il filtro periodo. Solo la risposta della request più recente conta.
  const loadSeqRef = useRef(0);

  const load = useCallback(() => {
    const seq = ++loadSeqRef.current;
    setLoading(true);
    setLoadError(false);
    const params = buildParams();
    // Timeout di sicurezza: se dopo 10s è ancora in loading, mostra errore + ricarica
    const safetyTimer = setTimeout(() => {
      if (seq !== loadSeqRef.current) return; // superata da una request più recente
      setLoading(curr => { if (curr) { setLoadError(true); return false; } return curr; });
    }, 10000);
    Promise.allSettled([getTransactions(params), getTransactionCount(params)])
      .then(([txRes, countRes]) => {
        clearTimeout(safetyTimer);
        if (seq !== loadSeqRef.current) return; // risposta di una request ormai obsoleta: ignora
        if (txRes.status === "fulfilled") setTxs(txRes.value.data);
        else setLoadError(true);
        if (countRes.status === "fulfilled") setSummary(countRes.value.data);
      })
      .finally(() => {
        if (seq !== loadSeqRef.current) return;
        setLoading(false);
      });
  }, [buildParams]);

  // Debounce del trigger: durante il drag dello slider monthRange cambia ad ogni
  // pixel — senza debounce partirebbero decine di fetch concorrenti per un singolo
  // trascinamento, inutili e più soggetti a intoppi di rete/backend sotto carico.
  useEffect(() => {
    const t = setTimeout(() => load(), 250);
    return () => clearTimeout(t);
  }, [load]);

  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput), 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  // DRILLDOWN: Carica filtri dalla Dashboard
  const { markTransactionsAsNew, dashboardFilter, setDashboardFilter } = useAppStore();

  // A-4: Al mount, consuma dashboardFilter se impostato dalla Dashboard
  useEffect(() => {
    const { category } = dashboardFilter;
    if (category) {
      setFilter(category);
      setDashboardFilter({}); // consuma e resetta il filtro dopo averlo applicato
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const clearFilters = () => {
    userNarrowedRef.current = false;
    setFilter(""); setSearch(""); setSearchInput(""); setMonthRange([0, MONTHS.length - 1]); setSortBy("date_desc");
  };
  const isFullMonthRange = monthRange[0] === 0 && monthRange[1] === MONTHS.length - 1;
  const hasFilters = filter || search || !isFullMonthRange || sortBy !== "date_desc";

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
    setSaving(true);
    try {
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

  const exitSelectMode = () => { setSelectMode(false); setSelectedIds(new Set()); };

  const toggleSelectId = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const allVisibleSelected = sortedTxs.length > 0 && sortedTxs.every((t) => selectedIds.has(t.id));
  const toggleSelectAllVisible = () => {
    setSelectedIds((prev) => {
      if (allVisibleSelected) {
        const next = new Set(prev);
        sortedTxs.forEach((t) => next.delete(t.id));
        return next;
      }
      const next = new Set(prev);
      sortedTxs.forEach((t) => next.add(t.id));
      return next;
    });
  };

  const handleBulkDelete = async () => {
    const count = selectedIds.size;
    if (count === 0) return;
    if (!confirm(`Eliminare ${count} transazion${count === 1 ? "e" : "i"}? L'azione non è reversibile.`)) return;
    setBulkDeleting(true);
    try {
      markTransactionsAsNew();
      const { data } = await bulkDeleteTransactions(Array.from(selectedIds));
      toast.success(`${data.deleted} transazioni eliminate`);
      exitSelectMode();
      load();
    } catch {
      toast.error("Errore durante l'eliminazione multipla");
    } finally {
      setBulkDeleting(false);
    }
  };

  return (
    <div className="transactions-page animate-in">
      <TransactionForm onAdded={load} />

      <div className="transactions-list">
        <div className="list-header">
          <h3>Transazioni</h3>
          <div className="list-controls">
            <button
              className={`btn-icon ${selectMode ? "active-recurring" : ""}`}
              aria-label={selectMode ? "Esci da selezione multipla" : "Seleziona più transazioni"}
              title={selectMode ? "Esci da selezione multipla" : "Seleziona più transazioni"}
              onClick={() => (selectMode ? exitSelectMode() : setSelectMode(true))}
            >
              <ListChecks size={16} />
            </button>
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
          {/* Slider periodo: sempre visibile, sopra la barra di ricerca */}
          <div className="tx-range-bar">
            {(() => {
              // Indici clampati difensivamente: MONTHS[monthRange[i]] non deve MAI risultare
              // undefined (altrimenti .m crasha tutto il componente) e monthSpan non è mai 0
              // (altrimenti le percentuali del thumb sarebbero NaN e lo slider risulterebbe
              // "morto" — non trascinabile — con dati concentrati in un solo mese).
              const safeLo = Math.min(monthRange[0], MONTHS.length - 1);
              const safeHi = Math.min(monthRange[1], MONTHS.length - 1);
              const monthLo = MONTHS[safeLo] ?? MONTHS[0];
              const monthHi = MONTHS[safeHi] ?? MONTHS[0];
              const pctLo = (safeLo / monthSpan) * 100;
              const pctHi = (safeHi / monthSpan) * 100;
              return (
                <>
                  <div className="tx-range-bar-head">
                    <CalendarDays size={13} />
                    <span className="tx-range-bar-value">
                      {isFullMonthRange
                        ? "Tutto il periodo"
                        : safeLo === safeHi
                          ? `${MESI_SHORT[monthLo.m - 1]} ${monthLo.y}`
                          : `${MESI_SHORT[monthLo.m - 1]} ${monthLo.y} → ${MESI_SHORT[monthHi.m - 1]} ${monthHi.y}`}
                    </span>
                    {!isFullMonthRange && (
                      <button className="tx-range-bar-reset" onClick={() => { userNarrowedRef.current = false; setMonthRange([0, MONTHS.length - 1]); }} aria-label="Reset periodo">
                        <X size={11} /> reset
                      </button>
                    )}
                  </div>

                  <div
                    className="range-slider"
                    ref={rangeTrackRef}
                    onPointerDown={onTrackPointerDown}
                    onPointerMove={onDragMove}
                    onPointerUp={endDrag}
                    onPointerCancel={endDrag}
                  >
                    <div className="range-slider-track" />
                    <div
                      className="range-slider-fill"
                      style={{
                        left: `${pctLo}%`,
                        right: `${100 - pctHi}%`,
                      }}
                    />
                    <div
                      className="range-thumb"
                      style={{ left: `${pctLo}%` }}
                      onPointerDown={startDrag("min")}
                      onPointerMove={onDragMove}
                      onPointerUp={endDrag}
                      onPointerCancel={endDrag}
                      onKeyDown={(e) => {
                        if (e.key === "ArrowLeft") { e.preventDefault(); nudgeThumb("min", -1); }
                        if (e.key === "ArrowRight") { e.preventDefault(); nudgeThumb("min", 1); }
                      }}
                      role="slider"
                      aria-label="Da mese"
                      aria-valuemin={0}
                      aria-valuemax={MONTHS.length - 1}
                      aria-valuenow={safeLo}
                      tabIndex={0}
                    />
                    <div
                      className="range-thumb"
                      style={{ left: `${pctHi}%` }}
                      onPointerDown={startDrag("max")}
                      onPointerMove={onDragMove}
                      onPointerUp={endDrag}
                      onPointerCancel={endDrag}
                      onKeyDown={(e) => {
                        if (e.key === "ArrowLeft") { e.preventDefault(); nudgeThumb("max", -1); }
                        if (e.key === "ArrowRight") { e.preventDefault(); nudgeThumb("max", 1); }
                      }}
                      role="slider"
                      aria-label="A mese"
                      aria-valuemin={0}
                      aria-valuemax={MONTHS.length - 1}
                      aria-valuenow={safeHi}
                      tabIndex={0}
                    />
                  </div>

                  <div className="tx-range-bar-edges">
                    <span>{MESI_SHORT[MONTHS[0].m - 1]} {MONTHS[0].y}</span>
                    <span>Oggi</span>
                  </div>
                </>
              );
            })()}
          </div>

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

            <div className={`filters-collapsible ${filtersOpen ? "open" : ""}`}>
              <button
                ref={txFiltersBtnRef}
                className="filters-toggle"
                onClick={() => setFiltersOpen(o => !o)}
                aria-expanded={filtersOpen}
                aria-label="Apri filtri"
              >
                <ListFilter size={14} />
                <span>Filtri</span>
                {hasFilters && (
                  <span className="filters-badge">
                    {(filter ? 1 : 0) + (!isFullMonthRange ? 1 : 0) + (sortBy !== "date_desc" ? 1 : 0)}
                  </span>
                )}
                <ChevronDown size={14} className="filters-chevron" />
              </button>
            </div>
            {filtersOpen && (
              <div ref={txFiltersPanelRef} className="filters-panel">
                <div className="filter-row">
                  <select value={filter} onChange={(e) => setFilter(e.target.value)} className="filter-select" aria-label="Categoria">
                    <option value="">Tutte le categorie</option>
                    {CATEGORIES.map((k) => (
                      <option key={k} value={k}>{k}</option>
                    ))}
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
            )}
          </div>

          {summary && (
            <div className="tx-summary">
              <span>{summary.count} transazioni</span>
              <span className="tx-summary-total">Totale: <strong>€{summary.total.toFixed(2)}</strong></span>
            </div>
          )}
        </div>

        {selectMode && (
          <div className="tx-bulk-bar">
            <button type="button" className="tx-bulk-selectall" onClick={toggleSelectAllVisible}>
              {allVisibleSelected ? <CheckSquare size={16} /> : <Square size={16} />}
              <span>{allVisibleSelected ? "Deseleziona tutto" : "Seleziona tutto"} ({sortedTxs.length})</span>
            </button>
            <span className="tx-bulk-count">{selectedIds.size} selezionate</span>
            <div className="tx-bulk-actions">
              <button type="button" className="btn-logout" onClick={exitSelectMode} disabled={bulkDeleting}>
                Annulla
              </button>
              <button
                type="button"
                className="btn-icon danger tx-bulk-delete"
                onClick={handleBulkDelete}
                disabled={selectedIds.size === 0 || bulkDeleting}
              >
                <Trash2 size={14} />
                <span>{bulkDeleting ? "Eliminazione..." : `Elimina (${selectedIds.size})`}</span>
              </button>
            </div>
          </div>
        )}

        {loadError ? (
          <div style={{display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:"1rem", padding:"3rem"}}>
            <p style={{color:"var(--text-muted)", fontSize:"0.9rem"}}>Impossibile caricare le transazioni.</p>
            <button className="btn-primary" style={{padding:"0.6rem 1.5rem", width:"auto"}} onClick={() => window.location.reload()}>
              Ricarica pagina
            </button>
          </div>
        ) : loading ? (
          <div className="tx-table tx-skeleton-list" aria-busy="true" aria-label="Caricamento transazioni">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="tx-row tx-row--skeleton">
                <div className="skeleton skeleton-icon" style={{ width: 32, height: 32, borderRadius: "50%", flexShrink: 0 }} />
                <div className="tx-info" style={{ gap: "0.35rem" }}>
                  <div className="skeleton skeleton-text" style={{ width: "40%" }} />
                  <div className="skeleton skeleton-text" style={{ width: "65%", opacity: 0.6 }} />
                </div>
                <div className="skeleton skeleton-text" style={{ width: 70 }} />
                <div className="skeleton skeleton-text" style={{ width: 55 }} />
                <div style={{ display: "flex", gap: "0.4rem" }}>
                  {[...Array(3)].map((_, j) => (
                    <div key={j} className="skeleton" style={{ width: 28, height: 28, borderRadius: 8 }} />
                  ))}
                </div>
              </div>
            ))}
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
                {group.txs.map(tx => (
                  <TxRow
                    key={tx.id} tx={tx} toggling={toggling} onEdit={openEdit} onDelete={handleDelete} onToggle={toggleRecurring}
                    selectMode={selectMode} selected={selectedIds.has(tx.id)} onToggleSelect={toggleSelectId}
                  />
                ))}
              </div>
            ))}
          </div>
        ) : (
          <div className="tx-table">
            {sortedTxs.map((tx) => (
              <TxRow
                key={tx.id} tx={tx} toggling={toggling} onEdit={openEdit} onDelete={handleDelete} onToggle={toggleRecurring}
                selectMode={selectMode} selected={selectedIds.has(tx.id)} onToggleSelect={toggleSelectId}
              />
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
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
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
