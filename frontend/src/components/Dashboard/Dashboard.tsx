import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Cell,
} from "recharts";
import { getDashboard, getForecast, getBriefing, getAnomalies, getTransactions } from "../../api/client";
import type { DashboardData, ForecastData, BriefingData, Anomaly, Transaction } from "../../api/client";
import { useChartColors } from "../../hooks/useTheme";
import {
  TrendingUp, TrendingDown, Euro, AlertTriangle, Target, 
  RefreshCw, Info, X, Sparkles, Plus, MessageSquare, PieChart
} from "lucide-react";
import { useAppStore } from "../../store/appStore";

const COLORS = ["#6366f1", "#f43f5e", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4"];
const INSIGHT_COLORS: Record<string, string> = { positive: "#10b981", warning: "#f59e0b", info: "#6366f1" };

export default function Dashboard() {
  const { setView } = useAppStore();
  const [data, setData] = useState<DashboardData | null>(null);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [briefing, setBriefing] = useState<BriefingData | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [topTx, setTopTx] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingBriefing, setLoadingBriefing] = useState(false);
  const [modalContent, setModalContent] = useState<{title: string, type: 'anomalies' | 'forecast'} | null>(null);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [dash, fore, anom, txs] = await Promise.all([
        getDashboard(), getForecast(), getAnomalies(), getTransactions({ limit: 50 })
      ]);
      setData(dash.data);
      setForecast(fore.data);
      setAnomalies(anom.data.anomalies || []);
      
      const rawTxs = txs.data.transactions || txs.data || [];
      const sorted = [...rawTxs]
        .filter(t => t.amount > 0)
        .sort((a, b) => b.amount - a.amount)
        .slice(0, 5);
      setTopTx(sorted);
    } catch (e) { console.error("Errore caricamento dati:", e); }
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

      {/* QUICK ACTIONS */}
      <section className="dashboard-section" style={{marginTop:'1.5rem'}}>
        <div className="quick-actions-grid">
          <div className="quick-action-card" onClick={() => setView("transactions")}>
            <div className="icon-wrapper"><Plus size={22}/></div>
            <span>Nuova Spesa</span>
          </div>
          <div className="quick-action-card" onClick={() => setView("chat")}>
            <div className="icon-wrapper"><MessageSquare size={22}/></div>
            <span>Chiedi all'AI</span>
          </div>
          <div className="quick-action-card" onClick={() => setView("budget")}>
            <div className="icon-wrapper"><PieChart size={22}/></div>
            <span>Vedi Budget</span>
          </div>
          <div className="quick-action-card" onClick={() => loadAll()}>
            <div className="icon-wrapper"><RefreshCw size={22}/></div>
            <span>Aggiorna Dati</span>
          </div>
        </div>
      </section>

      {/* GRAFICI */}
      <section className="dashboard-section section-analytics">
        <div className="charts-grid">
          <div className="chart-card">
            <h3>Spese per categoria</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={sortedCats}>
                <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} vertical={false} />
                <XAxis dataKey="category" tick={{fill: cc.tick, fontSize: 10}} angle={-20} textAnchor="end" height={50} />
                <YAxis tick={{fill: cc.tick, fontSize: 10}} />
                <Tooltip contentStyle={{background: cc.tooltipBg, border: 'none', color: cc.tick, borderRadius: 8}} />
                <Bar dataKey="total" radius={[4, 4, 0, 0]}>
                  {sortedCats.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-card">
            <h3>Trend Giornaliero (30gg)</h3>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={data.daily_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke={cc.gridStroke} vertical={false} />
                <XAxis dataKey="date" tickFormatter={v => v.slice(-2)} tick={{fill: cc.tick}} />
                <YAxis tick={{fill: cc.tick}} />
                <Tooltip contentStyle={{background: cc.tooltipBg, border: 'none', color: cc.tick, borderRadius: 8}} />
                <Line type="monotone" dataKey="total" stroke="var(--accent)" strokeWidth={3} dot={{ r: 4, fill: 'var(--accent)' }} />
              </LineChart>
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
          <div className="modal-box" onClick={e => e.stopPropagation()} style={{ background: 'var(--bg-card)', color: 'var(--text)', border: '1px solid var(--glass-border)' }}>
            <div className="modal-header">
              <h3 style={{ color: 'var(--text)' }}>{modalContent.title}</h3>
              <button className="btn-icon" onClick={() => setModalContent(null)}><X size={18}/></button>
            </div>
            <div style={{padding: '0.5rem 1.2rem 1.2rem'}}>
              {modalContent.type === 'anomalies' && anomalies.map((a, i) => {
                const diff = ((a.amount - a.avg_category) / a.avg_category * 100).toFixed(0);
                return (
                  <div key={i} className="tx-row" style={{
                    background: 'var(--glass-1)', // Ritorna l'effetto "pillola", ma segue il tema
                    border: '1px solid var(--glass-border)',
                    borderRadius: '12px',
                    padding: '12px 16px',
                    marginBottom: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}>
                    <div className="tx-info">
                      <span style={{color: 'var(--text)', fontWeight: 500, display: 'block'}}>{a.description || a.category}</span>
                      <small style={{color:'var(--text-dim)'}}>Media: €{a.avg_category.toFixed(0)}</small>
                    </div>
                    <div style={{textAlign: 'right'}}>
                      <div className="negative" style={{fontWeight:700, fontSize: '1.1rem'}}>€{a.amount}</div>
                      <span className="tx-variation-badge variation-up">+{diff}%</span>
                    </div>
                  </div>
                );
              })}
              {modalContent.type === 'forecast' && (
                <div style={{color: 'var(--text)', paddingTop: '10px'}}>
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
