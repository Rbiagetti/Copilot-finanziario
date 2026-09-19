import { create } from "zustand";

export interface ConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

interface ConfirmState {
  options: ConfirmOptions | null;
  resolve: ((value: boolean) => void) | null;
}

export const useConfirmStore = create<ConfirmState>(() => ({ options: null, resolve: null }));

// Sostituto di window.confirm(): stessa forma d'uso (`if (!(await confirmAction(...))) return;`),
// ma disegnato dall'app. La finestra nativa del browser non è stilabile.
export function confirmAction(options: ConfirmOptions): Promise<boolean> {
  useConfirmStore.getState().resolve?.(false); // un solo dialog alla volta
  return new Promise<boolean>((resolve) => {
    useConfirmStore.setState({ options, resolve });
  });
}

export function settleConfirm(value: boolean) {
  const { resolve } = useConfirmStore.getState();
  useConfirmStore.setState({ options: null, resolve: null });
  resolve?.(value);
}
