import axios from "axios";
import { getToken } from "../lib/supabase";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1",
});

// Attacca il JWT Supabase ad ogni richiesta
api.interceptors.request.use(async (config) => {
  const token = await getToken();
  if (token) {
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

export interface Transaction {
  id: number;
  amount: number;
  category: string;
  description: string | null;
  date: string;
  time: string | null;
  account: string;
  source: string;
  tags: string | null;
  is_recurring: boolean | null;
  created_at: string | null;
}

export interface DashboardData {
  total_month: number;
  total_prev_month: number;
  variation_pct: number;
  top_category: string;
  by_category: { category: string; total: number }[];
  daily_trend: { date: string; total: number }[];
}

export interface TableData {
  headers: string[];
  rows: (string | number)[][];
}

export interface ChatResponse {
  answer: string;
  chart_data: { type: string; data: { name: string; value: number }[]; title: string } | null;
  data_table: TableData | null;
  followup_questions: string[];
}

export interface BudgetStatus {
  category: string;
  budget: number;
  spent: number;
  remaining: number;
  percentage: number;
  status: "ok" | "warning" | "over";
}

export interface ForecastData {
  projected_total: number;
  month_so_far: number;
  daily_burn_rate: number;
  days_remaining: number;
  confidence: "high" | "medium" | "low";
}

export interface BriefingInsight {
  title: string;
  body: string;
  type: "positive" | "warning" | "info";
}

export interface BriefingData {
  insights: BriefingInsight[];
  action: string;
}

export interface Anomaly {
  id: number;
  amount: number;
  category: string;
  description: string;
  date: string;
  z_score: number;
  avg_category: number;
  pct_above_avg: number;
}

export const getTransactions = (params?: Record<string, string>) =>
  api.get<Transaction[]>("/transactions/", { params });

export const getTransactionCount = (params?: Record<string, string>) =>
  api.get<{ count: number; total: number }>("/transactions/count", { params });

export const createTransaction = (data: {
  amount: number;
  category: string;
  description?: string;
  date?: string;
}) => api.post<Transaction>("/transactions/", data);

export const deleteTransaction = (id: number) =>
  api.delete(`/transactions/${id}`);

export const getDashboard = () =>
  api.get<DashboardData>("/analytics/dashboard");

export const sendChat = (message: string, history: { role: string; content: string }[] = []) =>
  api.post<ChatResponse>("/chat/", { message, history });

export const parseNatural = (text: string) =>
  api.post<Transaction>("/transactions/parse-natural", { text });

export const getForecast = () => api.get<ForecastData>("/analytics/forecast");
export const getMonthlyHistory = (months = 6) => api.get<{ month: string; label: string; total: number }[]>(`/analytics/monthly-history?months=${months}`);
export const getBriefing = () => api.get<BriefingData>("/ai/briefing");
export const getAnomalies = () => api.get<{ anomalies: Anomaly[]; count: number }>("/ai/anomalies");

export const updateTransaction = (id: number, data: Partial<{ amount: number; category: string; description: string; date: string; tags: string; is_recurring: boolean }>) =>
  api.put<Transaction>(`/transactions/${id}`, data);

export const exportTransactionsCsv = async (params?: Record<string, string>) => {
  const token = await getToken();
  const base = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";
  const p = new URLSearchParams(params);
  if (token) p.set("token", token);
  window.open(`${base}/transactions/export?${p.toString()}`, "_blank");
};

export const getBudgets = () => api.get("/budgets/");
export const createBudget = (data: { category: string; amount: number }) =>
  api.post("/budgets/", data);
export const getBudgetStatus = () => api.get<BudgetStatus[]>("/budgets/status");
export const updateBudget = (id: number, data: { category: string; amount: number }) =>
  api.put(`/budgets/${id}`, data);
export const deleteBudget = (id: number) => api.delete(`/budgets/${id}`);

export default api;
