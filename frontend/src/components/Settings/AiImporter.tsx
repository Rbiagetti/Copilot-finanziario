import { useRef, useState } from "react";
import { UploadCloud, FileSpreadsheet, Sparkles, CheckCircle2, X } from "lucide-react";
import toast from "react-hot-toast";
import { previewImport, commitImport } from "../../api/client";
import type { ImportPreviewResponse, ImportCommitResponse } from "../../api/client";
import { useAppStore } from "../../store/appStore";

const FIELD_LABELS: Record<string, string> = {
  date: "Data",
  amount: "Importo",
  description: "Descrizione",
  category: "Categoria",
  account: "Conto",
};

type Step = "idle" | "loading-preview" | "mapping" | "importing" | "done";

export default function AiImporter() {
  const [step, setStep] = useState<Step>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [result, setResult] = useState<ImportCommitResponse | null>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const invalidateDashboardCache = useAppStore((s) => s.invalidateDashboardCache);
  const markTransactionsAsNew = useAppStore((s) => s.markTransactionsAsNew);

  const reset = () => {
    setStep("idle");
    setFile(null);
    setPreview(null);
    setMapping({});
    setResult(null);
    setError("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleFile = async (f: File) => {
    setError("");
    setFile(f);
    setStep("loading-preview");
    try {
      const { data } = await previewImport(f);
      setPreview(data);
      setMapping(data.suggested_mapping);
      setStep("mapping");
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "Impossibile leggere il file.";
      setError(msg);
      setStep("idle");
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  };

  const missingRequired = preview?.required_fields.filter((f) => !mapping[f]) ?? [];

  const handleConfirm = async () => {
    if (!file || missingRequired.length > 0) return;
    setStep("importing");
    setError("");
    try {
      const { data } = await commitImport(file, mapping);
      setResult(data);
      setStep("done");
      if (data.imported > 0) {
        toast.success(`${data.imported} spese importate`);
        invalidateDashboardCache();
        markTransactionsAsNew();
      }
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "Import fallito.";
      setError(msg);
      setStep("mapping");
    }
  };

  return (
    <div className="settings-card ai-importer">
      <div className="settings-row">
        <div>
          <h3><Sparkles size={16} className="ai-importer-title-icon" /> AI Importer</h3>
          <p className="settings-copy">
            Carica un estratto conto (CSV, Excel o PDF): l'AI riconosce le colonne e categorizza le spese.
          </p>
        </div>
      </div>

      {step === "idle" && (
        <div
          className="ai-importer-dropzone"
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
        >
          <UploadCloud size={28} />
          <p>Trascina qui il file, o clicca per selezionarlo</p>
          <span className="ai-importer-hint">CSV, Excel o PDF (estratto conto), max 5MB</span>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx,.xls,.pdf"
            hidden
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
          />
        </div>
      )}

      {error && <p className="login-error ai-importer-error">{error}</p>}

      {step === "loading-preview" && (
        <div className="ai-importer-status">
          <Sparkles size={18} className="ai-importer-spin" />
          <span>Analisi del file in corso...</span>
        </div>
      )}

      {step === "mapping" && preview && (
        <div className="ai-importer-mapping">
          <div className="ai-importer-file-row">
            <FileSpreadsheet size={16} />
            <span>{file?.name}</span>
            <span className="ai-importer-hint">{preview.total_rows} righe rilevate</span>
            <button type="button" className="ai-importer-close" onClick={reset} aria-label="Annulla">
              <X size={16} />
            </button>
          </div>

          <p className="settings-copy">
            Abbina le colonne del file ai campi di FinCopilot (proposta AI già applicata, correggila se serve):
          </p>

          <div className="ai-importer-fields">
            {preview.target_fields.map((field) => (
              <div className="ai-importer-field" key={field}>
                <label>
                  {FIELD_LABELS[field] ?? field}
                  {preview.required_fields.includes(field) && <span className="ai-importer-required">*</span>}
                </label>
                <select
                  value={mapping[field] ?? ""}
                  onChange={(e) => setMapping((m) => ({ ...m, [field]: e.target.value || null }))}
                >
                  <option value="">— non mappato —</option>
                  {preview.columns.map((col) => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>

          <div className="ai-importer-preview-table-wrap">
            <table className="ai-importer-preview-table">
              <thead>
                <tr>{preview.columns.map((c) => <th key={c}>{c}</th>)}</tr>
              </thead>
              <tbody>
                {preview.preview_rows.slice(0, 5).map((row, i) => (
                  <tr key={i}>
                    {preview.columns.map((c) => <td key={c}>{row[c]}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {missingRequired.length > 0 && (
            <p className="ai-importer-hint ai-importer-warning">
              Manca il mapping di: {missingRequired.map((f) => FIELD_LABELS[f] ?? f).join(", ")}
            </p>
          )}

          <div className="ai-importer-actions">
            <button type="button" className="btn-logout" onClick={reset}>Annulla</button>
            <button
              type="button"
              className="btn-link-google"
              onClick={handleConfirm}
              disabled={missingRequired.length > 0}
            >
              Importa {preview.total_rows} righe
            </button>
          </div>
        </div>
      )}

      {step === "importing" && (
        <div className="ai-importer-status">
          <Sparkles size={18} className="ai-importer-spin" />
          <span>Categorizzazione con AI e importazione in corso...</span>
        </div>
      )}

      {step === "done" && result && (
        <div className="ai-importer-result">
          <div className="ai-importer-result-row">
            <CheckCircle2 size={18} className="ai-importer-result-icon-ok" />
            <span><strong>{result.imported}</strong> spese importate</span>
          </div>
          {result.skipped_duplicates > 0 && (
            <p className="settings-copy">{result.skipped_duplicates} righe scartate perché già presenti (duplicati).</p>
          )}
          {result.skipped_income > 0 && (
            <p className="settings-copy">{result.skipped_income} righe scartate perché entrate (importo positivo), non spese.</p>
          )}
          {result.invalid_rows > 0 && (
            <p className="settings-copy">{result.invalid_rows} righe scartate: data o importo non riconosciuti.</p>
          )}
          <div className="ai-importer-actions">
            <button type="button" className="btn-link-google" onClick={reset}>Importa un altro file</button>
          </div>
        </div>
      )}
    </div>
  );
}
