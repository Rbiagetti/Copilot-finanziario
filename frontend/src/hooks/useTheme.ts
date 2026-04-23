import { useState, useEffect } from "react";

export function useIsDark() {
  const [isDark, setIsDark] = useState(() => localStorage.getItem("theme") !== "light");

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.getAttribute("data-theme") !== "light");
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  return isDark;
}

export function useChartColors() {
  const isDark = useIsDark();
  return {
    tick: isDark ? "rgba(245,222,213,0.95)" : "#6b3100",
    tooltipBg: isDark ? "rgba(22,12,7,0.95)" : "rgba(255,255,255,0.98)",
    tooltipBorder: isDark ? "rgba(255,182,141,0.25)" : "rgba(255,140,66,0.25)",
    tooltipText: isDark ? "#f5ded5" : "#331200",
    tooltipItem: isDark ? "rgba(245,222,213,0.85)" : "#4d2600",
    legendText: isDark ? "rgba(221,193,179,0.85)" : "#763300",
    gridStroke: isDark ? "rgba(255,182,141,0.08)" : "rgba(118,51,0,0.08)",
    cursorFill: isDark ? "rgba(255,140,66,0.07)" : "rgba(255,140,66,0.08)",
    success: "#7dd992",
    warning: "#ffb77d",
    danger: "#ffb4ab",
    neutral: isDark ? "rgba(255,182,141,0.20)" : "rgba(118,51,0,0.14)",
  };
}
