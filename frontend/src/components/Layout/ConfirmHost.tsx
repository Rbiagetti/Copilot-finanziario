import { useEffect, useRef } from "react";
import { useConfirmStore, settleConfirm } from "../../lib/confirmDialog";

export default function ConfirmHost() {
  const options = useConfirmStore((s) => s.options);
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!options) return;
    // Focus su "Annulla": un Invio accidentale non deve confermare un'eliminazione.
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") settleConfirm(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [options]);

  if (!options) return null;
  const { title, message, confirmLabel = "Conferma", cancelLabel = "Annulla", danger } = options;

  return (
    <div className="modal-overlay" onClick={() => settleConfirm(false)}>
      <div
        className="modal-box confirm-box"
        role="alertdialog"
        aria-modal="true"
        aria-label={title ?? message}
        onClick={(e) => e.stopPropagation()}
      >
        {title && <h3 className="confirm-title">{title}</h3>}
        <p className="confirm-message">{message}</p>
        <div className="confirm-actions">
          <button ref={cancelRef} type="button" className="confirm-btn" onClick={() => settleConfirm(false)}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`confirm-btn ${danger ? "confirm-btn--danger" : "confirm-btn--primary"}`}
            onClick={() => settleConfirm(true)}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
