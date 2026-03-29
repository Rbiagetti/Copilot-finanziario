import { useEffect, useState } from "react";
import {
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadialBarChart, RadialBar, Legend, ComposedChart, Bar, Line, BarChart
} from "recharts";
import { 
  getDashboard, getForecast, getBriefing, getAnomalies, 
  getTransactions, getBudgetStatus, getMonthlyHistory 
} from "../../api/client";
import type { 
  DashboardData, ForecastData, BriefingData, Anomaly, 
  Transaction, BudgetStatus 
} from "../../api/client";
import { useChartColors } from "../../hooks/useTheme";
import {
  TrendingUp, TrendingDown, Euro, AlertTriangle, Target, 
  RefreshCw, Info, X, Sparkles, HelpCircle
} from "lucide-react";

const INSIGHT_COLORS: Record<string, string> = { positive: "#10b981", warning: "#f59e0b", info: "#6366f1" };

// ── BoxPlot Helper ──────────────────────────────────────────────────────────
const calculateBoxData = (txs: Transaction[]) => {
  const groups: Record<string, number[]> = {};
  txs.forEach(t => {
    if (!groups[t.category]) groups[t.category] = [];
    groups[t.category].push(t.amount);
  });

  return Object.entries(groups).map(([cat, vals]) => {
    const sorted = [...vals].sort((a, b) => a - b);
    const q1 = sorted[Math.floor(sorted.length * 0.25)];
    const median = sorted[Math.floor(sorted.length * 0.5)];
    const q3 = sorted[Math.floor(sorted.length * 0.75)];
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    return { category: cat, min, q1, median, q3, max, count: vals.length };
  }).filter(d => d.count > 2).sort((a,b) => b.median - a.median);
};

// ── ChartHeader Component ───────────────────────────────────────────────────
function ChartHeader({ title, infoTitle, infoBody }: { title: string; infoTitle: string; infoBody: string }) {
  const [showInfo, setShowInfo] = useState(false);
  return (
    <>
      <div className="chart-header">
        <h3>{title}</h3>
        <button className="btn-chart-info" onClick={() => setShowInfo(true)}>
          <HelpCircle size={16} />
        </button>
      </div>
      {showInfo && (
        <div className="chart-info-overlay" onClick={() => setShowInfo(false)}>
          <div className="info-content">
            <h4>{infoTitle}</h4>
            <p>{infoBody}</p>
            <button className="btn-primary" style={{padding: '8px 20px', fontSize: '0.8rem'}}>Ho capito</button>
          </div>
        </div>
      )}
    </>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [briefing, setBriefing] = useState<BriefingData | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [topTx, setTopTx] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingBriefing, setLoadingBriefing] = useState(false);
  const [modalContent, setModalContent] = useState<{title: string, type: 'anomalies' | 'forecast'} | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [budgetStatus, setBudgetStatus] = useState<BudgetStatus[]>([]);
  const [monthlyHistory, setMonthlyHistory] = useState<{ month: string; label: string; total: number }[]>([]);
  const [boxData, setBoxData] = useState<any[]>([]);

  const loadAll = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [dash, fore, anom, txs, budgets, history] = await Promise.all([
        getDashboard(), getForecast(), getAnomalies(), getTransactions({ limit: "50" }),
        getBudgetStatus(), getMonthlyHistory(6)
      ]);
      setData(dash.data);
      setForecast(fore.data);
      setAnomalies(anom.data.anomalies || []);
      setBudgetStatus(budgets.data);
      setMonthlyHistory(history.data);
      setBoxData(calculateBoxData(txs.data));
      
      const rawTxs = txs.data || [];
      const sorted = [...rawTxs]
        .filter(t => t.amount > 0)
        .sort((a, b) => b.amount - a.amount)
        .slice(0, 5);
      setTopTx(sorted);
    } catch (e: any) { 
      console.error("Errore caricamento dati:", e); 
      setErrorMsg(e?.message || "Errore sconosciuto di rete. I dati di simulazione o l'API potrebbero essere in ri-avvio.");
    }
    setLoading(false);
  };

  const refreshBriefing = () => {
    setLoadingBriefing(true);
    getBriefing().then(res => setBriefing(res.data)).catch(() => setBriefing(null)).finally(() => setLoadingBriefing(false));
  };

  useEffect(() => { 
    loadAll(); 
    refreshBriefing(); 
  }, []);

  const cc = useChartColors();

  const CustomTooltip = ({ active, payload, label, prefix = "€", type }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="custom-tooltip card-glass" style={{ 
          padding: '12px 16px', 
          border: `1px solid ${cc.tooltipBorder}`,
          background: cc.tooltipBg,
          boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
          pointerEvents: 'none',
          zIndex: 1000
        }}>
          <p className="label" style={{ fontWeight: 800, margin: '0 0 6px', fontSize: '0.9rem', color: cc.tooltipText, borderBottom: `1px solid ${cc.gridStroke}`, paddingBottom: '4px' }}>
            {label || data.name || data.label}
          </p>
          {type === 'budget' ? (
            <div style={{ fontSize: '0.85rem', color: cc.tooltipItem }}>
              <p style={{ margin: '4px 0' }}>Utilizzo: <strong>{data.value.toFixed(1)}%</strong></p>
              <p style={{ margin: '0', fontSize: '0.75rem', opacity: 0.8 }}>Percentuale del budget mensile allocato.</p>
            </div>
          ) : (
            payload.map((entry: any, index: number) => (
              <div key={index} style={{ margin: '4px 0 0' }}>
                <span style={{ fontSize: '0.85rem', color: entry.color || cc.tooltipItem }}>
                  {entry.name}: <strong>{prefix}{Number(entry.value).toFixed(2)}</strong>
                </span>
              </div>
            ))
          )}
        </div>
      );
    }
    return null;
  };

  if (errorMsg) return <div className="loading" style={{color: 'var(--danger)', display:'flex', flexDirection:'column', gap:'1rem'}}>
    <span>⚠️ Impossibile caricare la Dashboard.</span>
    <span style={{fontSize:'0.8rem', opacity: 0.8}}>{errorMsg}</span>
  </div>;

  if (loading || !data) return <div className="loading">Sincronizzazione in corso...</div>;

  const sortedCats = [...data.by_category].sort((a, b) => b.total - a.total);

  return (
    <div className="dashboard">
      <div className="dashboard-hero">
        <h2>Dashboard</h2>
        <p className="dashboard-subtitle">Controllo totale del tuo ecosistema finanziario.</p>
      </div>

      {/* BRIEFING AI */}
      <section className="dashboard-section section-insights">
        <div className="section-head">
          <div className="flex-row" style={{display:'flex', alignItems:'center', gap:'8px'}}>
            <Sparkles size={18} color="var(--accent)"/> 
            <h3>Copilot Insights</h3>
          </div>
          <button className="btn-icon" onClick={refreshBriefing} disabled={loadingBriefing}>
            <RefreshCw size={14} className={loadingBriefing ? "spin" : ""} />
          </button>
        </div>
        <div className="briefing-card card-glass">
          {briefing?.insights && briefing.insights.length > 0 ? (
            briefing.insights.map((ins, i) => (
              <div key={i} className="briefing-insight" style={{ borderLeftColor: INSIGHT_COLORS[ins.type] || 'var(--accent)' }}>
                <span className="insight-title">{ins.title}</span>
                <span className="insight-body">{ins.body}</span>
              </div>
            ))
          ) : (
            <p className="text-dim" style={{padding:'1rem'}}>L'AI sta analizzando i tuoi movimenti...</p>
          )}
        </div>
      </section>

      {/* KPI GRID */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-icon"><Euro size={20} /></div>
          <div className="kpi-content"><span className="kpi-label">Spese mese</span><span className="kpi-value">€{data.total_month.toFixed(2)}</span></div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon" style={{color: data.variation_pct >= 0 ? "var(--danger)" : "var(--success)"}}>
            {data.variation_pct >= 0 ? <TrendingUp size={20}/> : <TrendingDown size={20}/>}
          </div>
          <div className="kpi-content"><span className="kpi-label">vs mese prec.</span><span className="kpi-value" style={{color: data.variation_pct >= 0 ? "var(--danger)" : "var(--success)"}}>{data.variation_pct >= 0 ? "+" : ""}{data.variation_pct.toFixed(1)}%</span></div>
        </div>
        <div className="kpi-card has-drilldown" onClick={() => setModalContent({title: 'Analisi Previsionale', type: 'forecast'})}>
          <Info size={14} className="drilldown-icon" />
          <div className="kpi-icon" style={{color:'var(--accent)'}}><Target size={20} /></div>
          <div className="kpi-content"><span className="kpi-label">Target fine mese</span><span className="kpi-value">€{forecast?.projected_total.toFixed(0) || "---"}</span></div>
        </div>
        <div className="kpi-card has-drilldown" onClick={() => setModalContent({title: 'Dettaglio Anomalie', type: 'anomalies'})}>
          <Info size={14} className="drilldown-icon" />
          <div className="kpi-icon" style={{color:'var(--warning)'}}><AlertTriangle size={20} /></div>
          <div className="kpi-content"><span className="kpi-label">Anomalie AI</span><span className="kpi-value" style={{color:'var(--warning)'}}>{anomalies.length} rilevate</span></div>
        </div>
      </div>

      {/* GRAFICI Data Science */}
      <section className="dashboard-section section-analytics" style={{marginTop:'1.5rem'}}>
        <div className="charts-grid">
          
          {/* 1. BoxPlot (Advanced View) */}
          <div className="chart-card">
            <ChartHeader 
              title="Varianza Spese (BoxPlot)" 
              infoTitle="Analisi della Volatilità"
              infoBody="Questo grafico mostra quanto oscillano le tue spese. I 'baffi' indicano i minimi e massimi, mentre il rettangolo (IQR) mostra dove si concentra il 50% delle spese. Più il rettangolo è grande, più la spesa in quella categoria è variabile e imprevedibile."
            />
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={boxData} layout="vertical" margin={{ left: 20, right: 20 }}>
                <XAxis type="number" hide />
                <YAxis dataKey="category" type="category" tick={{ fill: cc.tick, fontSize: 11 }} width={80} />
                <Tooltip content={<CustomTooltip prefix="€" />} cursor={{fill: 'transparent'}} />
                {/* Visualizzazione custom per BoxPlot via Stacked Bars */}
                <Bar dataKey="min" stackId="a" fill="transparent" />
                <Bar dataKey="q1" stackId="a" fill="transparent" />
                <Bar dataKey="q3" stackId="a" fill="var(--accent-glow)" stroke={cc.gridStroke} />
                <Bar dataKey="max" stackId="a" fill="transparent" />
              </BarChart>
            </ResponsiveContainer>
            <div style={{textAlign:'center', fontSize:'0.7rem', color: cc.tick, marginTop:'-10px', opacity:0.6}}>
              Nota: le linee indicano la dispersione dei costi per ogni categoria.
            </div>
          </div>

          {/* 2. Bar Chart Semplice (Base User) */}
          <div className="chart-card">
            <ChartHeader 
              title="Classifica Categorie (Semplice)" 
              infoTitle="Dove spendi di più?"
              infoBody="Una vista semplificata delle tue uscite totali per categoria questo mese. Le barre più lunghe indicano le categorie che stanno assorbendo la maggior parte delle tue risorse."
            />
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={sortedCats} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} horizontal={false} />
                <XAxis type="number" tick={{ fill: cc.tick, fontSize: 10 }} />
                <YAxis dataKey="category" type="category" tick={{ fill: cc.tick, fontSize: 11 }} width={80} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="total" fill="var(--accent)" radius={[0, 6, 6, 0]} barSize={20} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 3. Radial Bar Chart (Budget Pacing) */}
          <div className="chart-card">
            <ChartHeader 
              title="Pressione Budget" 
              infoTitle="Consumo delle Risorse"
              infoBody="Ogni cerchio è una categoria. Quando il cerchio si chiude, hai esaurito il budget. I colori cambiano (Verde > Arancio > Rosso) per aiutarti a capire subito dove devi rallentare le spese."
            />
            <ResponsiveContainer width="100%" height={300}>
              <RadialBarChart 
                cx="50%" cy="50%" 
                innerRadius="20%" outerRadius="90%" 
                barSize={15} 
                data={budgetStatus.map(b => ({
                  name: b.category,
                  fill: b.percentage > 90 ? cc.danger : b.percentage > 70 ? cc.warning : cc.success,
                  value: b.percentage
                }))}
              >
                <RadialBar background={{ fill: cc.neutral }} dataKey="value" cornerRadius={10} />
                <Tooltip content={<CustomTooltip type="budget" />} cursor={{ fill: 'transparent' }} />
                <Legend iconSize={10} layout="vertical" verticalAlign="middle" align="right" wrapperStyle={{ fontSize: '10px' }} />
              </RadialBarChart>
            </ResponsiveContainer>
          </div>

          <div className="chart-card">
            <ChartHeader 
              title="Evoluzione Mensile" 
              infoTitle="Trend nel Tempo"
              infoBody="Confronta il totale speso nei mesi passati. La linea rossa indica la variazione e ti aiuta a visualizzare se la tua spesa media sta salendo o scendendo nel lungo periodo."
            />
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={monthlyHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} vertical={false} />
                <XAxis dataKey="label" tick={{ fill: cc.tick, fontSize: 10 }} />
                <YAxis tick={{ fill: cc.tick, fontSize: 10 }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="total" fill="rgba(79, 142, 247, 0.4)" radius={[4, 4, 0, 0]} barSize={30} />
                <Line type="monotone" dataKey="total" stroke="var(--danger)" strokeWidth={2} dot={{ r: 4, fill: 'white' }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

        </div>
      </section>

      {/* TOP SPESE RILEVATE */}
      <section className="dashboard-section">
        <div className="section-head"><h3>Spese più elevate (30gg)</h3></div>
        <div className="card-glass" style={{padding: '0.5rem'}}>
          {topTx.length > 0 ? topTx.map(tx => (
            <div key={tx.id} className="tx-row" style={{padding: '12px', borderBottom: '1px solid var(--glass-border)'}}>
              <div className="tx-info">
                <span style={{fontWeight: 600, color: 'var(--text)'}}>{tx.description || tx.category}</span>
                <small style={{display:'block', color:'var(--text-dim)'}}>{tx.date} • {tx.category}</small>
              </div>
              <div className="tx-amount negative" style={{fontWeight: 700}}>€{tx.amount.toFixed(2)}</div>
            </div>
          )) : <div className="empty-state">Nessuna spesa rilevante trovata.</div>}
        </div>
      </section>

      {/* MODAL - Riprogettato per Leggibilità e Glassmorphism */}
      {modalContent && (
        <div className="modal-overlay" onClick={() => setModalContent(null)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modalContent.title}</h3>
              <button className="btn-icon" onClick={() => setModalContent(null)}><X size={18}/></button>
            </div>
            <div style={{padding: '0.5rem 1.2rem 1.2rem'}}>
              {modalContent.type === 'anomalies' && anomalies.map((a, i) => {
                const diff = ((a.amount - a.avg_category) / a.avg_category * 100).toFixed(0);
                return (
                  <div key={i} className="tx-row tx-row-modal">
                    <div className="tx-info">
                      <span className="tx-desc">{a.description || a.category}</span>
                      <small className="tx-date">Media: €{a.avg_category.toFixed(0)}</small>
                    </div>
                    <div className="anomaly-amount">
                      <div className="anomaly-val">€{a.amount}</div>
                      <span className="tx-variation-badge variation-up">+{diff}%</span>
                    </div>
                  </div>
                );
              })}
              {modalContent.type === 'forecast' && (
                <div style={{paddingTop: '10px'}}>
                  <p>Burn Rate: <strong>€{forecast?.daily_burn_rate.toFixed(2)}/gg</strong></p>
                  <p style={{marginTop: '10px'}}>Confidenza AI: <span className="badge info">{forecast?.confidence}</span></p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
