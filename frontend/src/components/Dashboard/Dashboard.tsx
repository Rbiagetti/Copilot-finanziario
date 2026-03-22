import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Cell,
} from "recharts";
import { getDashboard, DashboardData } from "../../api/client";
import { TrendingUp, TrendingDown, DollarSign, Tag } from "lucide-react";

const COLORS = [
  "#6366f1", "#f43f5e", "#10b981", "#f59e0b", "#8b5cf6",
  "#06b6d4", "#ec4899", "#14b8a6", "#f97316", "#64748b",
];

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

  return (
    <div className="dashboard">
      <h2>Dashboard</h2>

      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-icon"><DollarSign size={24} /></div>
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
          <div className="kpi-icon"><DollarSign size={24} /></div>
          <div className="kpi-content">
            <span className="kpi-label">Mese precedente</span>
            <span className="kpi-value">&euro;{data.total_prev_month.toFixed(2)}</span>
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
          <h3>Trend giornaliero (30gg)</h3>
          <ResponsiveContainer width="100%" height={300}>
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
              />
              <Line
                type="monotone"
                dataKey="total"
                stroke="#6366f1"
                strokeWidth={2}
                dot={{ fill: "#6366f1", r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
