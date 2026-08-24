import { useEffect, useState } from "react";
import { Tag, Plus, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { getCategoriesDetailed, createCategory, deleteCategory } from "../../api/client";
import type { CustomCategory } from "../../api/client";
import { CategoryIcon } from "../../lib/categoryIcons";
import { useAppStore } from "../../store/appStore";

export default function CategoryManager() {
  const [standard, setStandard] = useState<string[]>([]);
  const [custom, setCustom] = useState<CustomCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [adding, setAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const refreshAppCategories = useAppStore((s) => s.refreshCategories);

  const load = () => {
    setLoading(true);
    getCategoriesDetailed()
      .then(({ data }) => { setStandard(data.standard); setCustom(data.custom); })
      .catch(() => toast.error("Impossibile caricare le categorie"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setAdding(true);
    try {
      await createCategory(name);
      toast.success(`Categoria "${name}" aggiunta`);
      setNewName("");
      load();
      refreshAppCategories();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || "Errore nella creazione della categoria");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (cat: CustomCategory) => {
    if (!confirm(
      `Eliminare "${cat.name}"? Non apparirà più tra le categorie disponibili per le nuove ` +
      `transazioni. Le transazioni già registrate con questa categoria restano invariate.`
    )) return;
    setDeletingId(cat.id);
    try {
      await deleteCategory(cat.id);
      toast.success(`Categoria "${cat.name}" eliminata`);
      load();
      refreshAppCategories();
    } catch {
      toast.error("Errore nell'eliminazione");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="settings-card">
      <div className="settings-row">
        <div>
          <h3><Tag size={16} className="ai-importer-title-icon" /> Categorie</h3>
          <p className="settings-copy">
            Aggiungi categorie personalizzate oltre alle {standard.length || 10} standard dell'app.
          </p>
        </div>
      </div>

      <form className="category-add-form" onSubmit={handleAdd}>
        <input
          type="text"
          placeholder="es. Animali, Bambini, Regali..."
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          maxLength={30}
          disabled={adding}
        />
        <button type="submit" className="btn-link-google" disabled={adding || !newName.trim()}>
          <Plus size={15} />
          <span>{adding ? "Aggiunta..." : "Aggiungi"}</span>
        </button>
      </form>

      {!loading && (
        <>
          <div className="category-chip-group">
            <span className="category-chip-group-label">Standard</span>
            <div className="category-chip-list">
              {standard.map((c) => (
                <span key={c} className="category-chip category-chip--standard">
                  <CategoryIcon category={c} size={13} />
                  <span className="capitalize">{c}</span>
                </span>
              ))}
            </div>
          </div>

          {custom.length > 0 && (
            <div className="category-chip-group">
              <span className="category-chip-group-label">Personalizzate</span>
              <div className="category-chip-list">
                {custom.map((c) => (
                  <span key={c.id} className="category-chip category-chip--custom">
                    <CategoryIcon category={c.name} size={13} />
                    <span className="capitalize">{c.name}</span>
                    <button
                      type="button"
                      className="category-chip-delete"
                      onClick={() => handleDelete(c)}
                      disabled={deletingId === c.id}
                      aria-label={`Elimina categoria ${c.name}`}
                      title="Elimina"
                    >
                      <Trash2 size={11} />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
