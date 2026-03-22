import os
import sys
import sqlite3
import json
import subprocess
import tempfile
import threading
from openai import OpenAI

DB_PATH = "db/finance.db"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

CATEGORIES = ["cibo", "trasporti", "casa", "salute", "intrattenimento", "lavoro", "shopping", "altro"]

SYSTEM_PROMPT = f"""Sei un parser di spese personali.
Estrai da testo libero in italiano: importo, categoria e nota.
Rispondi SOLO con JSON valido, nessun testo extra.
Formato: {{"amount": float, "category": str, "note": str}}
Categorie disponibili: {", ".join(CATEGORIES)}
Se la categoria non è chiara, usa "altro".
Se manca l'importo, usa 0.0.
La nota è una descrizione breve della spesa."""

def record_until_enter() -> str:
    path = tempfile.mktemp(suffix=".wav")
    proc = subprocess.Popen(
        ["sox", "-d", "-r", "16000", "-c", "1", "-b", "16", path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print("🎙️  Registrazione avviata... parla!")
    print("   [ premi INVIO per fermare ]")
    input()
    proc.terminate()
    proc.wait()
    print("⏹️  Registrazione terminata")
    return path

def transcribe(audio_path: str) -> str:
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=f,
            language="it"
        )
    return response.text.strip()

def parse(text: str) -> dict:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        temperature=0,
        max_tokens=100
    )
    return json.loads(response.choices[0].message.content.strip())

def save(amount: float, category: str, note: str, source: str = "voice"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO transactions (amount, category, note, source, timestamp) VALUES (?, ?, ?, ?, datetime('now', 'localtime'))",
        (amount, category, note, source)
    )
    conn.commit()
    conn.close()

def list_recent(limit: int = 5):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, amount, category, note, timestamp, source FROM transactions ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return rows

def main():
    print("\n💰 Copilota Finanziario — Input Vocale")
    print("=" * 42)
    print("INVIO = avvia registrazione | q = esci\n")

    while True:
        cmd = input("[ INVIO = registra | q = esci ] ").strip().lower()
        if cmd == "q":
            break

        try:
            audio_path = record_until_enter()
            text = transcribe(audio_path)
            os.remove(audio_path)

            if not text:
                print("⚠️  Nessun audio rilevato, riprova\n")
                continue

            print(f"📝 Trascritto: \"{text}\"")

            parsed = parse(text)
            if parsed["amount"] == 0.0:
                print("⚠️  Importo non trovato, riprova\n")
                continue

            save(parsed["amount"], parsed["category"], parsed["note"])
            print(f"✅ €{parsed['amount']:.2f} — {parsed['category']} — {parsed['note']}\n")

        except Exception as e:
            print(f"❌ Errore: {e}\n")

    print("\n📋 Ultime transazioni:")
    for row in list_recent():
        print(f"  [{row[0]}] €{row[1]:.2f} | {row[2]} | {row[3]} | {row[4]} | src:{row[5]}")

if __name__ == "__main__":
    main()
