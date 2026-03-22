import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Cell, PieChart, Pie,
} from "recharts";
import { getDashboard } from "../../api/client";
import type { DashboardData } from "../../api/client";
import { TrendingUp, TrendingDown, Euro, Tag, CalendarDays, BarChart3 } from "lucide-react";

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

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboard()
      .then((res) => setData(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Caricamento dashboard...</div>;
  if (!data) return <div className="error">Errore nel caricamento</div>;

  const isPositive = data.variation_pct >= 0;
  const avgDaily = data.daily_trend.length > 0
    ? data.daily_trend.reduce((s, d) => s + d.total, 0) / data.daily_trend.length
    : 0;
  const sortedCats = [...data.by_category].sort((a, b) => b.total - a.total);

  return (
    <div className="dashboard">
      <h2>Dashboard</h2>

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
      </div>

      <div className="charts-grid">
        <div className="chart-card">
          <h3>Spese per categoria</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.by_category}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="category" tick={{ fill: "#aaa", fontSize: 12 }} />
              <YAxis tick={{ fill: "#aaa" }} />
              <Tooltip
                contentStyle={{ background: "#1e1e2e", border: "1px solid #333", borderRadius: 8 }}
                labelStyle={{ color: "#fff" }}
                formatter={(value: number) => [`€${value.toFixed(2)}`, "Totale"]}
              />
              <Bar dataKey="total" radius={[6, 6, 0, 0]}>
                {data.by_category.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Distribuzione spese</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={data.by_category}
                dataKey="total"
                nameKey="category"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label={({ category, percent }) =>
                  `${EMOJI_MAP[category] || ""} ${(percent * 100).toFixed(0)}%`
                }
              >
                {data.by_category.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: "#1e1e2e", border: "1px solid #333", borderRadius: 8 }}
                formatter={(value: number) => [`€${value.toFixed(2)}`, "Totale"]}
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
