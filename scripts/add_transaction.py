import sqlite3
import sys
from datetime import datetime

DB_PATH = "db/finance.db"

CATEGORIES = [
    "cibo", "trasporti", "casa", "salute",
    "intrattenimento", "lavoro", "shopping", "altro"
]

def add_transaction(amount: float, category: str, note: str = "", source: str = "manual"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO transactions (amount, category, note, source) VALUES (?, ?, ?, ?)",
        (amount, category, note, source)
    )
    conn.commit()
    conn.close()

def list_transactions(limit: int = 10):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, amount, category, note, timestamp FROM transactions ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return rows

def main():
    print("\n💰 Copilota Finanziario — Inserimento Manuale")
    print("=" * 45)

    try:
        amount = float(input("Importo (€): "))
    except ValueError:
        print("❌ Importo non valido")
        sys.exit(1)

    print(f"Categorie: {', '.join(CATEGORIES)}")
    category = input("Categoria: ").strip().lower()
    if category not in CATEGORIES:
        print(f"⚠️  Categoria non riconosciuta, uso 'altro'")
        category = "altro"

    note = input("Nota (opzionale): ").strip()

    add_transaction(amount, category, note)
    print(f"\n✅ Salvato: €{amount:.2f} — {category}" + (f" — {note}" if note else ""))

    print("\n📋 Ultime transazioni:")
    for row in list_transactions(5):
        print(f"  [{row[0]}] €{row[1]:.2f} | {row[2]} | {row[3]} | {row[4]}")


if __name__ == '__main__':
    main()
