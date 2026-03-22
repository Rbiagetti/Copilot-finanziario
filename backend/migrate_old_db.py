"""Migra i dati dal vecchio db/finance.db al nuovo data/fincopilot.db."""
import sqlite3
import os

OLD_DB = "db/finance.db"
NEW_DB = "data/fincopilot.db"


def migrate():
    if not os.path.exists(OLD_DB):
        print("Nessun database precedente trovato, skip migrazione.")
        return

    os.makedirs("data", exist_ok=True)

    old_conn = sqlite3.connect(OLD_DB)
    old_rows = old_conn.execute(
        "SELECT amount, category, note, timestamp, source FROM transactions"
    ).fetchall()
    old_conn.close()

    if not old_rows:
        print("Nessuna transazione da migrare.")
        return

    new_conn = sqlite3.connect(NEW_DB)
    new_conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            description TEXT,
            date TEXT NOT NULL,
            time TEXT,
            account TEXT DEFAULT 'principale',
            tags TEXT,
            source TEXT DEFAULT 'manual',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for amount, category, note, timestamp, source in old_rows:
        date_part = timestamp[:10] if timestamp else "2024-01-01"
        time_part = timestamp[11:16] if timestamp and len(timestamp) > 10 else None
        new_conn.execute(
            "INSERT INTO transactions (amount, category, description, date, time, source) VALUES (?, ?, ?, ?, ?, ?)",
            (amount, category, note, date_part, time_part, source or "manual"),
        )

    new_conn.commit()
    count = new_conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    new_conn.close()
    print(f"Migrate {count} transazioni da {OLD_DB} → {NEW_DB}")


if __name__ == "__main__":
    migrate()
