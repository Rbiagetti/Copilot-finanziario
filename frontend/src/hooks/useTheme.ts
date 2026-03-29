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
    tick: isDark ? "rgba(160,190,230,0.55)" : "#555",
    tooltipBg: isDark ? "rgba(8,20,40,0.95)" : "rgba(255,255,255,0.98)",
    tooltipBorder: isDark ? "rgba(255,255,255,0.1)" : "rgba(79,142,247,0.2)",
    tooltipText: isDark ? "#f0f8ff" : "#0a1628",
    tooltipItem: isDark ? "rgba(240,248,255,0.75)" : "#334",
    legendText: isDark ? "rgba(160,190,230,0.8)" : "#444",
    gridStroke: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.06)",
    cursorFill: isDark ? "rgba(255,255,255,0.04)" : "rgba(79,142,247,0.06)",
    success: "#10b981",
    warning: "#f59e0b",
    danger: "#f43f5e",
    neutral: isDark ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.1)",
  };
}
