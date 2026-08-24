"""AI Importer — parsing di estratti conto CSV/XLSX/PDF e mapping colonne→campi DB.

Flusso (stateless, nessuno stato salvato lato server tra le due chiamate):
  1. /import/preview — riceve il file, lo parsa, propone un mapping colonne→campi
     (euristica + AI) e ritorna un'anteprima delle prime righe.
  2. /import/commit  — riceve di nuovo lo stesso file + il mapping confermato/corretto
     dall'utente, applica il mapping a tutte le righe, deduplica contro le
     transazioni esistenti, categorizza con AI le righe senza categoria e importa.
"""
import csv
import io
import re
import logging
from datetime import date as _date
from typing import Optional

import pandas as pd
from dateutil import parser as dateutil_parser

from backend.api.models.schemas import CATEGORIES

logger = logging.getLogger(__name__)

# Campi verso cui l'utente può mappare una colonna del file
TARGET_FIELDS = ["date", "amount", "description", "category", "account"]
REQUIRED_FIELDS = ["date", "amount"]

MAX_FILE_BYTES = 5 * 1024 * 1024   # 5MB — T-021
MAX_ROWS = 1000                     # T-021
PREVIEW_ROWS = 10

_ENCODINGS_TO_TRY = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]


class ImportError_(Exception):
    """Errore di parsing/validazione del file di import (nome non in conflitto con builtin)."""


def _parse_pdf(content: bytes) -> pd.DataFrame:
    """Estrae la tabella movimenti da un estratto conto PDF (es. Buddybank/UniCredit e
    formati simili: molte banche italiane offrono solo il PDF, non CSV/Excel).
    Euristica: la tabella dei movimenti è quella la cui riga di intestazione contiene sia
    una colonna "data" che una "descrizione" — si ripete identica su ogni pagina, quindi si
    prende l'header dalla prima occorrenza e si concatenano le righe dati di tutte le pagine."""
    import pdfplumber

    header: Optional[list[str]] = None
    rows: list[list[str]] = []

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    if not table or len(table) < 1:
                        continue
                    head = [str(c or "").strip().lower() for c in table[0]]
                    if not any("data" in c for c in head) or not any("descrizion" in c for c in head):
                        continue  # non è la tabella movimenti (es. blocco IBAN)
                    if header is None:
                        header = [str(c or "").strip() for c in table[0]]
                    for r in table[1:]:
                        if [str(c or "").strip().lower() for c in r] == head:
                            continue  # header ripetuto su ogni pagina
                        rows.append([str(c or "").replace("\n", " ").strip() for c in r])
    except Exception as e:
        raise ImportError_(f"Impossibile leggere il file PDF: {e}")

    if header is None or not rows:
        raise ImportError_(
            "Non ho trovato una tabella movimenti riconoscibile nel PDF. "
            "Alcuni formati di estratto conto non sono estraibili automaticamente: "
            "prova a esportare CSV/Excel dalla banca, se disponibile."
        )

    width = len(header)
    fixed_rows = [r[:width] + [""] * (width - len(r)) for r in rows]
    return pd.DataFrame(fixed_rows, columns=header, dtype=str)


_CSV_HEADER_DATE_KEYWORDS = ("data", "date")
_CSV_HEADER_CONTENT_KEYWORDS = (
    "descrizion", "importo", "amount", "denaro", "causale", "dare", "avere", "valore", "uscite", "entrate",
)


def _extract_csv_table(text: str) -> Optional[pd.DataFrame]:
    """Alcuni export (es. i 'consolidated statement' di Revolut) non sono una tabella pulita:
    hanno decine di righe di riepilogo/saldi/IBAN PRIMA della vera intestazione dei movimenti,
    e magari altre sezioni dopo. Un pd.read_csv normale prenderebbe la prima riga (il preambolo)
    come header, producendo colonne spazzatura tipo "Unnamed: 3".

    Cerca invece la riga che sembra davvero l'intestazione della tabella movimenti (contiene sia
    una parola tipo "data" sia una tipo "importo"/"descrizione"/...), e se la trova non in cima al
    file estrae solo quella tabella (fino alla prima riga vuota successiva, che nel formato Revolut
    segna la fine della sezione). Se l'header è già in riga 0 (export "normali" tipo N26/Fineco/lo
    stesso export di FinCopilot) ritorna None: nessun cambiamento, si usa il path normale."""
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except Exception:
        return None
    if not rows:
        return None

    def is_header_row(fields: list[str]) -> bool:
        joined = " ".join(f.strip().lower() for f in fields)
        return (
            any(kw in joined for kw in _CSV_HEADER_DATE_KEYWORDS)
            and any(kw in joined for kw in _CSV_HEADER_CONTENT_KEYWORDS)
        )

    header_idx = next((i for i, r in enumerate(rows) if is_header_row(r)), None)
    if header_idx is None or header_idx == 0:
        return None  # niente preambolo da saltare: usa il path pd.read_csv normale

    header = [str(c or "").strip() for c in rows[header_idx]]
    width = len(header)
    data_rows: list[list[str]] = []
    for r in rows[header_idx + 1:]:
        if not any(str(c or "").strip() for c in r):
            break  # riga vuota: fine della tabella (formato Revolut e simili)
        fixed = [str(c or "") for c in r][:width]
        fixed += [""] * (width - len(fixed))
        data_rows.append(fixed)

    if not data_rows:
        return None
    return pd.DataFrame(data_rows, columns=header, dtype=str)


def parse_upload(filename: str, content: bytes) -> pd.DataFrame:
    """Parsa un file CSV, XLSX/XLS o PDF (estratto conto) in un DataFrame di stringhe
    (nessuna conversione di tipo, per non perdere formati data/numero locali prima del
    mapping esplicito)."""
    if len(content) > MAX_FILE_BYTES:
        raise ImportError_(f"File troppo grande (max {MAX_FILE_BYTES // (1024*1024)}MB)")

    name = (filename or "").lower()

    if name.endswith(".pdf"):
        df = _parse_pdf(content)
    elif name.endswith((".xlsx", ".xls")):
        try:
            df = pd.read_excel(io.BytesIO(content), dtype=str, engine=None)
        except Exception as e:
            raise ImportError_(f"Impossibile leggere il file Excel: {e}")
    else:
        # CSV: auto-detect encoding e separatore (virgola, punto e virgola, tab)
        df = None
        last_err = None
        for enc in _ENCODINGS_TO_TRY:
            try:
                text = content.decode(enc)
                extracted = _extract_csv_table(text)
                df = extracted if extracted is not None else pd.read_csv(io.StringIO(text), sep=None, engine="python", dtype=str)
                break
            except Exception as e:
                last_err = e
                continue
        if df is None:
            raise ImportError_(f"Impossibile leggere il file CSV (encoding/separatore non riconosciuto): {last_err}")

    df = df.fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    # Righe completamente vuote fuori
    df = df[~(df.astype(str).apply(lambda r: "".join(r).strip() == "", axis=1))]

    if len(df) > MAX_ROWS:
        raise ImportError_(f"Troppe righe ({len(df)}), massimo {MAX_ROWS} per import")
    if df.empty:
        raise ImportError_("Il file non contiene righe valide")

    return df.reset_index(drop=True)


# ─── MAPPING EURISTICO (fallback + base per l'AI) ────────────────────────────

_HEURISTIC_KEYWORDS = {
    "date": ["data valuta", "data contabile", "data operazione", "data", "date"],
    "amount": ["importo", "amount", "dare/avere", "dare", "avere", "importo eur", "valore", "uscite", "uscita"],
    "description": ["descrizione", "causale", "causale abi", "description", "note", "dettaglio", "operazione"],
    "category": ["categoria", "category"],
    "account": ["conto", "account", "iban"],
}


def _heuristic_mapping(columns: list[str]) -> dict[str, Optional[str]]:
    mapping: dict[str, Optional[str]] = {f: None for f in TARGET_FIELDS}
    used: set[str] = set()
    for field, keywords in _HEURISTIC_KEYWORDS.items():
        for col in columns:
            if col in used:
                continue
            col_low = col.strip().lower()
            if any(kw == col_low or kw in col_low for kw in keywords):
                mapping[field] = col
                used.add(col)
                break
    return mapping


def suggest_mapping(columns: list[str], sample_rows: list[dict]) -> dict[str, Optional[str]]:
    """Propone un mapping colonna→campo DB. Parte da un'euristica su nomi colonna,
    poi prova a rifinirla con l'AI usando anche qualche riga di esempio (aiuta nei
    casi ambigui, es. più colonne numeriche o nomi non standard). Se l'AI non è
    disponibile o fallisce, resta valida l'euristica."""
    mapping = _heuristic_mapping(columns)

    try:
        from backend.core.ai_engine import client, MODEL, GROQ_API_KEY
        if not GROQ_API_KEY:
            return mapping

        sample_txt = "\n".join(
            ", ".join(f"{k}={v}" for k, v in row.items()) for row in sample_rows[:5]
        )
        prompt = (
            "Sei un assistente che mappa le colonne di un estratto conto bancario "
            "(CSV/Excel) ai campi di un database di spese personali.\n"
            f"Colonne disponibili nel file: {columns}\n"
            f"Esempio di righe (prime {min(5, len(sample_rows))}):\n{sample_txt}\n\n"
            "Campi target da riempire (usa il nome ESATTO di una colonna del file, o null "
            "se non c'è una colonna adatta):\n"
            "- date: colonna con la data dell'operazione\n"
            "- amount: colonna con l'importo della spesa (numero, anche con segno/valuta). "
            "Se ci sono due colonne separate tipo 'Uscite'/'Entrate' o 'Dare'/'Avere', scegli SEMPRE "
            "quella delle uscite/spese (Dare), mai quella delle entrate (Avere) — l'app traccia solo spese\n"
            "- description: colonna con causale/descrizione/note dell'operazione\n"
            "- category: colonna con una categoria di spesa già presente nel file (raro, spesso null)\n"
            "- account: colonna con nome conto/IBAN (raro, spesso null)\n\n"
            "Rispondi SOLO con un JSON valido, esempio: "
            '{"date": "Data operazione", "amount": "Importo", "description": "Causale", '
            '"category": null, "account": null}'
        )
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300,
            reasoning_effort="none",
        )
        import json as _json
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        ai_mapping = _json.loads(raw)
        for field in TARGET_FIELDS:
            col = ai_mapping.get(field)
            if col and col in columns:
                mapping[field] = col
    except Exception as e:
        logger.warning("AI mapping suggestion fallita, uso euristica: %s", e)

    return mapping


# ─── NORMALIZZAZIONE RIGHE ────────────────────────────────────────────────────

_AMOUNT_CLEAN_RE = re.compile(r"[^\d,.\-]")


def _parse_amount(raw: str) -> Optional[float]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = _AMOUNT_CLEAN_RE.sub("", s)
    if not s or s in ("-", "."):
        return None
    # Formato italiano "1.234,56" vs formato US "1,234.56"
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return round(float(s), 2)  # segno preservato: serve a distinguire spese da entrate
    except ValueError:
        return None


_ISO_DATE_RE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")

_IT_MONTHS = {
    "gen": 1, "gennaio": 1, "feb": 2, "febbraio": 2, "mar": 3, "marzo": 3,
    "apr": 4, "aprile": 4, "mag": 5, "maggio": 5, "giu": 6, "giugno": 6,
    "lug": 7, "luglio": 7, "ago": 8, "agosto": 8, "set": 9, "sett": 9, "settembre": 9,
    "ott": 10, "ottobre": 10, "nov": 11, "novembre": 11, "dic": 12, "dicembre": 12,
}
_IT_MONTH_DATE_RE = re.compile(r"^(\d{1,2})\s+([a-zA-Zà-ùÀ-Ù]+)\.?\s+(\d{4})$")


def _parse_date(raw: str) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None

    # Fast path: formato ISO YYYY-MM-DD (es. quello usato dall'export di FinCopilot stesso)
    # è già inequivocabile — va parsato direttamente, MAI passato a dateutil con dayfirst=True.
    # dateutil applica l'euristica dayfirst anche a stringhe ISO quando giorno e mese sono
    # entrambi <=12 (es. "2026-08-03" letto come 2026-03-08, mese e giorno scambiati), e se
    # il giorno "swappato" supera 12 (es. "2026-08-30" -> mese 30) l'intera riga viene persa
    # come data non valida invece che semplicemente interpretata correttamente.
    m = _ISO_DATE_RE.match(s)
    if m:
        try:
            d = _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if d > _date.today():
                return None
            return d.isoformat()
        except ValueError:
            return None  # es. "2026-13-40": non è comunque una data valida in nessun verso

    # "1 gen 2026" / "28 gennaio 2026" (formato usato es. da Revolut in locale it-it): dateutil
    # non riconosce i nomi dei mesi italiani (solo inglesi), e con fuzzy=True silenziosamente
    # scarta il token del mese come "rumore" riempiendo il giorno mancante con la data di OGGI
    # — risultato: date completamente inventate invece di un errore esplicito. Va intercettato
    # PRIMA di arrivare a dateutil.
    m = _IT_MONTH_DATE_RE.match(s)
    if m:
        day, month_name, year = m.groups()
        month_num = _IT_MONTHS.get(month_name.lower().rstrip("."))
        if month_num is None:
            return None
        try:
            d = _date(int(year), month_num, int(day))
            if d > _date.today():
                return None
            return d.isoformat()
        except ValueError:
            return None

    try:
        d = dateutil_parser.parse(s, dayfirst=True, fuzzy=True)
        if d.date() > _date.today():
            return None  # scarta date future — probabile errore di parsing
        return d.date().isoformat()
    except Exception:
        return None


def normalize_row(
    row: dict, mapping: dict[str, Optional[str]], allowed_categories: Optional[list[str]] = None
) -> Optional[dict]:
    """Applica il mapping a una riga raw del file. Ritorna None se date/amount
    non sono validi (riga scartata, verrà segnalata come errore all'utente).
    allowed_categories: standard + personalizzate attive dell'utente (default: solo standard,
    per compatibilità con chi chiama senza passarle)."""
    allowed = allowed_categories if allowed_categories is not None else CATEGORIES
    date_col = mapping.get("date")
    amount_col = mapping.get("amount")
    if not date_col or not amount_col:
        return None

    tx_date = _parse_date(row.get(date_col, ""))
    amount = _parse_amount(row.get(amount_col, ""))
    if tx_date is None or amount is None or amount == 0:
        return None

    desc_col = mapping.get("description")
    cat_col = mapping.get("category")
    acc_col = mapping.get("account")

    description = str(row.get(desc_col, "")).strip() if desc_col else ""
    category = str(row.get(cat_col, "")).strip().lower() if cat_col else ""
    if category not in allowed:
        category = ""
    account = str(row.get(acc_col, "")).strip() if acc_col else "principale"

    return {
        "date": tx_date,
        "amount": amount,  # segno preservato — la distinzione spesa/entrata avviene a valle
        "description": description,
        "category": category,  # "" → verrà categorizzata dall'AI
        "account": account or "principale",
    }


def split_expenses_and_income(rows: list[dict]) -> tuple[list[dict], int]:
    """FinCopilot traccia solo le spese. Se la colonna importo del file mescola segni
    positivi e negativi (tipico di un estratto conto con entrate e uscite insieme),
    tiene solo gli importi negativi (le uscite) e scarta quelli positivi (entrate:
    stipendi, bonifici in entrata, ecc.). Se invece nel file compare un solo segno
    (es. alcuni export contengono già solo le uscite, magari tutte positive), non
    scarta nulla: non c'è modo di distinguere spesa da entrata solo dal segno.
    Ritorna (righe_spesa con amount reso positivo, numero_di_righe_scartate_come_entrata)."""
    has_negative = any(r["amount"] < 0 for r in rows)
    has_positive = any(r["amount"] > 0 for r in rows)

    if has_negative and has_positive:
        kept = [r for r in rows if r["amount"] < 0]
        skipped = len(rows) - len(kept)
    else:
        kept = rows
        skipped = 0

    for r in kept:
        r["amount"] = abs(r["amount"])

    return kept, skipped


def categorize_batch(descriptions: list[str], categories: Optional[list[str]] = None) -> list[str]:
    """Categorizza in batch le descrizioni senza categoria mappata, via AI (T-003).
    In caso di errore/assenza API key, ritorna 'altro' per tutte.
    categories: standard + personalizzate attive dell'utente (default: solo standard)."""
    if not descriptions:
        return []
    allowed = categories if categories is not None else CATEGORIES
    try:
        from backend.core.ai_engine import client, MODEL, GROQ_API_KEY
        if not GROQ_API_KEY:
            return ["altro"] * len(descriptions)

        results: list[str] = []
        BATCH = 30
        for i in range(0, len(descriptions), BATCH):
            chunk = descriptions[i:i + BATCH]
            numbered = "\n".join(f"{j+1}. {d or '(senza descrizione)'}" for j, d in enumerate(chunk))
            prompt = (
                "Categorizza ciascuna di queste spese personali (una per riga, numerate) "
                f"in una di queste categorie: {', '.join(allowed)}.\n"
                "Rispondi SOLO con un array JSON di stringhe nello stesso ordine e stessa lunghezza "
                f"dell'input (esattamente {len(chunk)} elementi), es: [\"cibo\", \"trasporti\", ...]\n\n"
                f"{numbered}"
            )
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=1000,
                reasoning_effort="none",
            )
            import json as _json
            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
            cats = _json.loads(raw)
            if not isinstance(cats, list) or len(cats) != len(chunk):
                results.extend(["altro"] * len(chunk))
                continue
            results.extend([c if c in allowed else "altro" for c in cats])
        return results
    except Exception as e:
        logger.warning("AI categorization batch fallita: %s", e)
        return ["altro"] * len(descriptions)
