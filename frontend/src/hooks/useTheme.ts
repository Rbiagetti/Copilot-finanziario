// App solo tema scuro (predisposizione al tema chiaro rimossa: mai stata esposta
// all'utente, nessuna regola CSS la implementava). Colori fissi per i grafici Recharts,
// che non possono leggere le CSS custom properties (renderizzano SVG con props inline).
export function useChartColors() {
  return {
    tick: "#fff3e6",
    tooltipBg: "rgba(22,12,7,0.95)",
    tooltipBorder: "rgba(255,182,141,0.25)",
    tooltipText: "#f5ded5",
    tooltipItem: "rgba(245,222,213,0.85)",
    legendText: "#fff3e6",
    gridStroke: "rgba(255,182,141,0.08)",
    cursorFill: "rgba(255,140,66,0.07)",
    success: "#7dd992",
    warning: "#ffb77d",
    danger: "#ffb4ab",
    neutral: "rgba(255,182,141,0.20)",
  };
}
