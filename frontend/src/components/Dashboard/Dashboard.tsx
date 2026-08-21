import { useEffect, useState, useMemo, useRef } from "react";
import {
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area, Legend
} from "recharts";
import { getFullHistory } from "../../api/client";
import type { FullHistoryTransaction } from "../../api/client";
import { useChartColors } from "../../hooks/useTheme";
import { useAppStore } from "../../store/appStore";
import {
  TrendingUp, Euro, Calendar, ListFilter, BarChart2, PlusCircle, RefreshCw, Wallet
} from "lucide-react";
import { getRecurringData, getCategoryData } from "../../utils/analyticsUtils";

const EMOJI_MAP: Record<string, string> = {
  cibo: "🍕", trasporti: "🚗", casa: "🏠", salute: "💊",
  svago: "🎭", abbigliamento: "👕", lavoro: "💼",
  abbonamenti: "📱", formazione: "🎓", altro: "❓",
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
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
      <p style={{ color: "var(--text)", fontWeight: 700, fontSize: "0.85rem", marginBottom: 6, paddingBottom: 6, borderBottom: "1px solid var(--glass-border)" }}>{label}</p>
      {payload.map((item: any, i: number) => (
        <p key={i} style={{ color: "var(--text-muted)", fontSize: "0.82rem", fontWeight: 500, margin: "3px 0" }}>
          {item.name}: <span style={{ color: "var(--accent)", fontWeight: 700 }}>€{Number(item.value).toLocaleString("it-IT", { minimumFractionDigits: 2 })}</span>
        </p>
      ))}
    </div>
  );
};

export default function Dashboard() {
  const [rawHistory, setRawHistory] = useState<FullHistoryTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => { isMountedRef.current = false; };
  }, []);

  const { setView, setDashboardFilter, dashboardCache, setDashboardCache } = useAppStore();
  const cc = useChartColors();

  const loadAll = async (force = false) => {
    const CACHE_TTL = 5 * 60 * 1000; // 5 minuti
    const cacheValid = !force
      && dashboardCache.loadedAt
      && Date.now() - dashboardCache.loadedAt < CACHE_TTL;

    if (cacheValid) {
      setRawHistory(dashboardCache.rawHistory);
      setLoading(false);
      return;
    }

    if (force) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setErrorMsg(null);
    try {
      const hist = await getFullHistory();
      if (!isMountedRef.current) return;
      setRawHistory(hist.data);
      setDashboardCache({ rawHistory: hist.data, forecast: dashboardCache.forecast });
      setErrorMsg(null);
    } catch (e: any) {
      if (!isMountedRef.current) return;
      console.error("Errore Dashboard:", e);
      setErrorMsg("Errore di caricamento dati analitici.");
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
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

  const recurringData = useMemo(() => getRecurringData(rawHistory, "month"), [rawHistory]);

  const now = new Date();
  const curYear = now.getFullYear();
  const curMonth = now.getMonth();
  const prevMonthDate = new Date(curYear, curMonth - 1, 1);

  const currentMonthTxs = useMemo(() => rawHistory.filter(t => {
    const d = new Date(t.date);
    return d.getFullYear() === curYear && d.getMonth() === curMonth;
  }), [rawHistory, curYear, curMonth]);

  const prevMonthTxs = useMemo(() => rawHistory.filter(t => {
    const d = new Date(t.date);
    return d.getFullYear() === prevMonthDate.getFullYear() && d.getMonth() === prevMonthDate.getMonth();
  }), [rawHistory, prevMonthDate]);

  const stats = useMemo(() => {
    const totalCurrent = currentMonthTxs.reduce((s, t) => s + t.amount, 0);
    const totalPrev = prevMonthTxs.reduce((s, t) => s + t.amount, 0);
    const totalAll = rawHistory.reduce((s, t) => s + t.amount, 0);
    const daysElapsed = now.getDate();
    return {
      totalCurrent,
      totalPrev,
      totalAll,
      countCurrent: currentMonthTxs.length,
      countTotal: rawHistory.length,
      avgPerDay: daysElapsed > 0 ? totalCurrent / daysElapsed : 0,
    };
  }, [currentMonthTxs, prevMonthTxs, rawHistory]);

  const categoriesThisMonth = useMemo(() => getCategoryData(currentMonthTxs), [currentMonthTxs]);

  const handleDrilldown = (cat?: string) => {
    setDashboardFilter({ category: cat });
    setView("transactions");
  };

  if (loading) return (
    <div className="dashboard animate-in" aria-busy="true" aria-label="Caricamento dashboard">
      <header className="dashboard-hero">
        <div className="skeleton-line short" style={{ height: 28, width: 200 }} />
        <div className="skeleton-line" style={{ height: 14, width: 280, marginTop: 6 }} />
      </header>
      <div className="kpi-grid">
        {[...Array(6)].map((_, i) => (
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
        <div className="chart-card" style={{ pointerEvents: "none" }}>
          <div className="skeleton-line short" style={{ marginBottom: 16 }} />
          <div className="skeleton-chart" />
        </div>
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
        <h2>Panoramica</h2>
        <p className="dashboard-subtitle">I numeri essenziali delle tue spese.</p>
      </header>
      <div className="dashboard-empty-state">
        <div className="dashboard-empty-icon"><BarChart2 size={40} /></div>
        <h3>Nessun dato ancora</h3>
        <p>Aggiungi la tua prima spesa per vedere qui le tue statistiche.</p>
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
            <h2>Panoramica</h2>
            <p className="dashboard-subtitle">I numeri essenziali delle tue spese.</p>
          </div>
          <button
            className="filters-toggle"
            onClick={() => loadAll(true)}
            disabled={refreshing}
            aria-label="Aggiorna dashboard"
            title="Forza aggiornamento dati"
          >
            <RefreshCw size={14} className={refreshing ? "spin" : ""} />
            <span>{refreshing ? "Aggiornamento…" : "Aggiorna"}</span>
          </button>
        </div>
      </header>

      {/* KPI */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-icon"><Euro size={20} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Spese mese corrente</span>
            <span className="kpi-value">€{stats.totalCurrent.toLocaleString("it-IT", { maximumFractionDigits: 0 })}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon" style={{ color: "var(--text-muted)" }}><Calendar size={20} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Spese mese scorso</span>
            <span className="kpi-value">€{stats.totalPrev.toLocaleString("it-IT", { maximumFractionDigits: 0 })}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon" style={{ color: "var(--accent)" }}><Wallet size={20} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Spesa totale</span>
            <span className="kpi-value">€{stats.totalAll.toLocaleString("it-IT", { maximumFractionDigits: 0 })}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon" style={{ color: "var(--accent)" }}><ListFilter size={20} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Transazioni mese corrente</span>
            <span className="kpi-value">{stats.countCurrent}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon" style={{ color: "var(--accent)" }}><TrendingUp size={20} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Transazioni totali</span>
            <span className="kpi-value">{stats.countTotal}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon" style={{ color: "var(--warning)" }}><BarChart2 size={20} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Spesa media al giorno</span>
            <span className="kpi-value">€{stats.avgPerDay.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* CHARTS */}
      <main className="charts-grid">

        {/* Categorie del mese */}
        <div className="chart-card card-glass">
          <div className="chart-header">
            <h3>Categorie del mese</h3>
          </div>
          {categoriesThisMonth.length === 0 ? (
            <div className="widget-empty">
              <Euro size={28} />
              <p>Nessuna transazione questo mese</p>
            </div>
          ) : (
            <div className="top-tx-list">
              {categoriesThisMonth.map((c, i) => (
                <div
                  key={c.name}
                  className="top-tx-row"
                  onClick={() => handleDrilldown(c.name)}
                  role="button"
                  tabIndex={0}
                  aria-label={`${c.name} €${c.value.toFixed(2)}, ${c.percentage}% del mese`}
                  onKeyDown={e => e.key === "Enter" && handleDrilldown(c.name)}
                >
                  <span className="top-tx-rank">{i + 1}</span>
                  <span className="top-tx-emoji">{EMOJI_MAP[c.name] || "❓"}</span>
                  <div className="top-tx-info">
                    <span className="top-tx-cat capitalize">{c.name}</span>
                    <span className="top-tx-meta">{c.percentage}% · {c.count} tx</span>
                  </div>
                  <span className="top-tx-amount">€{c.value.toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Costi Fissi vs Variabili */}
        <div className="chart-card card-glass">
          <div className="chart-header">
            <h3>Costi Fissi vs Variabili</h3>
          </div>
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

      </main>
    </div>
  );
}
