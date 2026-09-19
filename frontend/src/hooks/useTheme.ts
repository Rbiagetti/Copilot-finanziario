// App solo tema scuro (predisposizione al tema chiaro rimossa: mai stata esposta
// all'utente, nessuna regola CSS la implementava). Colori fissi per i grafici Recharts,
// che non possono leggere le CSS custom properties (renderizzano SVG con props inline).
export function useChartColors() {
  return {
    tick: "#7a7a7a",
    tooltipBg: "#0a0a0a",
    tooltipBorder: "rgba(255,255,255,0.12)",
    tooltipText: "#ffffff",
    tooltipItem: "#b3b3b3",
    legendText: "#b3b3b3",
    gridStroke: "rgba(255,255,255,0.06)",
    cursorFill: "rgba(255,255,255,0.05)",
    success: "#34c759",
    warning: "#ff9f0a",
    danger: "#ff3b30",
    neutral: "rgba(255,255,255,0.2)",
  };
}
