import os
import sys
import sqlite3
import json
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

def save(amount: float, category: str, note: str, source: str = "natural"):
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
    print("\n💰 Copilota Finanziario — Inserimento Naturale")
    print("=" * 48)
    print("Scrivi la spesa in italiano (es: 'caffè 3 euro')")
    print("Digita 'q' per uscire\n")

    while True:
        text = input(">>> ").strip()
        if text.lower() == "q":
            break
        if not text:
            continue

        try:
            parsed = parse(text)
            if parsed["amount"] == 0.0:
                print("⚠️  Importo non trovato, riprova")
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
