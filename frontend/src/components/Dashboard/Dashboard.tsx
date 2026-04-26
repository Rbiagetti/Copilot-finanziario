import { useEffect, useState, useMemo, useRef } from "react";
import { createPortal } from "react-dom";
import {
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell, LineChart, Line,
  BarChart, Bar, Legend
} from "recharts";
import { getForecast, getAnomalies, getFullHistory } from "../../api/client";
import type { ForecastData, Anomaly, FullHistoryTransaction } from "../../api/client";
import { useChartColors } from "../../hooks/useTheme";
import { useAppStore } from "../../store/appStore";
import { TrendingUp, Euro, AlertTriangle, Target, X, HelpCircle, Calendar, Filter, SlidersHorizontal, ChevronDown } from "lucide-react";
import { getMonthlyTrend, getCategoryData, getCalendarData, getCategoryVolatility, getRecurringData, getTimeOfDayData } from "../../utils/analyticsUtils";

const CATEGORIES = ["cibo","trasporti","casa","salute","svago","abbigliamento","lavoro","abbonamenti","formazione","altro"];
const PALETTE = ["#6366f1","#f43f5e","#10b981","#f59e0b","#8b5cf6","#06b6d4","#ec4899","#14b8a6","#f97316","#64748b"];

function ChartHeader({ title, infoTitle, infoBody }: { title: string; infoTitle: string; infoBody: string }) {
  const [showInfo, setShowInfo] = useState(false);
  return (
    <>
      <div className="chart-header">
        <h3>{title}</h3>
        <button className="btn-chart-info" onClick={(e) => { e.stopPropagation(); setShowInfo(true); }}><HelpCircle size={14} /></button>
      </div>
      {showInfo && (
        <div className="chart-info-overlay" onClick={(e) => { e.stopPropagation(); setShowInfo(false); }}>
          <div className="info-content">
            <h4>{infoTitle}</h4>
            <p>{infoBody}</p>
            <button className="btn-primary" style={{padding:'8px 20px',fontSize:'0.8rem'}}>Ho capito</button>
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
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [modalContent, setModalContent] = useState<{title: string; type: "anomalies" | "forecast"} | null>(null);
  const [daysBack, setDaysBack] = useState(90);
  const [catFilter, setCatFilter] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);

  const { setView, setDashboardFilter, dashboardCache, setDashboardCache } = useAppStore();
  const cc = useChartColors();

  const loadAll = async (force = false) => {
    // Se cache valida (< 5 min) e non forzato, usa i dati in memoria
    if (!force && dashboardCache.loadedAt && Date.now() - dashboardCache.loadedAt < 5 * 60 * 1000) {
      setRawHistory(dashboardCache.rawHistory);
      setForecast(dashboardCache.forecast);
      setAnomalies(dashboardCache.anomalies);
      setLoading(false);
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    try {
      const [hist, fore, anom] = await Promise.all([getFullHistory(), getForecast(), getAnomalies()]);
      const rawHistory = hist.data;
      const forecast = fore.data;
      const anomalies = anom.data.anomalies || [];
      setRawHistory(rawHistory);
      setForecast(forecast);
      setAnomalies(anomalies);
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
      if (t.date < cutoff.toISOString().slice(0,10)) return false;
    }
    if (catFilter && t.category !== catFilter) return false;
    return true;
  }), [rawHistory, daysBack, catFilter]);

  // Tutti i grafici temporali sono sempre raggruppati per mese (etichetta chiara, no giorni)
  const monthlyTrend   = useMemo(() => getMonthlyTrend(filteredData, "month"), [filteredData]);
  const categoryData   = useMemo(() => getCategoryData(filteredData), [filteredData]);
  const calendarData   = useMemo(() => getCalendarData(filteredData), [filteredData]);
  const volatilityData = useMemo(() => getCategoryVolatility(filteredData).slice(0, 5), [filteredData]);
  const recurringData  = useMemo(() => getRecurringData(filteredData, "month"), [filteredData]);
  const timeOfDayData  = useMemo(() => getTimeOfDayData(filteredData), [filteredData]);

  // Aggrega calendar per giorno settimana
  const calendarByDay = useMemo(() => ["Dom","Lun","Mar","Mer","Gio","Ven","Sab"].map((day, i) => ({
    day,
    total: parseFloat(calendarData.filter(d => new Date(d.date + "T12:00:00").getDay() === i).reduce((s, d) => s + d.total, 0).toFixed(2)),
    count: calendarData.filter(d => new Date(d.date + "T12:00:00").getDay() === i).length,
  })), [calendarData]);

  // Aggrega time-of-day per ora (somma tutti i giorni)
  const timeByHour = useMemo(() => {
    const hours: Record<number, { total: number; count: number }> = {};
    timeOfDayData.filter(d => d.total > 0).forEach(d => {
      if (!hours[d.hour]) hours[d.hour] = { total: 0, count: 0 };
      hours[d.hour].total += d.total;
      hours[d.hour].count += d.count;
    });
    return Array.from({length: 24}, (_, h) => ({
      ora: `${String(h).padStart(2,"0")}:00`,
      total: parseFloat((hours[h]?.total || 0).toFixed(2)),
      count: hours[h]?.count || 0,
    }));
  }, [timeOfDayData]);

  const stats = useMemo(() => ({
    total: filteredData.reduce((s, t) => s + t.amount, 0),
    count: filteredData.length,
  }), [filteredData]);

  // ESC chiude il modale KPI
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
    const title = label || p?.payload?.ora || p?.payload?.day || p?.payload?.name || p?.payload?.category || "";
    const boxStyle: React.CSSProperties = {
      background: "var(--surface-container-hi)",
      border: "1px solid var(--glass-border-hi)",
      borderRadius: 12,
      padding: "10px 14px",
      boxShadow: "0 8px 32px rgba(0,0,0,0.45)",
      backdropFilter: "blur(12px)",
      WebkitBackdropFilter: "blur(12px)",
      pointerEvents: "none" as const,
      minWidth: 140,
    };
    const titleStyle: React.CSSProperties = {
      color: "var(--text)",
      fontWeight: 700,
      fontSize: "0.85rem",
      marginBottom: 6,
      paddingBottom: 6,
      borderBottom: "1px solid var(--glass-border)",
    };
    const rowStyle: React.CSSProperties = {
      color: "var(--text-muted)",
      fontSize: "0.82rem",
      fontWeight: 500,
      margin: "3px 0",
    };
    const valueStyle: React.CSSProperties = {
      color: "var(--accent)",
      fontWeight: 700,
    };
    const dimStyle: React.CSSProperties = {
      color: "var(--text-dim)",
      fontSize: "0.75rem",
      marginTop: 4,
    };
    return (
      <div style={boxStyle}>
        <p style={titleStyle}>{title}</p>
        {payload.map((item: any, i: number) => (
          <p key={i} style={rowStyle}>
            {item.name}: <span style={valueStyle}>€{Number(item.value).toLocaleString("it-IT", {minimumFractionDigits:2})}</span>
          </p>
        ))}
        {p?.payload?.count > 0 && (
          <p style={dimStyle}>Transazioni: {p.payload.count}</p>
        )}
      </div>
    );
  };

  if (loading) return (
    <div className="flex-col" style={{height:"80vh", gap:"1rem", alignItems:"center", justifyContent:"center"}}>
      <div className="spin" style={{width:40, height:40, border:"3px solid var(--accent)", borderTopColor:"transparent", borderRadius:"50%"}}></div>
      <span>Analisi in corso...</span>
    </div>
  );

  if (errorMsg) return (
    <div className="flex-col" style={{height:"80vh", gap:"1.5rem", alignItems:"center", justifyContent:"center"}}>
      <div className="text-danger" style={{textAlign:"center", maxWidth:400}}>{errorMsg}</div>
      <button onClick={loadAll} className="btn-primary" style={{padding:"0.6rem 1.5rem"}}>Riprova</button>
    </div>
  );

  return (
    <div className="dashboard animate-in">
      <header className="dashboard-hero">
        <div className="flex-row" style={{justifyContent:"space-between", alignItems:"flex-start", flexWrap:"wrap", gap:"1rem"}}>
          <div>
            <h2>Data Intelligence</h2>
            <p className="dashboard-subtitle">Analisi avanzata del comportamento di spesa.</p>
          </div>
          <div className={`filters-collapsible ${filtersOpen ? "open" : ""}`}>
            <button
              className="filters-toggle"
              onClick={() => setFiltersOpen(o => !o)}
              aria-expanded={filtersOpen}
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
                  <button
                    className="filters-reset"
                    onClick={() => { setDaysBack(90); setCatFilter(""); }}
                  >
                    <X size={12} /> Reset
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* KPI */}
      <div className="kpi-grid" style={{marginBottom:"2rem"}}>
        <div className="kpi-card">
          <div className="kpi-icon"><Euro size={20} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Volume Totale</span>
            <span className="kpi-value">€{stats.total.toLocaleString("it-IT", {maximumFractionDigits:0})}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon" style={{color:"var(--accent)"}}><TrendingUp size={20} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Transazioni</span>
            <span className="kpi-value">{stats.count}</span>
          </div>
        </div>
        <div className="kpi-card has-drilldown" onClick={() => setModalContent({title:"Forecast AI", type:"forecast"})}>
          <div className="kpi-icon" style={{color:"var(--warning)"}}><Target size={20} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Target Mese</span>
            <span className="kpi-value">€{forecast?.projected_total.toFixed(0) || "---"}</span>
          </div>
        </div>
        <div className="kpi-card has-drilldown" onClick={() => setModalContent({title:"Anomalie", type:"anomalies"})}>
          <div className="kpi-icon" style={{color:"var(--danger)"}}><AlertTriangle size={20} /></div>
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
          <ChartHeader title="Andamento Mensile Spese" infoTitle="Andamento Mensile" infoBody="Evoluzione delle spese nel tempo. La linea tratteggiata mostra la media giornaliera del mese." />
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={monthlyTrend}>
              <defs>
                <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="var(--accent)" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} vertical={false} />
              <XAxis dataKey="label" tick={{fill:cc.tick, fontSize:10}} />
              <YAxis tick={{fill:cc.tick, fontSize:10}} tickFormatter={v => `€${v}`} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="total" name="Spesa Totale" stroke="var(--accent)" fillOpacity={1} fill="url(#colorTotal)" strokeWidth={3} />
              <Line type="monotone" dataKey="avg_daily" name="Media/giorno" stroke="var(--warning)" strokeDasharray="5 5" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* 2. Spese per Categoria */}
        <div className="chart-card card-glass">
          <ChartHeader title="Spese per Categoria" infoTitle="Mix Categorie" infoBody="Distribuzione percentuale per categoria. Clicca su una fetta per vedere le transazioni di quella categoria." />
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie data={categoryData} innerRadius={60} outerRadius={100} paddingAngle={5} dataKey="value" nameKey="name" onClick={d => handleDrilldown(d.name)}>
                {categoryData.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend verticalAlign="bottom" height={36} iconSize={10} wrapperStyle={{ fontSize: "12px" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* 3. Attività per Giorno della Settimana */}
        <div className="chart-card card-glass">
          <ChartHeader title="Attività per Giorno" infoTitle="Pattern Settimanale" infoBody="Mostra in quali giorni della settimana spendi di più in media." />
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={calendarByDay}>
              <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} vertical={false} />
              <XAxis dataKey="day" tick={{fill:cc.tick, fontSize:11}} />
              <YAxis tick={{fill:cc.tick, fontSize:10}} tickFormatter={v => `€${v}`} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="total" name="Spesa" radius={[6,6,0,0]}>
                {calendarByDay.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* 4. Volatilità per Categoria */}
        <div className="chart-card card-glass">
          <ChartHeader title="Volatilità per Categoria" infoTitle="Stabilità Spese" infoBody="Confronta la spesa media con la varianza per categoria. Alta varianza = spesa imprevedibile." />
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={volatilityData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} horizontal={false} />
              <XAxis type="number" tick={{fill:cc.tick, fontSize:10}} tickFormatter={v => `€${v}`} />
              <YAxis type="category" dataKey="category" tick={{fill:cc.tick, fontSize:10}} width={80} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="mean" name="Media" fill="var(--accent)" radius={[0,4,4,0]} />
              <Bar dataKey="stdDev" name="Varianza" fill="var(--danger)" radius={[0,4,4,0]} />
              <Legend wrapperStyle={{ fontSize: "10px" }} iconSize={10} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* 5. Costi Fissi vs Variabili */}
        <div className="chart-card card-glass">
          <ChartHeader title="Costi Fissi vs Variabili" infoTitle="Fissi vs Variabili" infoBody="Confronta mese per mese quanto spendi in costi fissi (abbonamenti, affitto) vs spese variabili." />
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={recurringData}>
              <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} vertical={false} />
              <XAxis dataKey="label" tick={{fill:cc.tick, fontSize:10}} />
              <YAxis tick={{fill:cc.tick, fontSize:10}} tickFormatter={v => `€${v}`} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="recurring" stackId="1" name="Fissi" stroke="#10b981" fill="#10b981" fillOpacity={0.4} />
              <Area type="monotone" dataKey="variable" stackId="1" name="Variabili" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.6} />
              <Legend wrapperStyle={{ fontSize: "10px" }} iconSize={10} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* 6. Abitudini Orarie */}
        <div className="chart-card card-glass">
          <ChartHeader title="Abitudini Orarie" infoTitle="Orari di Spesa" infoBody="Mostra a che ora del giorno spendi di più. Utile per identificare abitudini come pranzi fuori o acquisti serali." />
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={timeByHour}>
              <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} vertical={false} />
              <XAxis dataKey="ora" tick={{fill:cc.tick, fontSize:9}} interval={3} />
              <YAxis tick={{fill:cc.tick, fontSize:10}} tickFormatter={v => `€${v}`} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="total" name="Spesa" fill="var(--accent)" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

      </main>

      {/* MODALS — montato su body via Portal per centratura corretta */}
      {modalContent && createPortal(
        <div className="modal-overlay" onClick={() => setModalContent(null)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modalContent.title}</h3>
              <button className="btn-icon" onClick={() => setModalContent(null)}><X size={18}/></button>
            </div>
            <div style={{padding:"1.5rem"}}>
              {modalContent.type === "anomalies" && (
                <div className="flex-col" style={{gap:12}}>
                  {anomalies.length === 0 && <p className="text-dim">Nessuna anomalia rilevata.</p>}
                  {anomalies.map((a, i) => (
                    <div key={i} className="tx-row" style={{padding:12, background:"rgba(255,255,255,0.03)", borderRadius:12, border:"1px solid rgba(255,255,255,0.05)"}}>
                      <div className="flex-col">
                        <span style={{fontWeight:600}}>{a.description || a.category}</span>
                        <small className="text-dim">{a.date} · Eccede la media di €{a.avg_category.toFixed(0)}</small>
                      </div>
                      <div className="text-danger" style={{fontWeight:700}}>€{a.amount}</div>
                    </div>
                  ))}
                </div>
              )}
              {modalContent.type === "forecast" && (
                <div className="flex-col" style={{gap:"2rem", textAlign:"center"}}>
                  <div style={{fontSize:"3rem", fontWeight:800, color:"var(--accent)"}}>€{forecast?.projected_total.toFixed(0)}</div>
                  <p className="text-dim">Proiezione fine mese basata su burn-rate di €{forecast?.daily_burn_rate}/g · {forecast?.days_remaining}gg rimanenti.</p>
                  <div className="badge info" style={{alignSelf:"center"}}>Confidenza: {forecast?.confidence?.toUpperCase()}</div>
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
