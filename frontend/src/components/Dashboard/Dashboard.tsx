import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Cell, PieChart, Pie, Legend,
} from "recharts";
import { getDashboard, getForecast, getBriefing, getAnomalies, getMonthlyHistory } from "../../api/client";
import type { DashboardData, ForecastData, BriefingData, Anomaly } from "../../api/client";
import {
  TrendingUp, TrendingDown, Euro, Tag, CalendarDays, BarChart3,
  Sparkles, AlertTriangle, Target, RefreshCw,
} from "lucide-react";

const COLORS = [
  "#6366f1", "#f43f5e", "#10b981", "#f59e0b", "#8b5cf6",
  "#06b6d4", "#ec4899", "#14b8a6", "#f97316", "#64748b",
];

const EMOJI_MAP: Record<string, string> = {
  cibo: "🍕", trasporti: "🚗", casa: "🏠", salute: "💊",
  svago: "🎭", abbigliamento: "👕", lavoro: "💼",
  abbonamenti: "📱", formazione: "🎓", altro: "❓",
  intrattenimento: "🎭", shopping: "🛍️",
};

const INSIGHT_COLORS: Record<string, string> = {
  positive: "#10b981",
  warning: "#f59e0b",
  info: "#6366f1",
};

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [briefing, setBriefing] = useState<BriefingData | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [monthlyHistory, setMonthlyHistory] = useState<{ month: string; label: string; total: number }[]>([]);
  const [loadingMain, setLoadingMain] = useState(true);
  const [loadingBriefing, setLoadingBriefing] = useState(true);
  const [showAnomalies, setShowAnomalies] = useState(false);

  useEffect(() => {
    Promise.allSettled([getDashboard(), getForecast(), getAnomalies(), getMonthlyHistory(6)])
      .then(([dashRes, forecastRes, anomalyRes, historyRes]) => {
        if (dashRes.status === "fulfilled") setData(dashRes.value.data);
        if (forecastRes.status === "fulfilled") setForecast(forecastRes.value.data);
        if (anomalyRes.status === "fulfilled") setAnomalies(anomalyRes.value.data.anomalies);
        if (historyRes.status === "fulfilled") setMonthlyHistory(historyRes.value.data);
      })
      .finally(() => setLoadingMain(false));

    getBriefing()
      .then((res) => setBriefing(res.data))
      .catch(() => setBriefing(null))
      .finally(() => setLoadingBriefing(false));
  }, []);

  const refreshBriefing = () => {
    setLoadingBriefing(true);
    getBriefing()
      .then((res) => setBriefing(res.data))
      .catch(console.error)
      .finally(() => setLoadingBriefing(false));
  };

  if (loadingMain) return <div className="loading">Caricamento dashboard...</div>;
  if (!data) return <div className="error">Errore nel caricamento</div>;

  const isPositive = data.variation_pct >= 0;
  const avgDaily = data.daily_trend.length > 0
    ? data.daily_trend.reduce((s, d) => s + d.total, 0) / data.daily_trend.length
    : 0;
  const sortedCats = [...data.by_category].sort((a, b) => b.total - a.total);

  // Forecast progress bar
  const forecastPct = forecast && data.total_month > 0
    ? Math.min((forecast.projected_total / (data.total_month * (30 / (30 - forecast.days_remaining || 1)))) * 100, 150)
    : 0;
  const forecastColor = forecastPct > 120 ? "#f43f5e" : forecastPct > 100 ? "#f59e0b" : "#10b981";

  return (
    <div className="dashboard">
      <h2>Dashboard</h2>

      {/* === BRIEFING AI === */}
      <div className="briefing-card">
        <div className="briefing-header">
          <div className="briefing-title">
            <Sparkles size={18} />
            <span>Il tuo Copilota dice</span>
          </div>
          <button className="btn-icon" onClick={refreshBriefing} title="Aggiorna" disabled={loadingBriefing}>
            <RefreshCw size={14} className={loadingBriefing ? "spin" : ""} />
          </button>
        </div>

        {loadingBriefing ? (
          <div className="briefing-skeleton">
            <div className="skeleton-line" />
            <div className="skeleton-line short" />
            <div className="skeleton-line" />
          </div>
        ) : briefing ? (
          <>
            <div className="briefing-insights">
              {briefing.insights.map((ins, i) => (
                <div key={i} className="briefing-insight" style={{ borderLeftColor: INSIGHT_COLORS[ins.type] }}>
                  <span className="insight-title">{ins.title}</span>
                  <span className="insight-body">{ins.body}</span>
                </div>
              ))}
            </div>
            {briefing.action && (
              <div className="briefing-action">
                <span>💡 </span>{briefing.action}
              </div>
            )}
          </>
        ) : null}
      </div>

      {/* === KPI === */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-icon"><Euro size={24} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Spese mese</span>
            <span className="kpi-value">&euro;{data.total_month.toFixed(2)}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon">
            {isPositive ? <TrendingUp size={24} /> : <TrendingDown size={24} />}
          </div>
          <div className="kpi-content">
            <span className="kpi-label">vs mese prec.</span>
            <span className={`kpi-value ${isPositive ? "negative" : "positive"}`}>
              {isPositive ? "+" : ""}{data.variation_pct.toFixed(1)}%
            </span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon"><CalendarDays size={24} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Media giornaliera</span>
            <span className="kpi-value">&euro;{avgDaily.toFixed(2)}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon"><Tag size={24} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Top categoria</span>
            <span className="kpi-value capitalize">{data.top_category}</span>
          </div>
        </div>

        {/* Forecast KPI */}
        {forecast && (
          <div className="kpi-card kpi-forecast">
            <div className="kpi-icon"><Target size={24} /></div>
            <div className="kpi-content">
              <span className="kpi-label">
                Previsione fine mese
                <span className={`confidence-badge ${forecast.confidence}`}>{forecast.confidence}</span>
              </span>
              <span className="kpi-value" style={{ color: forecastColor }}>
                &euro;{forecast.projected_total.toFixed(0)}
              </span>
              <div className="forecast-sub">
                burn: €{forecast.daily_burn_rate.toFixed(1)}/giorno · {forecast.days_remaining}gg al mese
              </div>
            </div>
          </div>
        )}

        {/* Anomalie KPI */}
        {anomalies.length > 0 && (
          <div className="kpi-card kpi-anomaly" onClick={() => setShowAnomalies(true)} style={{ cursor: "pointer" }}>
            <div className="kpi-icon" style={{ color: "#f59e0b" }}><AlertTriangle size={24} /></div>
            <div className="kpi-content">
              <span className="kpi-label">Anomalie rilevate</span>
              <span className="kpi-value" style={{ color: "#f59e0b" }}>{anomalies.length} spese</span>
              <div className="forecast-sub">Clicca per vedere i dettagli</div>
            </div>
          </div>
        )}
      </div>

      {/* === MODAL ANOMALIE === */}
      {showAnomalies && (
        <div className="modal-overlay" onClick={() => setShowAnomalies(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>⚠️ Spese anomale rilevate</h3>
              <button className="btn-icon" onClick={() => setShowAnomalies(false)}>✕</button>
            </div>
            <p className="modal-sub">Transazioni significativamente superiori alla media della categoria (ultimi 60gg)</p>
            <div className="anomaly-list">
              {anomalies.map((a) => (
                <div key={a.id} className="anomaly-row">
                  <span className="anomaly-emoji">{EMOJI_MAP[a.category] || "❓"}</span>
                  <div className="anomaly-info">
                    <span className="anomaly-desc">{a.description || a.category}</span>
                    <span className="anomaly-date">{a.date} · media categoria: €{a.avg_category.toFixed(2)}</span>
                  </div>
                  <div className="anomaly-amount">
                    <span className="anomaly-val">€{a.amount.toFixed(2)}</span>
                    <span className="anomaly-pct">+{a.pct_above_avg}% dalla media</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* === GRAFICI === */}
      <div className="charts-grid">
        <div className="chart-card">
          <h3>Spese per categoria</h3>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={sortedCats} margin={{ bottom: 55, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a40" />
              <XAxis
                dataKey="category"
                tick={{ fill: "#aaa", fontSize: 11 }}
                angle={-40}
                textAnchor="end"
                interval={0}
              />
              <YAxis tick={{ fill: "#aaa", fontSize: 11 }} tickFormatter={(v) => `€${v}`} />
              <Tooltip
                contentStyle={{ background: "#1e1e2e", border: "1px solid #2a2a40", borderRadius: 8 }}
                labelStyle={{ color: "#fff", textTransform: "capitalize" }}
                formatter={(value: number) => [`€${value.toFixed(2)}`, "Totale"]}
              />
              <Bar dataKey="total" radius={[6, 6, 0, 0]}>
                {sortedCats.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Distribuzione spese</h3>
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={sortedCats}
                dataKey="total"
                nameKey="category"
                cx="50%"
                cy="42%"
                outerRadius={95}
                label={false}
              >
                {sortedCats.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: "#1e1e2e", border: "1px solid #2a2a40", borderRadius: 8 }}
                formatter={(value: number, _: string, props: any) => {
                  const pct = data.total_month > 0 ? ((value as number) / data.total_month * 100).toFixed(0) : 0;
                  return [`€${(value as number).toFixed(2)} (${pct}%)`, props.payload.category];
                }}
              />
              <Legend
                formatter={(value) => (
                  <span style={{ color: "#ccc", fontSize: 12, textTransform: "capitalize" }}>
                    {EMOJI_MAP[value] || "❓"} {value}
                  </span>
                )}
                wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card chart-full">
          <h3>Trend giornaliero (30gg)</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data.daily_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#aaa", fontSize: 11 }}
                tickFormatter={(v) => v.slice(5)}
              />
              <YAxis tick={{ fill: "#aaa" }} />
              <Tooltip
                contentStyle={{ background: "#1e1e2e", border: "1px solid #333", borderRadius: 8 }}
                labelStyle={{ color: "#fff" }}
                formatter={(value: number) => [`€${value.toFixed(2)}`, "Spese"]}
              />
              <Line
                type="monotone"
                dataKey="total"
                stroke="#6366f1"
                strokeWidth={2}
                dot={{ fill: "#6366f1", r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {monthlyHistory.length > 0 && (
        <div className="chart-card chart-full" style={{ marginTop: "1.5rem" }}>
          <h3>Storico mensile (6 mesi)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={monthlyHistory} margin={{ left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a40" />
              <XAxis dataKey="label" tick={{ fill: "#aaa", fontSize: 11 }} />
              <YAxis tick={{ fill: "#aaa", fontSize: 11 }} tickFormatter={(v) => `€${v}`} />
              <Tooltip
                contentStyle={{ background: "#1e1e2e", border: "1px solid #2a2a40", borderRadius: 8 }}
                formatter={(v: number) => [`€${v.toFixed(2)}`, "Spese"]}
              />
              <Bar dataKey="total" radius={[6, 6, 0, 0]}>
                {monthlyHistory.map((_, i) => (
                  <Cell key={i} fill={i === monthlyHistory.length - 1 ? "#6366f1" : "#3b3b6b"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="chart-card top-categories">
        <h3><BarChart3 size={18} /> Classifica categorie mese</h3>
        <div className="cat-ranking">
          {sortedCats.map((c, i) => {
            const pct = data.total_month > 0 ? (c.total / data.total_month) * 100 : 0;
            return (
              <div key={c.category} className="cat-rank-row">
                <span className="cat-rank-pos">#{i + 1}</span>
                <span className="cat-rank-emoji">{EMOJI_MAP[c.category] || "❓"}</span>
                <span className="cat-rank-name capitalize">{c.category}</span>
                <div className="cat-rank-bar">
                  <div
                    className="cat-rank-fill"
                    style={{ width: `${pct}%`, background: COLORS[i % COLORS.length] }}
                  />
                </div>
                <span className="cat-rank-amount">&euro;{c.total.toFixed(2)}</span>
                <span className="cat-rank-pct">{pct.toFixed(0)}%</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
