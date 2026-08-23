import { useEffect } from "react";

/**
 * Blocca lo scroll della pagina sotto un modale mentre è aperto.
 *
 * Non è solo estetica: su Safari mobile, un elemento `position: fixed` aggiunto al DOM
 * mentre la pagina è scrollata (es. si apre il modale di modifica dopo aver scrollato una
 * lista lunga di transazioni) viene renderizzato con un bug noto — appare spostato in basso
 * di quanto la pagina era scrollata, invece che centrato nel viewport, finché non arriva un
 * altro scroll/repaint. Bloccare lo scroll del body (position:fixed con top negativo pari
 * allo scroll corrente) evita il bug e, come effetto collaterale corretto, impedisce anche
 * lo scroll "fantasma" dello sfondo mentre il modale è aperto.
 */
export function useBodyScrollLock(active: boolean) {
  useEffect(() => {
    if (!active) return;

    const scrollY = window.scrollY;
    const body = document.body;
    const prev = { position: body.style.position, top: body.style.top, width: body.style.width };

    body.style.position = "fixed";
    body.style.top = `-${scrollY}px`;
    body.style.width = "100%";

    return () => {
      body.style.position = prev.position;
      body.style.top = prev.top;
      body.style.width = prev.width;
      window.scrollTo(0, scrollY);
    };
  }, [active]);
}
