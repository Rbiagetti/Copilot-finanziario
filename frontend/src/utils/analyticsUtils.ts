import type { FullHistoryTransaction } from "../api/client";

export type GroupBy = "day" | "month";

/**
 * Trend Data — supporta raggruppamento per giorno o mese
 */
export const getMonthlyTrend = (transactions: FullHistoryTransaction[], groupBy: GroupBy = "month") => {
  const buckets: Record<string, { total: number; count: number; label: string }> = {};

  transactions.forEach(t => {
    const d = new Date(t.date);
    let key: string;
    let label: string;
    if (groupBy === "day") {
      key = t.date; // YYYY-MM-DD
      label = d.toLocaleDateString('it-IT', { day: '2-digit', month: 'short' });
    } else {
      key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      label = d.toLocaleDateString('it-IT', { month: 'short', year: 'numeric' });
    }
    if (!buckets[key]) buckets[key] = { total: 0, count: 0, label };
    buckets[key].total += t.amount;
    buckets[key].count += 1;
  });

  return Object.entries(buckets)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, val]) => {
      const avgDivisor = groupBy === "day"
        ? 1
        : new Date(parseInt(key.split('-')[0]), parseInt(key.split('-')[1]), 0).getDate();
      return {
        month: key,
        label: val.label,
        total: parseFloat(val.total.toFixed(2)),
        count: val.count,
        avg_daily: parseFloat((val.total / avgDivisor).toFixed(2))
      };
    });
};

/**
 * Category Data (for Donut)
 */
export const getCategoryData = (transactions: FullHistoryTransaction[]) => {
  const categories: Record<string, { total: number; count: number }> = {};
  let grandTotal = 0;

  transactions.forEach(t => {
    if (!categories[t.category]) categories[t.category] = { total: 0, count: 0 };
    categories[t.category].total += t.amount;
    categories[t.category].count += 1;
    grandTotal += t.amount;
  });

  return Object.entries(categories)
    .map(([name, val]) => ({
      name,
      value: parseFloat(val.total.toFixed(2)),
      count: val.count,
      percentage: grandTotal > 0 ? parseFloat(((val.total / grandTotal) * 100).toFixed(1)) : 0
    }))
    .sort((a, b) => b.value - a.value);
};

/**
 * Calendar Heatmap Data
 */
export const getCalendarData = (transactions: FullHistoryTransaction[]) => {
  const days: Record<string, { total: number; count: number }> = {};
  transactions.forEach(t => {
    if (!days[t.date]) days[t.date] = { total: 0, count: 0 };
    days[t.date].total += t.amount;
    days[t.date].count += 1;
  });

  return Object.entries(days).map(([date, val]) => ({
    date,
    total: parseFloat(val.total.toFixed(2)),
    count: val.count
  }));
};

/**
 * Category Volatility (StdDev / Mean)
 */
export const getCategoryVolatility = (transactions: FullHistoryTransaction[]) => {
  const catMonthly: Record<string, Record<string, number>> = {};
  
  transactions.forEach(t => {
    const d = new Date(t.date);
    const monthKey = `${d.getFullYear()}-${d.getMonth()}`;
    if (!catMonthly[t.category]) catMonthly[t.category] = {};
    catMonthly[t.category][monthKey] = (catMonthly[t.category][monthKey] || 0) + t.amount;
  });

  return Object.entries(catMonthly).map(([category, monthlyData]) => {
    const values = Object.values(monthlyData);
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const stdDev = Math.sqrt(values.reduce((sq, n) => sq + Math.pow(n - mean, 2), 0) / values.length);
    
    return {
      category,
      mean: parseFloat(mean.toFixed(2)),
      stdDev: parseFloat(stdDev.toFixed(2)),
      volatility: mean > 0 ? parseFloat((stdDev / mean).toFixed(2)) : 0,
      history: Object.entries(monthlyData)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([month, total]) => ({ month, total: parseFloat(total.toFixed(2)) }))
    };
  }).sort((a, b) => b.mean - a.mean);
};

/**
 * Recurring vs Variable — supporta raggruppamento per giorno o mese
 */
export const getRecurringData = (transactions: FullHistoryTransaction[], groupBy: GroupBy = "month") => {
  const buckets: Record<string, { recurring: number; variable: number; label: string }> = {};

  transactions.forEach(t => {
    const d = new Date(t.date);
    let key: string;
    let label: string;
    if (groupBy === "day") {
      key = t.date;
      label = d.toLocaleDateString('it-IT', { day: '2-digit', month: 'short' });
    } else {
      key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      label = d.toLocaleDateString('it-IT', { month: 'short', year: 'numeric' });
    }
    if (!buckets[key]) {
      buckets[key] = { recurring: 0, variable: 0, label };
    }
    if (t.is_recurring) {
      buckets[key].recurring += t.amount;
    } else {
      buckets[key].variable += t.amount;
    }
  });

  return Object.entries(buckets)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, val]) => ({
      month: key,
      label: val.label,
      recurring: parseFloat(val.recurring.toFixed(2)),
      variable: parseFloat(val.variable.toFixed(2)),
      ratio: val.variable > 0 ? parseFloat((val.recurring / val.variable).toFixed(2)) : 0
    }));
};

/**
 * Time-of-Day / Weekday Heatmap
 */
export const getTimeOfDayData = (transactions: FullHistoryTransaction[]) => {
  const heat: Record<string, { total: number; count: number }> = {};
  const weekdays = ["Dom", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab"];

  transactions.forEach(t => {
    const timeStr = t.time || "12:00"; // skip se no time
    const hour = parseInt(timeStr.split(':')[0]);
    const day = new Date(t.date).getDay();
    const key = `${day}-${hour}`;

    if (!heat[key]) heat[key] = { total: 0, count: 0 };
    heat[key].total += t.amount;
    heat[key].count += 1;
  });

  const data: any[] = [];
  for (let d = 0; d < 7; d++) {
    for (let h = 0; h < 24; h++) {
      const key = `${d}-${h}`;
      data.push({
        day: weekdays[d],
        dayIdx: d,
        hour: h,
        total: heat[key] ? parseFloat(heat[key].total.toFixed(2)) : 0,
        count: heat[key] ? heat[key].count : 0
      });
    }
  }
  return data;
};
