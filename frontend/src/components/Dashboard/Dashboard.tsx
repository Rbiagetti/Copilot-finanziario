import { useEffect, useState, useMemo } from "react";
import { useFocusTrap } from "../../hooks/useFocusTrap";
import { createPortal } from "react-dom";
import {
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell, Line,
  BarChart, Bar, LabelList, Legend, Sector
} from "recharts";
import { getForecast, getAnomalies, getFullHistory, getBudgetStatus } from "../../api/client";
import type { ForecastData, Anomaly, FullHistoryTransaction, BudgetStatus } from "../../api/client";
import { useChartColors } from "../../hooks/useTheme";
import { useAppStore } from "../../store/appStore";
import {
  TrendingUp, Euro, AlertTriangle, Target, X, HelpCircle,
  Calendar, Filter, SlidersHorizontal, ChevronDown, PlusCircle,
  BarChart2, Wallet, ArrowRight, TrendingDown, Minus
} from "lucide-react";
import { getMonthlyTrend, getCategoryData, getRecurringData, getCalendarData, getTimeOfDayData, getCategoryMoM, getAvailableMonths } from "../../utils/analyticsUtils";

const CATEGORIES = ["cibo","trasporti","casa","salute","svago","abbigliamento","lavoro","abbonamenti","formazione","altro"];
const PALETTE = ["#6366f1","#f43f5e","#10b981","#f59e0b","#8b5cf6","#06b6d4","#ec4899","#14b8a6","#f97316","#64748b"];
const EMOJI_MAP: Record<string, string> = {
  cibo: "🍕", trasporti: "🚗", casa: "🏠", salute: "💊",
  svago: "🎭", abbigliamento: "👕", lavoro: "💼",
  abbonamenti: "📱", formazione: "🎓", altro: "❓",
};

function ChartHeader({ title, infoTitle, infoBody }: { title: string; infoTitle: string; infoBody: string }) {
  const [showInfo, setShowInfo] = useState(false);
  return (
    <>
      <div className="chart-header">
        <h3>{title}</h3>
        <button
          className="btn-chart-info"
          aria-label={`Info: ${title}`}
          onClick={(e) => { e.stopPropagation(); setShowInfo(true); }}
        >
          <HelpCircle size={14} />
        </button>
      </div>
      {showInfo && (
        <div className="chart-info-overlay" onClick={(e) => { e.stopPropagation(); setShowInfo(false); }}>
          <div className="info-content">
            <h4>{infoTitle}</h4>
            <p>{infoBody}</p>
            <button
              className="btn-primary"
              aria-label="Chiudi info"
              style={{ padding: "8px 20px", fontSize: "0.8rem" }}
              onClick={() => setShowInfo(false)}
            >
              Ho capito
            </button>
          </div>
        </div>
      )}
    </>
  );
}

export default function Dashboard() {
  const [rawHistory, setRawHistory] = useState<FullHistoryTransaction[]>([]);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [budgets, setBudgets] = useState<BudgetStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [modalContent, setModalContent] = useState<{ title: string; type: "anomalies" | "forecast" } | null>(null);
  const [daysBack, setDaysBack] = useState(90);
  const [catFilter, setCatFilter] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [patternTab, setPatternTab] = useState<"orario" | "giornaliero">("giornaliero");
  const [momA, setMomA] = useState<string>("");   // mese "corrente" (barra piena)
  const [momB, setMomB] = useState<string>("");   // mese "precedente" (barra dim)

  const { setView, setDashboardFilter, dashboardCache, setDashboardCache } = useAppStore();
  const cc = useChartColors();
  const modalRef = useFocusTrap(!!modalContent);

  const loadAll = async (force = false) => {
    if (!force && dashboardCache.loadedAt && Date.now() - dashboardCache.loadedAt < 5 * 60 * 1000) {
      setRawHistory(dashboardCache.rawHistory);
      setForecast(dashboardCache.forecast);
      setAnomalies(dashboardCache.anomalies);
      setLoading(false);
      // Budget non è in cache — lo fetchamo sempre (dati live)
      getBudgetStatus().then(r => setBudgets(r.data)).catch(() => {});
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    try {
      const [hist, fore, anom, budg] = await Promise.all([
        getFullHistory(), getForecast(), getAnomalies(), getBudgetStatus(),
      ]);
      const rawHistory = hist.data;
      const forecast = fore.data;
      const anomalies = anom.data.anomalies || [];
      setRawHistory(rawHistory);
      setForecast(forecast);
      setAnomalies(anomalies);
      setBudgets(budg.data);
      setDashboardCache({ rawHistory, forecast, anomalies });
    } catch (e: any) {
      console.error("Errore Dashboard:", e);
      setErrorMsg("Errore di caricamento dati analitici.");
    }
    setLoading(false);
  };

  useEffect(() => {
    loadAll();
    const timer = setTimeout(() => {
      setLoading(curr => {
        if (curr) setErrorMsg("Caricamento troppo lento. Riprova.");
        return false;
      });
    }, 10000);
    return () => clearTimeout(timer);
  }, []);

  const filteredData = useMemo(() => rawHistory.filter(t => {
    if (daysBack < 9999) {
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - daysBack);
      if (t.date < cutoff.toISOString().slice(0, 10)) return false;
    }
    if (catFilter && t.category !== catFilter) return false;
    return true;
  }), [rawHistory, daysBack, catFilter]);

  const monthlyTrend = useMemo(() => getMonthlyTrend(filteredData, "month"), [filteredData]);
  const categoryData = useMemo(() => getCategoryData(filteredData), [filteredData]);
  const recurringData = useMemo(() => getRecurringData(filteredData, "month"), [filteredData]);

  // Pattern temporali
  const calendarData = useMemo(() => getCalendarData(filteredData), [filteredData]);
  const calendarByDay = useMemo(() => ["Dom","Lun","Mar","Mer","Gio","Ven","Sab"].map((day, i) => ({
    day,
    total: parseFloat(calendarData.filter(d => new Date(d.date + "T12:00:00").getDay() === i).reduce((s, d) => s + d.total, 0).toFixed(2)),
    count: calendarData.filter(d => new Date(d.date + "T12:00:00").getDay() === i).length,
  })), [calendarData]);
  const timeByHour = useMemo(() => {
    const raw = getTimeOfDayData(filteredData);
    const hours: Record<number, { total: number; count: number }> = {};
    raw.filter(d => d.total > 0).forEach(d => {
      if (!hours[d.hour]) hours[d.hour] = { total: 0, count: 0 };
      hours[d.hour].total += d.total;
      hours[d.hour].count += d.count;
    });
    return Array.from({ length: 24 }, (_, h) => ({
      ora: `${String(h).padStart(2, "0")}:00`,
      total: parseFloat((hours[h]?.total || 0).toFixed(2)),
      count: hours[h]?.count || 0,
    }));
  }, [filteredData]);

  // Mesi disponibili (ordinati dal più recente)
  const availableMonths = useMemo(() => getAvailableMonths(rawHistory), [rawHistory]);

  // Valori effettivi: se l'utente non ha ancora selezionato, usa i default
  const effectiveMomA = momA || availableMonths[0]?.key || "";
  const effectiveMomB = momB || availableMonths[1]?.key || "";

  const momData = useMemo(
    () => effectiveMomA && effectiveMomB
      ? getCategoryMoM(rawHistory, effectiveMomA, effectiveMomB)
      : { rows: [], currentLabel: "", prevLabel: "" },
    [rawHistory, effectiveMomA, effectiveMomB]
  );

  // Top 10 transazioni del periodo (ordinate per importo desc)
  const top10 = useMemo(() =>
    [...filteredData].sort((a, b) => b.amount - a.amount).slice(0, 10),
    [filteredData]
  );

  // Pacing: calcolo burn rate mese corrente
  const pacing = useMemo(() => {
    if (!forecast) return null;
    const today = new Date();
    const daysInMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
    const daysElapsed = today.getDate();
    const dayPct = daysElapsed / daysInMonth; // es. 0.5 = metà mese
    const expectedByNow = forecast.projected_total * dayPct;
    const actual = forecast.month_so_far;
    const delta = actual - expectedByNow; // positivo = over pace
    const spendPct = forecast.projected_total > 0
      ? Math.min((actual / forecast.projected_total) * 100, 100)
      : 0;
    return {
      daysElapsed,
      daysInMonth,
      dayPct: Math.round(dayPct * 100),
      spendPct: Math.round(spendPct),
      actual,
      expected: expectedByNow,
      projected: forecast.projected_total,
      delta,
      isOverPace: delta > 0,
      daysRemaining: forecast.days_remaining,
      dailyBurn: forecast.daily_burn_rate,
    };
  }, [forecast]);

  const stats = useMemo(() => ({
    total: filteredData.reduce((s, t) => s + t.amount, 0),
    count: filteredData.length,
  }), [filteredData]);

  useEffect(() => {
    if (!modalContent) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setModalContent(null); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [modalContent]);

  const handleDrilldown = (cat?: string) => {
    setDashboardFilter({ category: cat });
    setView("transactions");
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    const p = payload[0];
    const title = label || p?.payload?.name || p?.payload?.category || "";
    return (
      <div style={{
        background: "var(--surface-container-hi)",
        border: "1px solid var(--glass-border-hi)",
        borderRadius: 12,
        padding: "10px 14px",
        boxShadow: "0 8px 32px rgba(0,0,0,0.45)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        pointerEvents: "none",
        minWidth: 140,
      }}>
        <p style={{ color: "var(--text)", fontWeight: 700, fontSize: "0.85rem", marginBottom: 6, paddingBottom: 6, borderBottom: "1px solid var(--glass-border)" }}>{title}</p>
        {payload.map((item: any, i: number) => (
          <p key={i} style={{ color: "var(--text-muted)", fontSize: "0.82rem", fontWeight: 500, margin: "3px 0" }}>
            {item.name}: <span style={{ color: "var(--accent)", fontWeight: 700 }}>€{Number(item.value).toLocaleString("it-IT", { minimumFractionDigits: 2 })}</span>
          </p>
        ))}
        {p?.payload?.count > 0 && (
          <p style={{ color: "var(--text-dim)", fontSize: "0.75rem", marginTop: 4 }}>Transazioni: {p.payload.count}</p>
        )}
      </div>
    );
  };

  if (loading) return (
    <div className="dashboard animate-in" aria-busy="true" aria-label="Caricamento dashboard">
      <header className="dashboard-hero">
        <div className="skeleton-line short" style={{ height: 28, width: 200 }} />
        <div className="skeleton-line" style={{ height: 14, width: 280, marginTop: 6 }} />
      </header>
      <div className="kpi-grid" style={{ marginBottom: "2rem" }}>
        {[...Array(4)].map((_, i) => (
          <div key={i} className="kpi-card" style={{ pointerEvents: "none" }}>
            <div className="skeleton-icon" />
            <div style={{ flex: 1 }}>
              <div className="skeleton-line short" style={{ marginBottom: 8 }} />
              <div className="skeleton-line" style={{ height: 24 }} />
            </div>
          </div>
        ))}
      </div>
      <div className="charts-grid">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="chart-card" style={{ pointerEvents: "none" }}>
            <div className="skeleton-line short" style={{ marginBottom: 16 }} />
            <div className="skeleton-chart" />
          </div>
        ))}
      </div>
    </div>
  );

  if (errorMsg) return (
    <div className="flex-col" style={{ height: "80vh", gap: "1.5rem", alignItems: "center", justifyContent: "center" }}>
      <div className="text-danger" style={{ textAlign: "center", maxWidth: 400 }}>{errorMsg}</div>
      <button onClick={() => loadAll(true)} className="btn-primary" style={{ padding: "0.6rem 1.5rem", width: "auto" }}>Riprova</button>
    </div>
  );

  if (!loading && rawHistory.length === 0) return (
    <div className="dashboard animate-in">
      <header className="dashboard-hero">
        <h2>Data Intelligence</h2>
        <p className="dashboard-subtitle">Analisi avanzata del comportamento di spesa.</p>
      </header>
      <div className="dashboard-empty-state">
        <div className="dashboard-empty-icon"><BarChart2 size={40} /></div>
        <h3>Nessun dato ancora</h3>
        <p>Aggiungi la tua prima spesa per sbloccare grafici, forecast e analisi comportamentali.</p>
        <button
          className="btn-primary"
          style={{ width: "auto", padding: "0.7rem 1.75rem", marginTop: "0.5rem" }}
          onClick={() => setView("transactions")}
        >
          <PlusCircle size={18} /> Aggiungi la prima spesa
        </button>
      </div>
    </div>
  );

  return (
    <div className="dashboard animate-in">
      <header className="dashboard-hero">
        <div className="flex-row" style={{ justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <h2>Data Intelligence</h2>
            <p className="dashboard-subtitle">Analisi avanzata del comportamento di spesa.</p>
          </div>
          <div className={`filters-collapsible ${filtersOpen ? "open" : ""}`}>
            <button
              className="filters-toggle"
              onClick={() => setFiltersOpen(o => !o)}
              aria-expanded={filtersOpen}
              aria-label="Apri filtri"
            >
              <SlidersHorizontal size={14} />
              <span>Filtri</span>
              {(daysBack !== 90 || catFilter) && (
                <span className="filters-badge">{(daysBack !== 90 ? 1 : 0) + (catFilter ? 1 : 0)}</span>
              )}
              <ChevronDown size={14} className="filters-chevron" />
            </button>
            {filtersOpen && (
              <div className="filters-panel">
                <div className="filter-row">
                  <Calendar size={14} className="text-dim" />
                  <select value={daysBack} onChange={e => setDaysBack(Number(e.target.value))} className="input-minimal">
                    <option value={7}>Ultima settimana</option>
                    <option value={30}>Ultimo mese</option>
                    <option value={90}>Ultimi 3 mesi</option>
                    <option value={180}>Ultimi 6 mesi</option>
                    <option value={365}>Ultimo anno</option>
                    <option value={9999}>Tutto</option>
                  </select>
                </div>
                <div className="filter-row">
                  <Filter size={14} className="text-dim" />
                  <select value={catFilter} onChange={e => setCatFilter(e.target.value)} className="input-minimal">
                    <option value="">Tutte le categorie</option>
                    {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                {(daysBack !== 90 || catFilter) && (
                  <button className="filters-reset" onClick={() => { setDaysBack(90); setCatFilter(""); }}>
                    <X size={12} /> Reset
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* KPI */}
      <div className="kpi-grid" style={{ marginBottom: "2rem" }}>
        <div className="kpi-card">
          <div className="kpi-icon"><Euro size={20} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Volume Totale</span>
            <span className="kpi-value">€{stats.total.toLocaleString("it-IT", { maximumFractionDigits: 0 })}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon" style={{ color: "var(--accent)" }}><TrendingUp size={20} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Transazioni</span>
            <span className="kpi-value">{stats.count}</span>
          </div>
        </div>
        <div className="kpi-card has-drilldown" onClick={() => setModalContent({ title: "Forecast AI", type: "forecast" })}>
          <div className="kpi-icon" style={{ color: "var(--warning)" }}><Target size={20} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Target Mese</span>
            <span className="kpi-value">€{forecast?.projected_total.toFixed(0) || "---"}</span>
          </div>
        </div>
        <div className="kpi-card has-drilldown" onClick={() => setModalContent({ title: "Anomalie", type: "anomalies" })}>
          <div className="kpi-icon" style={{ color: "var(--danger)" }}><AlertTriangle size={20} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Eventi Anomali</span>
            <span className="kpi-value">{anomalies.length} rilevati</span>
          </div>
        </div>
      </div>

      {/* CHARTS */}
      <main className="charts-grid">

        {/* 1. Andamento Mensile */}
        <div className="chart-card card-glass">
          <ChartHeader
            title="Andamento Mensile Spese"
            infoTitle="Andamento Mensile"
            infoBody="Evoluzione delle spese nel tempo. La linea tratteggiata mostra la media giornaliera del mese."
          />
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={monthlyTrend}>
              <defs>
                <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} vertical={false} />
              <XAxis dataKey="label" tick={{ fill: cc.tick, fontSize: 10 }} />
              <YAxis tick={{ fill: cc.tick, fontSize: 10 }} tickFormatter={v => `€${v}`} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="total" name="Spesa Totale" stroke="var(--accent)" fillOpacity={1} fill="url(#colorTotal)" strokeWidth={3} />
              <Line type="monotone" dataKey="avg_daily" name="Media/giorno" stroke="var(--warning)" strokeDasharray="5 5" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* 2. Spese per Categoria */}
        <div className="chart-card card-glass">
          <ChartHeader
            title="Spese per Categoria"
            infoTitle="Mix Categorie"
            infoBody="Distribuzione percentuale per categoria. Clicca su una fetta per vedere le transazioni di quella categoria."
          />
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={categoryData}
                innerRadius={60}
                outerRadius={100}
                paddingAngle={5}
                dataKey="value"
                nameKey="name"
                onClick={d => handleDrilldown(d.name)}
                activeShape={(props: any) => (
                  <Sector
                    cx={props.cx} cy={props.cy}
                    innerRadius={props.innerRadius}
                    outerRadius={props.outerRadius + 8}
                    startAngle={props.startAngle}
                    endAngle={props.endAngle}
                    fill={props.fill}
                  />
                )}
              >
                {categoryData.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend verticalAlign="bottom" height={36} iconSize={10} wrapperStyle={{ fontSize: "12px" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* 3. Budget del Mese */}
        <div className="chart-card card-glass">
          <ChartHeader
            title="Budget del Mese"
            infoTitle="Budget per Categoria"
            infoBody="Avanzamento del budget mensile per ogni categoria. Verde = nei limiti, arancio = vicino al limite (>75%), rosso = sforato."
          />
          {budgets.length === 0 ? (
            <div className="widget-empty">
              <Wallet size={28} />
              <p>Nessun budget impostato</p>
              <button className="widget-empty-cta" onClick={() => setView("budget")}>
                Configura budget <ArrowRight size={14} />
              </button>
            </div>
          ) : (
            <div className="budget-tracker-list">
              {budgets.map(b => (
                <div
                  key={b.category}
                  className={`budget-tracker-row ${b.status}`}
                  onClick={() => setView("budget")}
                  role="button"
                  tabIndex={0}
                  aria-label={`Budget ${b.category}: ${b.percentage}% utilizzato`}
                  onKeyDown={e => e.key === "Enter" && setView("budget")}
                >
                  <div className="budget-tracker-meta">
                    <span className="budget-tracker-label">
                      {EMOJI_MAP[b.category] || "❓"} <span className="capitalize">{b.category}</span>
                    </span>
                    <span className="budget-tracker-pct">{b.percentage}%</span>
                    <span className="budget-tracker-amounts">
                      €{b.spent.toFixed(0)}<span className="budget-tracker-sep">/</span>€{b.budget.toFixed(0)}
                    </span>
                  </div>
                  <div className="budget-tracker-bar-wrap">
                    <div
                      className={`budget-tracker-bar-fill ${b.status}`}
                      style={{ width: `${Math.min(b.percentage, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 4. Pacing / Burn Rate */}
        <div className="chart-card card-glass">
          <ChartHeader
            title="Ritmo di Spesa"
            infoTitle="Pacing mensile"
            infoBody="Confronta quanto hai speso finora con quanto dovresti aver speso linearmente. Se la barra arancio supera il segnaposto dei giorni, stai spendendo più del previsto."
          />
          {pacing ? (
            <div className="pacing-widget">
              <div className="pacing-status">
                {pacing.isOverPace
                  ? <><TrendingUp size={16} style={{ color: "var(--danger)" }} /><span style={{ color: "var(--danger)", fontWeight: 600 }}>Sopra ritmo di €{Math.abs(pacing.delta).toFixed(0)}</span></>
                  : pacing.delta < -1
                    ? <><TrendingDown size={16} style={{ color: "var(--success)" }} /><span style={{ color: "var(--success)", fontWeight: 600 }}>Sotto ritmo di €{Math.abs(pacing.delta).toFixed(0)}</span></>
                    : <><Minus size={16} style={{ color: "var(--text-muted)" }} /><span style={{ color: "var(--text-muted)", fontWeight: 600 }}>In linea con il ritmo</span></>
                }
                <span className="pacing-days">Giorno {pacing.daysElapsed}/{pacing.daysInMonth}</span>
              </div>

              {/* Barra pacing */}
              <div className="pacing-bar-container">
                <div className="pacing-bar-track">
                  {/* Fill: spesa attuale */}
                  <div
                    className={`pacing-bar-fill ${pacing.isOverPace ? "over" : "ok"}`}
                    style={{ width: `${pacing.spendPct}%` }}
                  />
                  {/* Marker: dove "dovresti essere" oggi */}
                  <div
                    className="pacing-day-marker"
                    style={{ left: `${pacing.dayPct}%` }}
                    title={`Oggi: giorno ${pacing.daysElapsed} (${pacing.dayPct}% del mese)`}
                  />
                </div>
                <div className="pacing-bar-labels">
                  <span>€0</span>
                  <span>€{pacing.projected.toFixed(0)} proiettato</span>
                </div>
              </div>

              {/* Numeri chiave */}
              <div className="pacing-stats">
                <div className="pacing-stat">
                  <span className="pacing-stat-label">Speso</span>
                  <span className="pacing-stat-value">€{pacing.actual.toFixed(0)}</span>
                </div>
                <div className="pacing-stat">
                  <span className="pacing-stat-label">Atteso oggi</span>
                  <span className="pacing-stat-value">€{pacing.expected.toFixed(0)}</span>
                </div>
                <div className="pacing-stat">
                  <span className="pacing-stat-label">Media/giorno</span>
                  <span className="pacing-stat-value">€{pacing.dailyBurn.toFixed(1)}</span>
                </div>
                <div className="pacing-stat">
                  <span className="pacing-stat-label">Giorni rimasti</span>
                  <span className="pacing-stat-value">{pacing.daysRemaining}gg</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="widget-empty">
              <Target size={28} />
              <p>Dati insufficienti per il calcolo del ritmo</p>
            </div>
          )}
        </div>

        {/* 5. Costi Fissi vs Variabili */}
        <div className="chart-card card-glass">
          <ChartHeader
            title="Costi Fissi vs Variabili"
            infoTitle="Fissi vs Variabili"
            infoBody="Confronta mese per mese quanto spendi in costi fissi (abbonamenti, affitto) vs spese variabili."
          />
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={recurringData}>
              <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} vertical={false} />
              <XAxis dataKey="label" tick={{ fill: cc.tick, fontSize: 10 }} />
              <YAxis tick={{ fill: cc.tick, fontSize: 10 }} tickFormatter={v => `€${v}`} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="recurring" stackId="1" name="Fissi" stroke="#10b981" fill="#10b981" fillOpacity={0.4} />
              <Area type="monotone" dataKey="variable" stackId="1" name="Variabili" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.6} />
              <Legend wrapperStyle={{ fontSize: "10px" }} iconSize={10} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* 6. Pattern Temporali — tab Giornaliero / Orario */}
        <div className="chart-card card-glass">
          <div className="chart-header">
            <h3>Pattern Temporali</h3>
            <div className="pattern-tabs">
              <button
                className={`pattern-tab ${patternTab === "giornaliero" ? "active" : ""}`}
                onClick={() => setPatternTab("giornaliero")}
                aria-pressed={patternTab === "giornaliero"}
              >
                Per giorno
              </button>
              <button
                className={`pattern-tab ${patternTab === "orario" ? "active" : ""}`}
                onClick={() => setPatternTab("orario")}
                aria-pressed={patternTab === "orario"}
              >
                Per ora
              </button>
            </div>
          </div>

          {patternTab === "giornaliero" ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={calendarByDay}>
                <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} vertical={false} />
                <XAxis dataKey="day" tick={{ fill: cc.tick, fontSize: 11 }} />
                <YAxis tick={{ fill: cc.tick, fontSize: 10 }} tickFormatter={v => `€${v}`} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="total" name="Spesa" radius={[6, 6, 0, 0]}>
                  {calendarByDay.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                  <LabelList dataKey="total" position="top" style={{ fill: "var(--text-muted)", fontSize: 10 }} formatter={(v: number) => v > 0 ? `€${v}` : ""} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={timeByHour}>
                <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} vertical={false} />
                <XAxis dataKey="ora" tick={{ fill: cc.tick, fontSize: 9 }} interval={3} />
                <YAxis tick={{ fill: cc.tick, fontSize: 10 }} tickFormatter={v => `€${v}`} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="total" name="Spesa" fill="var(--accent)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* 7. Top 10 Spese del Periodo */}
        <div className="chart-card card-glass">
          <ChartHeader
            title="Top Spese del Periodo"
            infoTitle="Transazioni più alte"
            infoBody="Le 10 spese più elevate nel periodo selezionato. Clicca su una riga per vedere tutte le transazioni di quella categoria."
          />
          {top10.length === 0 ? (
            <div className="widget-empty">
              <Euro size={28} />
              <p>Nessuna transazione nel periodo</p>
            </div>
          ) : (
            <div className="top-tx-list">
              {top10.map((tx, i) => (
                <div
                  key={tx.id}
                  className="top-tx-row"
                  onClick={() => handleDrilldown(tx.category)}
                  role="button"
                  tabIndex={0}
                  aria-label={`${tx.category} €${tx.amount.toFixed(2)} del ${tx.date}`}
                  onKeyDown={e => e.key === "Enter" && handleDrilldown(tx.category)}
                >
                  <span className="top-tx-rank">{i + 1}</span>
                  <span className="top-tx-emoji">{EMOJI_MAP[tx.category] || "❓"}</span>
                  <div className="top-tx-info">
                    <span className="top-tx-cat capitalize">{tx.category}</span>
                    <span className="top-tx-meta">{tx.date}</span>
                  </div>
                  <span className="top-tx-amount">€{tx.amount.toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 8. Confronto Mese-su-Mese per Categoria */}
        {availableMonths.length >= 2 && (
          <div className="chart-card card-glass chart-full">
            {/* Header con selects inline */}
            <div className="chart-header mom-header">
              <h3>Confronto categorie</h3>
              <div className="mom-selects">
                <select
                  className="mom-select"
                  value={effectiveMomA}
                  onChange={e => setMomA(e.target.value)}
                  aria-label="Mese A"
                >
                  {availableMonths.map(m => (
                    <option key={m.key} value={m.key} disabled={m.key === effectiveMomB}>{m.label}</option>
                  ))}
                </select>
                <span className="mom-vs">vs</span>
                <select
                  className="mom-select"
                  value={effectiveMomB}
                  onChange={e => setMomB(e.target.value)}
                  aria-label="Mese B"
                >
                  {availableMonths.map(m => (
                    <option key={m.key} value={m.key} disabled={m.key === effectiveMomA}>{m.label}</option>
                  ))}
                </select>
                <button
                  className="btn-chart-info"
                  aria-label="Info: Confronto categorie"
                  onClick={() => {/* info inline non serve, niente overlay */}}
                  title="Confronta la spesa per categoria tra due mesi a scelta. Barra piena = mese A, barra trasparente = mese B. Il % a destra indica la variazione."
                >
                  <HelpCircle size={14} />
                </button>
              </div>
            </div>

            {momData.rows.length === 0 ? (
              <div className="widget-empty">
                <p>Nessun dato per i mesi selezionati</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(200, momData.rows.length * 44)}>
                <BarChart data={momData.rows} layout="vertical" margin={{ left: 8, right: 44 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} horizontal={false} />
                  <XAxis type="number" tick={{ fill: cc.tick, fontSize: 10 }} tickFormatter={v => `€${v}`} />
                  <YAxis
                    type="category"
                    dataKey="category"
                    tick={{ fill: cc.tick, fontSize: 10 }}
                    width={92}
                    tickFormatter={v => `${EMOJI_MAP[v] || "❓"} ${v}`}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: "11px" }} iconSize={10} />
                  <Bar dataKey="previous" name={momData.prevLabel} fill="rgba(255,140,66,0.28)" radius={[0, 3, 3, 0]} />
                  <Bar dataKey="current" name={momData.currentLabel} fill="var(--accent)" radius={[0, 3, 3, 0]}>
                    <LabelList
                      dataKey="deltaPct"
                      position="right"
                      style={{ fill: "var(--text-dim)", fontSize: 10 }}
                      formatter={(v: number | null) => v !== null ? (v > 0 ? `+${v}%` : `${v}%`) : "nuovo"}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        )}

      </main>

      {/* MODALS */}
      {modalContent && createPortal(
        <div className="modal-overlay" onClick={() => setModalContent(null)}>
          <div
            className="modal-box"
            ref={modalRef}
            role="dialog"
            aria-modal="true"
            aria-label={modalContent.title}
            onClick={e => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3>{modalContent.title}</h3>
              <button className="btn-icon" aria-label="Chiudi" onClick={() => setModalContent(null)}><X size={18} /></button>
            </div>
            <div style={{ padding: "1.5rem" }}>
              {modalContent.type === "anomalies" && (
                <div className="flex-col" style={{ gap: 12 }}>
                  {anomalies.length === 0 && <p className="text-dim">Nessuna anomalia rilevata.</p>}
                  {anomalies.map((a, i) => (
                    <div key={i} className="tx-row" style={{ padding: 12, background: "rgba(255,255,255,0.03)", borderRadius: 12, border: "1px solid rgba(255,255,255,0.05)" }}>
                      <div className="flex-col">
                        <span style={{ fontWeight: 600 }}>{a.description || a.category}</span>
                        <small className="text-dim">{a.date} · Eccede la media di €{a.avg_category.toFixed(0)}</small>
                      </div>
                      <div className="text-danger" style={{ fontWeight: 700 }}>€{a.amount}</div>
                    </div>
                  ))}
                </div>
              )}
              {modalContent.type === "forecast" && (
                <div className="flex-col" style={{ gap: "2rem", textAlign: "center" }}>
                  <div style={{ fontSize: "3rem", fontWeight: 800, color: "var(--accent)" }}>€{forecast?.projected_total.toFixed(0)}</div>
                  <p className="text-dim">Proiezione fine mese basata su burn-rate di €{forecast?.daily_burn_rate}/g · {forecast?.days_remaining}gg rimanenti.</p>
                  <div className="badge info" style={{ alignSelf: "center" }}>Confidenza: {forecast?.confidence?.toUpperCase()}</div>
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
