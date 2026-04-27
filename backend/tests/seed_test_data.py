"""
Seed di dati realistici per il backtest del motore chat AI.
Idempotente: elimina e ricrea solo le righe con source="backtest".

Distribuzione target:
  Ultimi 30gg:   ~1800€
  Giorni 31-60:  ~1500€
  Anomalia:      Esselunga 320€ ca. 45 giorni fa
"""
from __future__ import annotations

from datetime import date, timedelta
from backend.core.database import SessionLocal
from backend.core.database import Transaction


def _d(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


# ---------------------------------------------------------------------------
# Definizione transazioni seed
# Ogni tupla: (description, category, amount, days_ago, is_recurring, tags)
# ---------------------------------------------------------------------------
_ROWS: list[tuple] = [
    # ── CIBO ─────────────────────────────────────────────────────────────────
    # Esselunga 10x weekly (week 1..10); week 7 = anomalia 320€ (≈49 gg fa)
    ("Esselunga",  "cibo",  45.00,  3,  False, None),
    ("Esselunga",  "cibo",  82.00, 10,  False, None),
    ("Esselunga",  "cibo",  67.00, 17,  False, None),
    ("Esselunga",  "cibo",  53.00, 24,  False, None),
    ("Esselunga",  "cibo",  92.00, 31,  False, None),
    ("Esselunga",  "cibo",  48.00, 38,  False, None),
    ("Esselunga",  "cibo", 320.00, 45,  False, None),   # anomalia
    ("Esselunga",  "cibo",  60.00, 52,  False, None),
    ("Esselunga",  "cibo",  35.00, 59,  False, None),
    ("Esselunga",  "cibo", 110.00, 66,  False, None),
    # Carrefour 5x (last 5 weeks)
    ("Carrefour",  "cibo",  28.00,  5,  False, None),
    ("Carrefour",  "cibo",  57.00, 12,  False, None),
    ("Carrefour",  "cibo",  15.00, 19,  False, None),
    ("Carrefour",  "cibo",  44.00, 33,  False, None),
    ("Carrefour",  "cibo",  60.00, 40,  False, None),
    # Ristorante Da Mario 4x
    ("Ristorante Da Mario", "cibo",  45.00,  7, False, None),
    ("Ristorante Da Mario", "cibo",  72.00, 14, False, None),
    ("Ristorante Da Mario", "cibo",  38.00, 35, False, None),
    ("Ristorante Da Mario", "cibo",  85.00, 50, False, None),
    # McDonald's 4x
    ("McDonald's", "cibo",   9.50,  4, False, None),
    ("McDonald's", "cibo",  14.00, 11, False, None),
    ("McDonald's", "cibo",   8.50, 36, False, None),
    ("McDonald's", "cibo",  12.00, 55, False, None),
    # Starbucks 6x (ogni 3-4 giorni, ultimi 25gg)
    ("Starbucks",  "cibo",   4.50,  2, False, None),
    ("Starbucks",  "cibo",   7.00,  6, False, None),
    ("Starbucks",  "cibo",   5.50,  9, False, None),
    ("Starbucks",  "cibo",   8.50, 13, False, None),
    ("Starbucks",  "cibo",   4.00, 17, False, None),
    ("Starbucks",  "cibo",   6.50, 22, False, None),
    # Deliveroo 6x
    ("Deliveroo",  "cibo",  22.00,  1, False, None),
    ("Deliveroo",  "cibo",  38.00,  8, False, None),
    ("Deliveroo",  "cibo",  18.00, 15, False, None),
    ("Deliveroo",  "cibo",  45.00, 34, False, None),
    ("Deliveroo",  "cibo",  29.00, 41, False, None),
    ("Deliveroo",  "cibo",  33.00, 58, False, None),

    # ── TRASPORTI ─────────────────────────────────────────────────────────────
    # Uber 8x
    ("Uber",       "trasporti", 14.00,  2, False, None),
    ("Uber",       "trasporti", 28.00,  7, False, None),
    ("Uber",       "trasporti", 19.00, 13, False, None),
    ("Uber",       "trasporti", 35.00, 20, False, None),
    ("Uber",       "trasporti", 12.00, 32, False, None),
    ("Uber",       "trasporti", 22.00, 40, False, None),
    ("Uber",       "trasporti", 17.00, 48, False, None),
    ("Uber",       "trasporti", 31.00, 56, False, None),
    # Trenitalia 3x
    ("Trenitalia", "trasporti", 25.00, 10, False, None),
    ("Trenitalia", "trasporti", 89.00, 28, False, None),
    ("Trenitalia", "trasporti", 54.00, 55, False, None),
    # Q8 benzina 4x
    ("Q8 benzina", "trasporti", 65.00,  6, False, None),
    ("Q8 benzina", "trasporti", 90.00, 20, False, None),
    ("Q8 benzina", "trasporti", 55.00, 40, False, None),
    ("Q8 benzina", "trasporti", 78.00, 58, False, None),
    # ATM abbonamento 1x (ricorrente)
    ("ATM abbonamento", "trasporti", 39.00, 5, True, "abbonamento,trasporti"),
    # Telepass 4x
    ("Telepass",   "trasporti",  8.50,  3, False, None),
    ("Telepass",   "trasporti", 22.00, 18, False, None),
    ("Telepass",   "trasporti", 11.00, 37, False, None),
    ("Telepass",   "trasporti", 15.00, 54, False, None),

    # ── CASA ─────────────────────────────────────────────────────────────────
    # IKEA 3x (critico per TC-A01)
    ("IKEA",       "casa",  45.00, 12, False, None),
    ("IKEA",       "casa", 180.00, 25, False, None),
    ("IKEA",       "casa", 320.00, 50, False, None),
    # Leroy Merlin 2x
    ("Leroy Merlin", "casa",  35.00, 18, False, None),
    ("Leroy Merlin", "casa", 150.00, 45, False, None),
    # Affitto 1x (ricorrente)
    ("Affitto",    "casa", 900.00, 15, True,  "affitto,fisso"),
    # Edison luce 2x (ricorrente)
    ("Edison luce","casa",  65.00, 10, True,  "utenza,fisso"),
    ("Edison luce","casa", 110.00, 40, True,  "utenza,fisso"),
    # Vodafone 2x (ricorrente)
    ("Vodafone",   "casa",  24.99,  8, True,  "abbonamento,fisso"),
    ("Vodafone",   "casa",  24.99, 38, True,  "abbonamento,fisso"),

    # ── SVAGO ────────────────────────────────────────────────────────────────
    # Netflix 3x (ricorrente)
    ("Netflix",    "svago", 15.99,  5, True,  "abbonamento,streaming"),
    ("Netflix",    "svago", 15.99, 35, True,  "abbonamento,streaming"),
    ("Netflix",    "svago", 15.99, 65, True,  "abbonamento,streaming"),
    # Spotify 3x (ricorrente)
    ("Spotify",    "svago",  9.99,  7, True,  "abbonamento,streaming"),
    ("Spotify",    "svago",  9.99, 37, True,  "abbonamento,streaming"),
    ("Spotify",    "svago",  9.99, 67, True,  "abbonamento,streaming"),
    # Amazon Prime 1x
    ("Amazon Prime","svago",49.99, 20, True,  "abbonamento"),
    # Cinema Odeon 3x
    ("Cinema Odeon","svago",11.00,  9, False, None),
    ("Cinema Odeon","svago",22.00, 23, False, None),
    ("Cinema Odeon","svago",15.00, 44, False, None),
    # Palestra FitActive 5x (ricorrente, ultimi 45gg)
    ("Palestra FitActive","svago",55.00,  6, True,  "salute,abbonamento"),
    ("Palestra FitActive","svago",55.00, 14, True,  "salute,abbonamento"),
    ("Palestra FitActive","svago",55.00, 23, True,  "salute,abbonamento"),
    ("Palestra FitActive","svago",55.00, 32, True,  "salute,abbonamento"),
    ("Palestra FitActive","svago",55.00, 42, True,  "salute,abbonamento"),

    # ── ABBONAMENTI ──────────────────────────────────────────────────────────
    # ChatGPT Plus 2x
    ("ChatGPT Plus","abbonamenti",20.00,  4, True,  "abbonamento,tech"),
    ("ChatGPT Plus","abbonamenti",20.00, 34, True,  "abbonamento,tech"),
    # iCloud 3x
    ("iCloud",     "abbonamenti",  0.99,  3, True,  "abbonamento,tech"),
    ("iCloud",     "abbonamenti",  0.99, 33, True,  "abbonamento,tech"),
    ("iCloud",     "abbonamenti",  0.99, 63, True,  "abbonamento,tech"),

    # ── FORMAZIONE ───────────────────────────────────────────────────────────
    # Udemy 2x
    ("Udemy",      "formazione", 11.99, 16, False, None),
    ("Udemy",      "formazione", 19.99, 55, False, None),
    # O'Reilly 1x (ricorrente)
    ("O'Reilly",   "formazione", 49.00, 20, True,  "abbonamento,tech"),
    # Libro Amazon 2x
    ("Libro Amazon","formazione",12.00,  8, False, None),
    ("Libro Amazon","formazione",28.00, 45, False, None),
]


def seed_backtest_db() -> int:
    """Cancella e reinserisce le transazioni di test. Ritorna il numero di righe inserite."""
    with SessionLocal() as session:
        deleted = session.query(Transaction).filter_by(source="backtest").delete()
        session.commit()

        objs = [
            Transaction(
                description=desc,
                category=cat,
                amount=amount,
                date=_d(days_ago),
                is_recurring=recurring,
                tags=tags,
                source="backtest",
                account="principale",
            )
            for desc, cat, amount, days_ago, recurring, tags in _ROWS
        ]
        session.bulk_save_objects(objs)
        session.commit()

    return len(_ROWS)


if __name__ == "__main__":
    n = seed_backtest_db()
    print(f"Seed completato: {n} transazioni inserite (source=backtest)")
