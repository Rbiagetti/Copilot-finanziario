import { Link } from "react-router-dom";
import { Wallet, ArrowLeft } from "lucide-react";

export default function TermsPage() {
  return (
    <div className="legal-page">
      <div className="legal-card">
        <Link to="/login" className="legal-back"><ArrowLeft size={16} /> Torna al login</Link>
        <div className="legal-logo"><Wallet size={26} /><span>FinCopilot</span></div>
        <h1>Termini di utilizzo</h1>
        <p className="legal-updated">Ultimo aggiornamento: 9 settembre 2026</p>

        <p>
          FinCopilot è un progetto personale sviluppato e gestito da Roberto Biagetti, offerto così
          com'è ("as-is"), senza garanzie commerciali. Usando l'app accetti questi termini.
        </p>

        <h2>1. Cos'è il servizio</h2>
        <p>
          FinCopilot ti permette di registrare le tue spese, visualizzare statistiche e budget, e porre
          domande in linguaggio naturale a un assistente AI che analizza i tuoi dati finanziari.
        </p>

        <h2>2. Nessuna consulenza finanziaria</h2>
        <p>
          <strong>Le risposte dell'assistente AI hanno esclusivamente finalità informativa e organizzativa.</strong>{" "}
          Non costituiscono consulenza finanziaria, fiscale o di investimento professionale, e non
          sostituiscono il parere di un consulente qualificato. Le decisioni economiche che prendi
          restano sotto la tua esclusiva responsabilità.
        </p>

        <h2>3. Accuratezza dei dati</h2>
        <p>
          Le analisi e i report generati dall'app si basano sui dati che inserisci tu. Sei responsabile
          della correttezza delle informazioni inserite (importi, categorie, date): l'app non verifica
          l'esattezza dei dati con fonti esterne (banca, estratti conto).
        </p>

        <h2>4. Account e sicurezza</h2>
        <p>
          Sei responsabile di mantenere riservate le credenziali del tuo account. Segnalami subito
          qualsiasi accesso non autorizzato sospetto.
        </p>

        <h2>5. Disponibilità del servizio</h2>
        <p>
          Essendo un progetto personale, non garantisco uptime, SLA o assistenza continuativa.
          Il servizio può essere modificato, sospeso o interrotto in qualsiasi momento, con preavviso
          quando ragionevolmente possibile.
        </p>

        <h2>6. Limitazione di responsabilità</h2>
        <p>
          Nei limiti consentiti dalla legge, non sono responsabile per perdite economiche o danni
          derivanti dall'uso (o dall'impossibilità di uso) dell'app, incluse eventuali imprecisioni
          delle analisi generate dall'assistente AI.
        </p>

        <h2>7. Trattamento dei dati</h2>
        <p>
          Il trattamento dei tuoi dati personali è descritto nella{" "}
          <Link to="/privacy">informativa sulla privacy</Link>.
        </p>

        <h2>8. Legge applicabile</h2>
        <p>Questi termini sono regolati dalla legge italiana.</p>

        <h2>9. Contatti</h2>
        <p>
          Per domande su questi termini: <a href="mailto:rbiagetti2001@gmail.com">rbiagetti2001@gmail.com</a>.
        </p>
      </div>
    </div>
  );
}
