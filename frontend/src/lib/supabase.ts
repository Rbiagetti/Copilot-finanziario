import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export async function getToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function signIn(email: string, password: string) {
  return supabase.auth.signInWithPassword({ email, password });
}

export async function signUp(email: string, password: string) {
  return supabase.auth.signUp({ email, password });
}

export async function signOut() {
  return supabase.auth.signOut();
}

/** Login/registrazione con Google. Scope di default (openid/email/profile) — nessun
 * permesso aggiuntivo richiesto: l'app non può accedere a Gmail, Drive o altro. */
export async function signInWithGoogle() {
  return supabase.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: window.location.origin },
  });
}

/** Collega l'identità Google all'account attualmente loggato (stesso user_id, stessi dati —
 * a differenza di un login Google "a fresco" che creerebbe un utente nuovo). Richiede una
 * sessione attiva (va chiamata da loggati) e "Allow manual linking" abilitato su Supabase. */
export async function linkGoogleIdentity() {
  return supabase.auth.linkIdentity({
    provider: "google",
    options: { redirectTo: window.location.origin },
  });
}

/** Elenco provider collegati all'utente corrente (es. ["email", "google"]). */
export async function getLinkedProviders(): Promise<string[]> {
  const { data, error } = await supabase.auth.getUserIdentities();
  if (error || !data) return [];
  return data.identities.map((i) => i.provider);
}

/** Invia l'email di reset password. Il link porta a /reset-password con una sessione
 * di recupero temporanea, da cui l'utente può impostare una nuova password. */
export async function resetPasswordForEmail(email: string) {
  return supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/reset-password`,
  });
}

/** Imposta la nuova password. Va chiamata mentre è attiva la sessione di recupero
 * creata cliccando il link ricevuto via email (resetPasswordForEmail). */
export async function updatePassword(newPassword: string) {
  return supabase.auth.updateUser({ password: newPassword });
}
