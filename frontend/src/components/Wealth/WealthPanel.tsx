import { useCallback, useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Archive,
  Check,
  Landmark,
  Pencil,
  Plus,
  RefreshCw,
  X,
} from "lucide-react";
import toast from "react-hot-toast";
import {
  createWealthAccount,
  deleteWealthAccount,
  getWealthAccounts,
  getWealthOverview,
  getWealthSnapshot,
  saveWealthSnapshot,
  updateWealthAccount,
} from "../../api/client";
import type { WealthAccount, WealthKind, WealthOverview } from "../../api/client";
import { useChartColors } from "../../hooks/useTheme";
import { confirmAction } from "../../lib/confirmDialog";

const KIND_LABELS: Record<WealthKind, string> = {
  liquidita: "Liquidità",
  investimenti: "Investimenti",
  previdenza: "Previdenza",
  immobili: "Immobili",
  altro: "Altro",
};

const KINDS = Object.keys(KIND_LABELS) as WealthKind[];

const eur = (value: number, decimals = 2) =>
  new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);

const eurCompact = (value: number) =>
  new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);

const todayISO = () => {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
};

const monthLabel = (iso: string) => {
  const [year, month] = iso.split("-").map(Number);
  if (!year || !month) return iso;
  return new Intl.DateTimeFormat("it-IT", {
    month: "short",
    year: "2-digit",
  }).format(new Date(year, month - 1, 1));
};

const errorDetail = (err: unknown): string | undefined => {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response
    ?.data?.detail;
  return typeof detail === "string" ? detail : undefined;
};

export default function WealthPanel() {
  const colors = useChartColors();

  const [overview, setOverview] = useState<WealthOverview | null>(null);
  const [accounts, setAccounts] = useState<WealthAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [formDate, setFormDate] = useState(todayISO());
  const [formEntries, setFormEntries] = useState<Record<number, string>>({});
  const [formLoading, setFormLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const [newName, setNewName] = useState("");
  const [newKind, setNewKind] = useState<WealthKind>("liquidita");
  const [adding, setAdding] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editKind, setEditKind] = useState<WealthKind>("liquidita");

  const load = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [overviewResponse, accountsResponse] = await Promise.all([
        getWealthOverview(12),
        getWealthAccounts(),
      ]);
      setOverview(overviewResponse.data);
      setAccounts(accountsResponse.data);
    } catch {
      setErrorMsg(
        "Impossibile caricare il patrimonio. Controlla la connessione e riprova."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const loadSnapshot = useCallback(async (day: string) => {
    setFormLoading(true);
    try {
      const { data } = await getWealthSnapshot(day);
      const entries: Record<number, string> = {};
      data.accounts.forEach((account) => {
        entries[account.account_id] =
          account.balance === null ? "" : String(account.balance);
      });
      setFormEntries(entries);
    } catch {
      toast.error("Impossibile caricare i saldi di quella data");
    } finally {
      setFormLoading(false);
    }
  }, []);

  const openForm = async () => {
    const day = todayISO();
    setFormDate(day);
    setFormOpen(true);
    await loadSnapshot(day);
  };

  const handleDateChange = async (value: string) => {
    setFormDate(value);
    if (value) await loadSnapshot(value);
  };

  const handleSave = async () => {
    const entries = accounts
      .map((account) => ({
        account_id: account.id,
        raw: formEntries[account.id],
      }))
      .filter((entry) => entry.raw !== undefined && entry.raw.trim() !== "")
      .map((entry) => ({
        account_id: entry.account_id,
        balance: Number(entry.raw.replace(",", ".")),
      }))
      .filter((entry) => Number.isFinite(entry.balance) && entry.balance >= 0);

    if (entries.length === 0) {
      toast.error("Inserisci almeno un saldo");
      return;
    }

    setSaving(true);
    try {
      const { data } = await saveWealthSnapshot(formDate, entries);
      toast.success(
        data.saved === 1 ? "Salvato 1 saldo" : `Salvati ${data.saved} saldi`
      );
      setFormOpen(false);
      await load();
    } catch (err) {
      toast.error(errorDetail(err) || "Errore nel salvataggio");
    } finally {
      setSaving(false);
    }
  };

  const handleAdd = async (event: React.FormEvent) => {
    event.preventDefault();
    const name = newName.trim();
    if (!name) return;

    setAdding(true);
    try {
      await createWealthAccount({ name, kind: newKind });
      toast.success(`Conto ${name} aggiunto`);
      setNewName("");
      await load();
      if (formOpen) await loadSnapshot(formDate);
    } catch (err) {
      toast.error(errorDetail(err) || "Errore nell'aggiunta del conto");
    } finally {
      setAdding(false);
    }
  };

  const startEdit = (account: WealthAccount) => {
    setEditingId(account.id);
    setEditName(account.name);
    setEditKind(account.kind);
  };

  const saveEdit = async () => {
    if (editingId === null) return;
    const name = editName.trim();
    if (!name) {
      toast.error("Il nome non può essere vuoto");
      return;
    }
    try {
      await updateWealthAccount(editingId, { name, kind: editKind });
      toast.success("Conto aggiornato");
      setEditingId(null);
      await load();
    } catch (err) {
      toast.error(errorDetail(err) || "Errore nell'aggiornamento");
    }
  };

  const handleArchive = async (account: WealthAccount) => {
    const confirmed = await confirmAction({
      title: "Archivia conto",
      message: `Archiviare "${account.name}"? Non sarà più conteggiato nel patrimonio.`,
      confirmLabel: "Archivia",
      danger: true,
    });
    if (!confirmed) return;

    try {
      await deleteWealthAccount(account.id);
      toast.success("Conto archiviato");
      await load();
    } catch {
      toast.error("Errore nell'archiviazione");
    }
  };

  const total = overview?.current?.total ?? 0;
  const delta = overview?.delta ?? null;
  const deltaPct = overview?.delta_pct ?? null;
  const lastDate = overview?.current?.date ?? null;

  return (
    <div className="wealth-page animate-in">
      <div className="wealth-head">
        <div>
          <h2>Patrimonio</h2>
          <p className="wealth-sub">
            Foto periodiche dei tuoi conti. Solo attività, nessun debito.
          </p>
        </div>
        <button
          className="btn-primary wealth-update-btn"
          onClick={openForm}
          disabled={accounts.length === 0}
        >
          <RefreshCw size={15} /> Aggiorna saldi
        </button>
      </div>

      {loading ? (
        <div className="loading">
          <span className="glyph-dot" />
        </div>
      ) : errorMsg ? (
        <div className="error wealth-error">
          <p>{errorMsg}</p>
          <button className="btn-primary" onClick={load}>
            Riprova
          </button>
        </div>
      ) : (
        <>
          <div className="wealth-kpi">
            <div className="wealth-kpi-card">
              <span className="wealth-kpi-label">Patrimonio totale</span>
              <span className="wealth-kpi-value">{eur(total, 0)}</span>
              <span className="wealth-kpi-hint">
                {lastDate ? `foto del ${lastDate}` : "nessuna foto salvata"}
              </span>
            </div>
            <div className="wealth-kpi-card">
              <span className="wealth-kpi-label">Variazione</span>
              <span
                className={`wealth-kpi-value ${
                  delta === null ? "" : delta >= 0 ? "up" : "down"
                }`}
              >
                {delta === null
                  ? "—"
                  : `${delta >= 0 ? "+" : ""}${eur(delta, 0)}`}
              </span>
              <span className="wealth-kpi-hint">
                {deltaPct === null
                  ? "servono almeno due foto"
                  : `${deltaPct >= 0 ? "+" : ""}${deltaPct}% vs foto precedente`}
              </span>
            </div>
            <div className="wealth-kpi-card">
              <span className="wealth-kpi-label">Conti attivi</span>
              <span className="wealth-kpi-value">{accounts.length}</span>
              <span className="wealth-kpi-hint">
                {overview?.composition.length
                  ? `${overview.composition.length} tipi di attività`
                  : "aggiungi il primo conto"}
              </span>
            </div>
          </div>

          <div className="wealth-card">
            <div className="wealth-card-head">
              <h3>Andamento</h3>
              <span className="wealth-muted">
                {overview?.series.length
                  ? `${overview.series.length} foto`
                  : "nessun dato"}
              </span>
            </div>
            {overview && overview.series.length > 0 ? (
              <div className="wealth-chart">
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart
                    data={overview.series}
                    margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid
                      stroke={colors.gridStroke}
                      vertical={false}
                    />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(value) => monthLabel(String(value))}
                      tick={{
                        fill: colors.tick,
                        fontSize: 10,
                        fontFamily: "var(--font-mono)",
                      }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tickFormatter={(value) => eurCompact(Number(value))}
                      tick={{
                        fill: colors.tick,
                        fontSize: 10,
                        fontFamily: "var(--font-mono)",
                      }}
                      axisLine={false}
                      tickLine={false}
                      width={72}
                    />
                    <Tooltip
                      contentStyle={{
                        background: colors.tooltipBg,
                        border: `1px solid ${colors.tooltipBorder}`,
                        borderRadius: 0,
                        fontSize: 12,
                        fontFamily: "var(--font-mono)",
                      }}
                      labelFormatter={(value) => monthLabel(String(value))}
                      formatter={(value) => [
                        eur(Number(value), 0),
                        "Patrimonio",
                      ]}
                      itemStyle={{ color: colors.tooltipText }}
                    />
                    <Line
                      type="monotone"
                      dataKey="total"
                      stroke={colors.tooltipText}
                      strokeWidth={1.5}
                      dot={{ r: 2, fill: colors.tooltipText }}
                      activeDot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="wealth-muted wealth-chart-empty">
                Salva la prima foto per vedere l'andamento.
              </p>
            )}
          </div>

          {overview && overview.composition.length > 0 && (
            <div className="wealth-card">
              <div className="wealth-card-head">
                <h3>Composizione</h3>
                <span className="wealth-muted">{eur(total, 0)}</span>
              </div>
              <div className="wealth-composition">
                {overview.composition.map((row) => (
                  <div key={row.kind} className="wealth-comp-row">
                    <span className="wealth-comp-label">
                      {KIND_LABELS[row.kind] ?? row.kind}
                    </span>
                    <div className="wealth-comp-bar">
                      <div style={{ width: `${row.pct}%` }} />
                    </div>
                    <span className="wealth-comp-value">
                      {eur(row.total, 0)}
                    </span>
                    <span className="wealth-comp-pct">{row.pct}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {formOpen && (
            <div className="wealth-card wealth-form-card">
              <div className="wealth-card-head">
                <h3>Aggiorna saldi</h3>
                <button
                  type="button"
                  className="btn-icon"
                  onClick={() => setFormOpen(false)}
                  aria-label="Chiudi"
                >
                  <X size={14} />
                </button>
              </div>

              <label className="wealth-date-row">
                <span>Data della foto</span>
                <input
                  type="date"
                  value={formDate}
                  max={todayISO()}
                  onChange={(event) => handleDateChange(event.target.value)}
                />
              </label>

              {accounts.length === 0 ? (
                <p className="wealth-muted">
                  Aggiungi prima un conto, qui sotto.
                </p>
              ) : formLoading ? (
                <div className="loading">
                  <span className="glyph-dot" />
                </div>
              ) : (
                <div className="wealth-form-rows">
                  {accounts.map((account) => (
                    <label key={account.id} className="wealth-form-row">
                      <span className="wealth-form-name">
                        {account.name}
                        <small>{KIND_LABELS[account.kind]}</small>
                      </span>
                      <span className="wealth-input-wrap">
                        <span aria-hidden="true">€</span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          inputMode="decimal"
                          placeholder="0"
                          value={formEntries[account.id] ?? ""}
                          onChange={(event) =>
                            setFormEntries((previous) => ({
                              ...previous,
                              [account.id]: event.target.value,
                            }))
                          }
                        />
                      </span>
                    </label>
                  ))}
                </div>
              )}

              <div className="wealth-form-actions">
                <button
                  className="btn-primary"
                  onClick={handleSave}
                  disabled={saving || formLoading || accounts.length === 0}
                >
                  {saving ? "Salvataggio..." : "Salva foto"}
                </button>
              </div>
            </div>
          )}

          <div className="wealth-card">
            <div className="wealth-card-head">
              <h3>Conti</h3>
              <span className="wealth-muted">
                <Landmark size={13} /> {accounts.length}
              </span>
            </div>

            {accounts.length === 0 ? (
              <p className="wealth-muted">
                Nessun conto. Aggiungine uno qui sotto per iniziare.
              </p>
            ) : (
              <div className="wealth-account-list">
                {accounts.map((account) => {
                  const row = overview?.accounts.find(
                    (item) => item.id === account.id
                  );

                  if (editingId === account.id) {
                    return (
                      <div
                        key={account.id}
                        className="wealth-account-row wealth-account-row--editing"
                      >
                        <input
                          className="wealth-account-name-input"
                          value={editName}
                          maxLength={40}
                          onChange={(event) => setEditName(event.target.value)}
                        />
                        <select
                          className="wealth-kind-select"
                          value={editKind}
                          onChange={(event) =>
                            setEditKind(event.target.value as WealthKind)
                          }
                        >
                          {KINDS.map((kind) => (
                            <option key={kind} value={kind}>
                              {KIND_LABELS[kind]}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="btn-icon"
                          onClick={saveEdit}
                          aria-label="Salva"
                        >
                          <Check size={14} />
                        </button>
                        <button
                          type="button"
                          className="btn-icon"
                          onClick={() => setEditingId(null)}
                          aria-label="Annulla"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    );
                  }

                  return (
                    <div key={account.id} className="wealth-account-row">
                      <div className="wealth-account-main">
                        <span className="wealth-account-name">
                          {account.name}
                        </span>
                        <span className="wealth-kind">
                          {KIND_LABELS[account.kind]}
                        </span>
                      </div>
                      <div className="wealth-account-numbers">
                        <span className="wealth-account-balance">
                          {row && row.last_date ? eur(row.balance) : "—"}
                        </span>
                        <span
                          className={`wealth-account-delta ${
                            row?.delta == null
                              ? ""
                              : row.delta >= 0
                                ? "up"
                                : "down"
                          }`}
                        >
                          {row?.delta == null
                            ? "nessuna variazione"
                            : `${row.delta >= 0 ? "+" : ""}${eur(row.delta)}`}
                        </span>
                      </div>
                      <div className="wealth-account-actions">
                        <button
                          type="button"
                          className="btn-icon"
                          onClick={() => startEdit(account)}
                          aria-label={`Rinomina ${account.name}`}
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          type="button"
                          className="btn-icon danger"
                          onClick={() => handleArchive(account)}
                          aria-label={`Archivia ${account.name}`}
                        >
                          <Archive size={14} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <form className="wealth-add-form" onSubmit={handleAdd}>
              <input
                placeholder="Nome conto (es. MPS)"
                value={newName}
                maxLength={40}
                onChange={(event) => setNewName(event.target.value)}
              />
              <select
                value={newKind}
                onChange={(event) =>
                  setNewKind(event.target.value as WealthKind)
                }
              >
                {KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {KIND_LABELS[kind]}
                  </option>
                ))}
              </select>
              <button
                type="submit"
                className="btn-primary"
                disabled={adding || !newName.trim()}
              >
                <Plus size={15} /> {adding ? "Aggiunta..." : "Aggiungi"}
              </button>
            </form>
          </div>
        </>
      )}
    </div>
  );
}
