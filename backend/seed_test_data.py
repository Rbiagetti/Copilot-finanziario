"""Genera dati di test realistici per 3 mesi."""
import sqlite3
import random
import os
from datetime import date, timedelta

DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./data/fincopilot.db").replace("sqlite:///", "")

TRANSACTIONS = [
    # Cibo - spese quotidiane
    ("cibo", 3.50, "caffe al bar"),
    ("cibo", 4.20, "cornetto e cappuccino"),
    ("cibo", 12.00, "pranzo in mensa"),
    ("cibo", 8.50, "panino e bibita"),
    ("cibo", 35.00, "spesa settimanale Esselunga"),
    ("cibo", 55.00, "spesa grossa Carrefour"),
    ("cibo", 42.00, "cena ristorante giapponese"),
    ("cibo", 28.00, "pizza con amici"),
    ("cibo", 60.00, "cena romantica"),
    ("cibo", 15.00, "sushi take away"),
    ("cibo", 6.50, "aperitivo"),
    ("cibo", 22.00, "brunch domenicale"),
    ("cibo", 18.00, "delivery Glovo"),
    # Trasporti
    ("trasporti", 50.00, "benzina"),
    ("trasporti", 45.00, "pieno benzina"),
    ("trasporti", 39.00, "abbonamento metro mensile"),
    ("trasporti", 1.50, "biglietto bus"),
    ("trasporti", 12.00, "taxi centro"),
    ("trasporti", 85.00, "treno Roma-Milano"),
    ("trasporti", 25.00, "parcheggio aeroporto"),
    ("trasporti", 8.50, "Uber"),
    # Casa
    ("casa", 650.00, "affitto mensile"),
    ("casa", 85.00, "bolletta luce"),
    ("casa", 45.00, "bolletta gas"),
    ("casa", 30.00, "internet fibra"),
    ("casa", 120.00, "spesa IKEA"),
    ("casa", 15.00, "detersivi e pulizia"),
    ("casa", 35.00, "riparazione rubinetto"),
    # Salute
    ("salute", 22.00, "farmacia"),
    ("salute", 80.00, "visita dentista"),
    ("salute", 150.00, "occhiali nuovi"),
    ("salute", 35.00, "integratori"),
    ("salute", 25.00, "crema solare e vitamine"),
    # Svago
    ("svago", 12.00, "cinema"),
    ("svago", 45.00, "concerto"),
    ("svago", 15.00, "Netflix + Disney+"),
    ("svago", 8.00, "birra al pub"),
    ("svago", 30.00, "escape room"),
    ("svago", 55.00, "cena e bowling"),
    ("svago", 20.00, "museo"),
    # Abbigliamento
    ("abbigliamento", 45.00, "maglietta Zara"),
    ("abbigliamento", 89.00, "scarpe Nike"),
    ("abbigliamento", 35.00, "jeans"),
    ("abbigliamento", 120.00, "giacca invernale"),
    # Lavoro
    ("lavoro", 15.00, "caffe coworking"),
    ("lavoro", 29.00, "mouse ergonomico"),
    ("lavoro", 12.00, "quaderno Moleskine"),
    # Abbonamenti
    ("abbonamenti", 9.99, "Spotify"),
    ("abbonamenti", 12.99, "Netflix"),
    ("abbonamenti", 7.99, "iCloud"),
    ("abbonamenti", 4.99, "ChatGPT Plus"),
    ("abbonamenti", 14.99, "palestra"),
    # Formazione
    ("formazione", 12.99, "corso Udemy Python"),
    ("formazione", 29.00, "libro programmazione"),
    ("formazione", 49.00, "workshop AI"),
]


def seed():
    conn = sqlite3.connect(DB_PATH)

    # Non cancello i dati esistenti, aggiungo solo
    today = date.today()
    start_date = today - timedelta(days=90)  # 3 mesi fa

    count = 0
    current = start_date

    while current <= today:
        # Ogni giorno 1-4 transazioni casuali
        n_tx = random.randint(1, 4)
        for _ in range(n_tx):
            cat, base_amount, note = random.choice(TRANSACTIONS)

            # Variazione prezzo +/- 20%
            amount = round(base_amount * random.uniform(0.8, 1.2), 2)

            # Spese ricorrenti mensili (affitto, bollette, abbonamenti)
            if cat == "casa" and "affitto" in note and current.day != 1:
                continue
            if cat == "casa" and "bolletta" in note and current.day not in [5, 10, 15]:
                continue
            if cat == "abbonamenti" and current.day != random.choice([1, 5, 10, 15]):
                continue

            hour = random.randint(7, 22)
            minute = random.randint(0, 59)
            time_str = f"{hour:02d}:{minute:02d}"

            sources = ["manual", "natural", "voice"]
            source = random.choice(sources)

            conn.execute(
                """INSERT INTO transactions (amount, category, description, date, time, source)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (amount, cat, note, current.isoformat(), time_str, source),
            )
            count += 1

        current += timedelta(days=1)

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    total_amount = conn.execute("SELECT ROUND(SUM(amount), 2) FROM transactions").fetchone()[0]
    conn.close()

    print(f"Inserite {count} nuove transazioni")
    print(f"Totale DB: {total} transazioni, EUR {total_amount}")


if __name__ == "__main__":
    seed()
