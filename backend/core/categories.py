"""Fonte unica delle categorie standard di FinCopilot.

Le categorie standard sono fisse e non eliminabili; le personalizzate vivono nella
tabella `categories` e vengono unite per utente da `get_active_category_names()`.

Prima di questo modulo la lista era duplicata in `api/models/schemas.py` (10 voci)
e in `core/ai_engine.py` (11 voci, con `intrattenimento`): il motore AI accettava
una categoria che il resto dell'app non offriva. Ora entrambi importano da qui.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.core.database import Category

# Ordine usato dai menu del frontend. `intrattenimento` era già presente nelle
# icone e nel motore AI, ma mancava nella lista API: ora è una categoria standard
# a tutti gli effetti.
STANDARD_CATEGORIES: list[str] = [
    "cibo",
    "trasporti",
    "casa",
    "salute",
    "svago",
    "abbigliamento",
    "lavoro",
    "abbonamenti",
    "formazione",
    "intrattenimento",
    "altro",
]

CATEGORIES: frozenset[str] = frozenset(STANDARD_CATEGORIES)


def get_active_category_names(db: Session, user_id: str) -> list[str]:
    """Le standard (fisse, mai toccate) + le personalizzate attive dell'utente.
    Usata ovunque serve validare/proporre categorie: creazione/modifica transazioni,
    AI Importer, quick-add in linguaggio naturale, router della chat."""
    custom = (
        db.query(Category.name)
        .filter(Category.user_id == user_id, Category.active == True)
        .all()
    )
    return STANDARD_CATEGORIES + [row[0] for row in custom]
