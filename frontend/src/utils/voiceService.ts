/* 
  voiceService.ts — Singleton Globale per la gestione della Web Speech API.
  Garantisce che esista una sola istanza attiva nell'app, evitando "leaks" del microfono
  e risolvendo i conflitti tra componenti diversi (es. Chat vs TransactionForm).
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

  private getSpeechRecognition() {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    return SpeechRecognition ? new SpeechRecognition() : null;
  }

  /**
   * Avvia una sessione di ascolto. 
   * Se esiste già una sessione attiva, viene terminata forzatamente (abort).
   */
  start(options: VoiceOptions) {
    // 1. Forza la chiusura di sessioni precedenti nel singleton
    this.stop();

    const rec = this.getSpeechRecognition();
    if (!rec) {
      options.onError("browser-not-supported");
      return;
    }

    this.recognition = rec;
    rec.lang = options.lang || "it-IT";
    rec.continuous = options.continuous ?? true;
    rec.interimResults = options.interimResults ?? true;

    rec.onstart = () => {
      this.isActive = true;
    };

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
      // Ignora errori di silenzio o interruzione manuale (aborted)
      if (['no-speech', 'aborted'].includes(event.error)) {
        return;
      }
      options.onError(event.error);
    };

    rec.onend = () => {
      this.isActive = false;
      this.recognition = null;
      options.onEnd();
    };

    rec.start();
  }

  /**
   * Termina la sessione corrente in modo aggressivo.
   */
  stop() {
    if (this.recognition) {
      try {
        // abort() è più veloce di stop() perché interrompe subito l'audio stream
        this.recognition.abort();
      } catch (e) {
        console.warn("Errore durante abort microfono:", e);
      }
      this.recognition = null;
      this.isActive = false;
    }
  }

  isListening() {
    return this.isActive;
  }
}

export const voiceService = new VoiceService();
