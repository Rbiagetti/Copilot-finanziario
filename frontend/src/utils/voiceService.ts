/*
  voiceService.ts — Singleton Globale per la gestione della Web Speech API.
  Garantisce che esista una sola istanza attiva nell'app, evitando "leaks" del microfono
  e risolvendo i conflitti tra componenti diversi (es. Chat vs TransactionForm).

  FIX: auto-restart dopo pausa — il browser chiude la sessione anche con continuous:true
  su molte implementazioni (Chrome mobile, Safari). Il service riapre silenziosamente
  la sessione così il testo già dettato non va perso e l'utente può continuare a parlare.
*/

export interface VoiceOptions {
  lang?: string;
  continuous?: boolean;
  interimResults?: boolean;
  onResult: (transcript: string, isFinal: boolean) => void;
  onError: (error: string) => void;
  onEnd: () => void;
}

class VoiceService {
  private recognition: any = null;
  private isActive: boolean = false;
  private intentionalStop: boolean = false;
  private activeOptions: VoiceOptions | null = null;

  private getSpeechRecognition() {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    return SpeechRecognition ? new SpeechRecognition() : null;
  }

  /**
   * Avvia una sessione di ascolto.
   * Se esiste già una sessione attiva, viene terminata forzatamente (abort).
   */
  start(options: VoiceOptions) {
    this.stop();
    this.intentionalStop = false;
    this.activeOptions = options;
    this._startInner();
  }

  /**
   * Apre (o riapre) la sessione di riconoscimento usando le opzioni correnti.
   * Chiamato sia alla prima apertura che all'auto-restart dopo pausa.
   */
  private _startInner() {
    const options = this.activeOptions;
    if (!options) return; // stop() è stato chiamato nel frattempo

    const rec = this.getSpeechRecognition();
    if (!rec) {
      options.onError("browser-not-supported");
      return;
    }

    this.recognition = rec;
    rec.lang = options.lang || "it-IT";
    rec.continuous = options.continuous ?? true;
    rec.interimResults = options.interimResults ?? true;
    this.isActive = true;

    rec.onresult = (event: any) => {
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }

      options.onResult(finalTranscript || interimTranscript, !!finalTranscript);
    };

    rec.onerror = (event: any) => {
      // no-speech = pausa di silenzio (gestita da onend con auto-restart)
      // aborted = stop() chiamato dal codice — ignorato
      if (['no-speech', 'aborted'].includes(event.error)) return;
      options.onError(event.error);
    };

    rec.onend = () => {
      this.isActive = false;
      this.recognition = null;

      if (!this.intentionalStop && this.activeOptions) {
        // Pausa rilevata: il browser ha chiuso la sessione automaticamente.
        // Riapriamo silenziosamente — il componente non vede interruzione.
        setTimeout(() => this._startInner(), 150);
      }
      // Se intentionalStop: stop() ha già chiamato onEnd e pulito activeOptions.
      // Non richiamiamo onEnd qui per evitare doppio trigger.
    };

    try {
      rec.start();
    } catch (e) {
      this.isActive = false;
      options.onError('start-failed');
    }
  }

  /**
   * Termina la sessione corrente in modo definitivo (scelta dell'utente).
   */
  stop() {
    this.intentionalStop = true;
    const opts = this.activeOptions;
    this.activeOptions = null; // pulisce prima dell'abort: onend non farà restart

    if (this.recognition) {
      try {
        this.recognition.abort();
      } catch (e) {
        console.warn("Errore durante abort microfono:", e);
      }
      this.recognition = null;
      this.isActive = false;
    }

    // Notifica il componente che il mic è stato chiuso intenzionalmente
    if (opts) opts.onEnd();
  }

  isListening() {
    return this.isActive;
  }
}

export const voiceService = new VoiceService();
