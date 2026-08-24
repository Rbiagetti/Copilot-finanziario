import { useState } from "react";
import { FileDown, RefreshCw } from "lucide-react";
import toast from "react-hot-toast";
import { generateMonthlyReport } from "../../api/client";

const MESI = [
  "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
  "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
];

const today = new Date();
const DEFAULT_MONTH = today.getMonth() === 0 ? 12 : today.getMonth();
const DEFAULT_YEAR  = today.getMonth() === 0 ? today.getFullYear() - 1 : today.getFullYear();
const YEARS = Array.from({ length: 3 }, (_, i) => today.getFullYear() - i);

export default function MonthlyReport() {
  const [month, setMonth]     = useState(DEFAULT_MONTH);
  const [year, setYear]       = useState(DEFAULT_YEAR);
  const [loading, setLoading] = useState(false);
  const [status, setStatus]   = useState<string | null>(null);

  const handleDownload = async () => {
    setLoading(true);
    setStatus(null);

    try {
      setStatus("Generazione PDF in corso...");

      const res = await generateMonthlyReport(year, month);

      // Scarica il PDF da base64
      const pdfBytes = Uint8Array.from(atob(res.data.pdf_base64), (c) => c.charCodeAt(0));
      const blob = new Blob([pdfBytes], { type: "application/pdf" });
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = res.data.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);

      setStatus(null);
      toast.success(`Report ${MESI[month - 1]} ${year} scaricato`);
    } catch (err) {
      setStatus(null);
      toast.error(err instanceof Error ? err.message : "Errore nella generazione del report");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="settings-card">
      <div className="settings-row" style={{ flexWrap: "wrap", gap: "1rem" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <h3>Report Mensile PDF</h3>
          <p className="settings-copy">
            Scarica il riepilogo completo del mese selezionato: spese per categoria,
            top transazioni, budget e analisi AI.
          </p>
        </div>
      </div>

      <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap", marginTop: "0.75rem" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <label style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Mese</label>
          <select
            value={month}
            onChange={e => setMonth(Number(e.target.value))}
            className="report-select"
            disabled={loading}
          >
            {MESI.map((m, i) => (
              <option key={i + 1} value={i + 1}>{m}</option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <label style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Anno</label>
          <select
            value={year}
            onChange={e => setYear(Number(e.target.value))}
            className="report-select"
            disabled={loading}
          >
            {YEARS.map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <label style={{ fontSize: "0.75rem", color: "transparent" }}>—</label>
          <button
            className="btn-primary"
            onClick={handleDownload}
            disabled={loading}
            style={{ display: "flex", alignItems: "center", gap: "0.5rem", width: "auto", padding: "0.5rem 1.25rem" }}
          >
            {loading
              ? <><RefreshCw size={15} className="spin" /> {status || "Generazione..."}</>
              : <><FileDown size={15} /> Genera PDF</>
            }
          </button>
        </div>
      </div>

      {loading && status && (
        <p style={{ fontSize: "0.78rem", color: "var(--text-dim)", marginTop: "0.5rem" }}>
          {status}
        </p>
      )}
    </div>
  );
}
