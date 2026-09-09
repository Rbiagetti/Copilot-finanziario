import { Link } from "react-router-dom";
import { Wallet, ArrowLeft } from "lucide-react";

export default function PrivacyPolicy() {
  return (
    <div className="legal-page">
      <div className="legal-card">
        <Link to="/login" className="legal-back"><ArrowLeft size={16} /> Torna al login</Link>
        <div className="legal-logo"><Wallet size={26} /><span>FinCopilot</span></div>
        <h1>Informativa sulla privacy</h1>
        <p className="legal-updated">Ultimo aggiornamento: 9 settembre 2026</p>

        <p>
          FinCopilot è un progetto personale di gestione delle finanze, sviluppato e gestito da
          Roberto Biagetti (contatto: <a href="mailto:rbiagetti2001@gmail.com">rbiagetti2001@gmail.com</a>).
          Questa pagina spiega quali dati raccoglie l'app, perché, e come vengono trattati.
        </p>

        <h2>1. Dati raccolti</h2>
        <ul>
          <li><strong>Dati account</strong>: email e password (gestite da Supabase Auth — la password non è mai visibile né accessibile a me in chiaro), oppure identità Google se accedi con "Accedi con Google".</li>
          <li><strong>Dati finanziari</strong>: le transazioni, importi, categorie, budget e note che inserisci volontariamente nell'app.</li>
          <li><strong>Cronologia chat</strong>: le domande che fai all'assistente AI e le relative risposte, salvate per mantenere il contesto della conversazione.</li>
        </ul>
        <p>Non raccolgo dati che non inserisci tu stesso: nessun tracciamento del comportamento, nessun cookie pubblicitario, nessun analytics di terze parti.</p>

        <h2>2. Come vengono usati i dati</h2>
        <p>
          I dati servono esclusivamente a far funzionare l'app per te: mostrare dashboard e report,
          calcolare statistiche, e generare le risposte dell'assistente AI alle tue domande sulle spese.
        </p>

        <h2>3. Servizi di terze parti (sub-responsabili)</h2>
        <p>Per far funzionare FinCopilot mi appoggio ai seguenti fornitori, che trattano i dati per mio conto secondo le rispettive policy:</p>
        <ul>
          <li><strong>Supabase</strong> — autenticazione e database dove sono salvati i tuoi dati.</li>
          <li><strong>Groq</strong> — elabora le domande che fai in chat (testo della domanda + dati di spesa aggregati necessari a rispondere) per generare le risposte dell'assistente AI.</li>
          <li><strong>Render</strong> e <strong>Vercel</strong> — ospitano rispettivamente il backend e il frontend dell'app.</li>
        </ul>
        <p>Nessuno di questi fornitori usa i tuoi dati per scopi propri (pubblicità, rivendita, addestramento di modelli su tuoi dati personali) al di fuori dell'erogazione del servizio.</p>

        <h2>4. Conservazione e cancellazione</h2>
        <p>
          I dati restano finché il tuo account è attivo. Puoi chiedermi in qualsiasi momento la cancellazione
          completa del tuo account e di tutti i dati associati scrivendo a{" "}
          <a href="mailto:rbiagetti2001@gmail.com">rbiagetti2001@gmail.com</a>.
        </p>

        <h2>5. Sicurezza</h2>
        <p>
          Le connessioni tra app, backend e database sono cifrate (HTTPS). L'accesso ai dati richiede
          un token di autenticazione valido, verificato ad ogni richiesta. Ogni utente vede esclusivamente
          i propri dati.
        </p>

        <h2>6. I tuoi diritti</h2>
        <p>
          In quanto interessato, hai diritto di accedere ai tuoi dati, chiederne la rettifica, la cancellazione
          o la portabilità in un formato leggibile. Per esercitare questi diritti scrivimi a{" "}
          <a href="mailto:rbiagetti2001@gmail.com">rbiagetti2001@gmail.com</a>.
        </p>

        <h2>7. Modifiche</h2>
        <p>
          Questa informativa può essere aggiornata; la data in cima alla pagina riflette l'ultima revisione.
          Cambiamenti sostanziali (es. nuovi fornitori terzi) ti saranno comunicati via email.
        </p>
      </div>
    </div>
  );
}
