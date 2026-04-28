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

// Gestione errori globali (es. 401 Unauthorized)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      console.warn("Sessione scaduta o non valida. Disconnessione...");
      const { signOut } = await import("../lib/supabase");
      await signOut();
      window.location.reload(); // Forza il reset dell'app allo stato di login
    }
    return Promise.reject(error);
  }
);

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

export interface FullHistoryTransaction {
  id: number;
  amount: number;
  category: string;
  date: string;
  time: string | null;
  account: string;
  tags: string | null;
  is_recurring: boolean;
}

export interface TableData {
  headers: string[];
  rows: (string | number)[][];
}

export interface ReasoningStep {
  phase: string;
  label: string;
  detail: string;
  duration_ms: number;
  status: string;
}

export interface ChatResponse {
  answer: string;
  chart_data: { type: string; data: { name: string; value: number }[]; title: string } | null;
  data_table: TableData | null;
  followup_questions: string[];
  reasoning_steps: ReasoningStep[];
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

export interface AnomalyStats {
  // amount_spike
  mean?: number; median?: number; p75?: number; p90?: number;
  std?: number; z_score?: number; sample_size?: number;
  min?: number; max?: number;
  // new_merchant
  first_seen?: string;
  // frequency_spike
  count_this_week?: number; avg_weekly?: number; ratio?: number;
  // duplicate_suspect
  original_tx_id?: number; original_date?: string;
  original_time?: string; hours_apart?: number;
  // unusual_time
  tx_time?: string; usual_start?: string; usual_end?: string;
  // shared
  category?: string; amount?: number;
}

export interface Anomaly {
  id: number;
  amount: number;
  category: string;
  description: string;
  date: string;
  time: string | null;
  // retrocompatibilità
  z_score: number;
  avg_category: number;
  pct_above_avg: number;
  // nuovi campi
  detection_type: "amount_spike" | "new_merchant" | "frequency_spike" | "duplicate_suspect" | "unusual_time";
  detection_label: string;
  severity: "low" | "medium" | "high";
  stats: AnomalyStats;
}

export interface AnomalyDetail {
  tx: Transaction;
  detection_type: string;
  stats: AnomalyStats;
  context: Array<{ date: string; amount: number; description: string }>;
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
export const getAnomalies = () =>
  api.get<{ anomalies: Anomaly[]; count: number; by_type: Record<string, number>; generated_at: string | null }>("/ai/anomalies");

export const refreshAnomalies = () =>
  api.post<{ anomalies: Anomaly[]; count: number; by_type: Record<string, number>; generated_at: string }>("/ai/anomalies/refresh");

export const getAnomalyDetail = (txId: number, detectionType: string) =>
  api.get<AnomalyDetail>(`/ai/anomalies/${txId}?detection_type=${detectionType}`);
export const getFullHistory = () => api.get<FullHistoryTransaction[]>("/analytics/full-history");

export const updateTransaction = (id: number, data: Partial<{ amount: number; category: string; description: string; date: string; tags: string; is_recurring: boolean }>) =>
  api.put<Transaction>(`/transactions/${id}`, data);

export const exportTransactionsCsv = async (
  params?: Record<string, string>
): Promise<void> => {
  const token = await getToken();
  const base  = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

  const p = new URLSearchParams(params ?? {});
  const url = `${base}/transactions/export?${p.toString()}`;

  const response = await fetch(url, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    throw new Error(`Export fallito: ${response.status}`);
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match       = disposition.match(/filename="?([^";\n]+)"?/);
  const filename    = match?.[1] ?? `fincopilot_${new Date().toISOString().slice(0, 10)}.csv`;

  const blob    = await response.blob();
  const blobUrl = URL.createObjectURL(blob);

  const a    = document.createElement("a");
  a.href     = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
};

export const downloadMonthlyReport = async (year: number, month: number): Promise<void> => {
  const token = await getToken();
  const base  = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";
  const url   = `${base}/report/monthly?year=${year}&month=${month}`;

  const response = await fetch(url, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });

  if (!response.ok) throw new Error(`Report fallito: ${response.status}`);

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match       = disposition.match(/filename="?([^";\n]+)"?/);
  const filename    = match?.[1] ?? `fincopilot_report_${year}_${String(month).padStart(2, "0")}.pdf`;

  const blob    = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  const a       = document.createElement("a");
  a.href        = blobUrl;
  a.download    = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
};

export const generateMonthlyReportWithAnomalies = (year: number, month: number) =>
  api.post<{ status: string; filename: string; size_kb: number; pdf_base64: string }>(
    `/report/monthly/generate?year=${year}&month=${month}`
  );

export const getBudgets = () => api.get("/budgets/");
export const createBudget = (data: { category: string; amount: number }) =>
  api.post("/budgets/", data);
export const getBudgetStatus = () => api.get<BudgetStatus[]>("/budgets/status");
export const updateBudget = (id: number, data: { category: string; amount: number }) =>
  api.put(`/budgets/${id}`, data);
export const deleteBudget = (id: number) => api.delete(`/budgets/${id}`);

export default api;
