import { useEffect, useState } from "react";
import { Cpu, AlertTriangle, Check } from "lucide-react";
import toast from "react-hot-toast";
import { getAiModelSettings, updateAiModelSettings } from "../../api/client";
import type { AiModelSettings as AiModelSettingsData } from "../../api/client";

export default function AiModelSettings() {
  const [data, setData] = useState<AiModelSettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null); // id del modello in salvataggio

  const load = () => {
    setLoading(true);
    getAiModelSettings()
      .then(({ data }) => setData(data))
      .catch(() => toast.error("Impossibile caricare le impostazioni del modello AI"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleSelect = async (model: string) => {
    if (!data || model === data.current || saving) return;
    setSaving(model);
    try {
      await updateAiModelSettings(model);
      setData({ ...data, current: model, current_is_valid: true });
      toast.success(`Modello AI aggiornato a "${data.available.find(m => m.id === model)?.label ?? model}"`);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || "Errore nell'aggiornamento del modello");
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="settings-card">
      <div className="settings-row">
        <div>
          <h3><Cpu size={16} className="ai-importer-title-icon" /> Modello AI</h3>
          <p className="settings-copy">
            Scegli quale modello usa FinCopilot per parsing, chat, report e categorizzazione automatica.
            Riguarda solo il tuo account.
          </p>
        </div>
      </div>

      {!loading && data && data.current_is_valid === false && (
        <div className="ai-model-warning">
          <AlertTriangle size={15} />
          <span>
            Il modello selezionato ("{data.current}") non è più disponibile — scegline uno qui sotto.
          </span>
        </div>
      )}

      {loading && <p className="settings-copy" style={{ marginTop: "0.75rem" }}>Caricamento...</p>}

      {!loading && data && (
        <div className="ai-model-list">
          {data.available.map((m) => {
            const active = m.id === data.current;
            const isSaving = saving === m.id;
            return (
              <button
                key={m.id}
                type="button"
                className={`ai-model-option${active ? " ai-model-option--active" : ""}`}
                onClick={() => handleSelect(m.id)}
                disabled={saving !== null}
                aria-pressed={active}
              >
                <span className="ai-model-option-radio" aria-hidden="true">
                  {active && <Check size={12} />}
                </span>
                <span className="ai-model-option-text">
                  <span className="ai-model-option-title">
                    {m.label}
                    {m.id === data.default && <span className="ai-model-option-badge">Default</span>}
                  </span>
                  {m.description && <span className="ai-model-option-desc">{m.description}</span>}
                </span>
                {isSaving && <span className="ai-model-option-status">Salvataggio...</span>}
              </button>
            );
          })}
          {data.available.length === 0 && (
            <p className="settings-copy">Nessun modello disponibile al momento — riprova più tardi.</p>
          )}
        </div>
      )}
    </div>
  );
}
