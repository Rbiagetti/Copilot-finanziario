import os
import json
import sqlite3
import io
from pathlib import Path

from openai import OpenAI

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL = "llama-3.3-70b-versatile"

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


def get_db_path() -> str:
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/fincopilot.db")
    path = db_url.replace("sqlite:///", "")
    return str(Path(path).resolve())


def build_context(db_path: str) -> str:
    """Costruisce il contesto del DB per il prompt AI."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    schema = "transactions(id, amount REAL, category TEXT, subcategory TEXT, description TEXT, date TEXT, time TEXT, account TEXT, tags TEXT, source TEXT, created_at TEXT, updated_at TEXT)"

    cur.execute("SELECT COUNT(*) FROM transactions")
    total = cur.fetchone()[0]

    cur.execute("SELECT MIN(date), MAX(date) FROM transactions")
    date_range = cur.fetchone()

    cur.execute(
        "SELECT category, COUNT(*), ROUND(SUM(amount),2), ROUND(AVG(amount),2) "
        "FROM transactions GROUP BY category ORDER BY SUM(amount) DESC"
    )
    cat_stats = cur.fetchall()

    cur.execute("SELECT ROUND(SUM(amount),2) FROM transactions")
    grand_total = cur.fetchone()[0] or 0

    cur.execute(
        "SELECT ROUND(SUM(amount),2) FROM transactions WHERE date >= date('now', '-30 days')"
    )
    last_30 = cur.fetchone()[0] or 0

    conn.close()

    categories_str = "\n".join(
        f"  - {c[0]}: {c[1]} tx, tot €{c[2]}, media €{c[3]}"
        for c in cat_stats
    )

    return f"""SCHEMA: {schema}
TOTALE: {total} transazioni, €{grand_total}, range {date_range[0]} → {date_range[1]}
ULTIMI 30GG: €{last_30}
CATEGORIE:
{categories_str}"""


SYSTEM_PROMPT = """Sei un analista finanziario AI avanzato. Rispondi in italiano, CONCISO e con insight actionable.

{context}

IL TUO RUOLO: Non sei un semplice calcolatore. Sei un consulente finanziario che trova pattern nascosti, anomalie e opportunita' di risparmio. Ogni risposta deve dare VALORE PRATICO all'utente.

TIPI DI ANALISI CHE SAI FARE:
- Trend e previsioni (confronti temporali, proiezioni fine mese)
- Anomalie (spese fuori media, picchi insoliti, pattern ripetitivi)
- Ottimizzazione (dove tagliare, categorie con crescita anomala)
- Comportamentale (weekend vs feriali, pattern orari, frequenza)
- Confronti (mese vs mese, categoria vs categoria)

REGOLE CODICE:
1. GENERA SEMPRE python_code per domande sui dati.
2. Il codice DEVE:
   - import sqlite3, json
   - conn = sqlite3.connect(DB_PATH)  # GIA' DEFINITO, NON ridefinirlo!
   - NON usare SELECT * — specifica le colonne
   - SEMPRE print("CHART_DATA:" + json.dumps(chart))
   - Formato: {{"type":"bar|pie|line","data":[{{"name":"...","value":N}}],"title":"..."}}
   - print() per dati chiave
   - NON usare matplotlib, pandas, plt. Solo sqlite3 e json.
3. OGNI python_code DEVE avere CHART_DATA. Nessuna eccezione.

REGOLE RISPOSTA:
1. Max 2-3 frasi con INSIGHT, non descrizioni. Esempio buono: "Stai spendendo il 40% in piu' in cibo rispetto al mese scorso. Il picco e' nei weekend." Esempio cattivo: "Ecco i dati delle tue spese."
2. Followup devono essere analisi AVANZATE, non domande banali. Esempi: "Simula un taglio del 20% su cibo", "Pattern spese impulsive dopo le 18:00", "Proiezione spese a fine trimestre"

ESEMPIO codice:
```
import sqlite3, json
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT category, SUM(amount) as tot FROM transactions WHERE date >= date('now','-30 days') GROUP BY category ORDER BY tot DESC")
rows = cur.fetchall()
conn.close()
chart = {{"type":"bar","data":[{{"name":r[0],"value":round(r[1],2)}} for r in rows],"title":"Spese per categoria (30gg)"}}
print("CHART_DATA:" + json.dumps(chart))
for r in rows:
    print(f"{{r[0]}}: €{{r[1]:.2f}}")
```

RISPONDI SOLO con JSON (no markdown, no backtick):
{{"answer": "insight actionable", "python_code": "codice", "followup_questions": ["analisi avanzata 1", "analisi avanzata 2"]}}

Se non servono dati, python_code: null."""


def generate_analytics(question: str, history=None) -> dict:
    """Chiama Groq LLM per generare analisi dalla domanda utente."""
    db_path = get_db_path()
    context = build_context(db_path)

    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(context=context)}]

    if history:
        for h in history[-4:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

    messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=2500,
    )

    raw = response.choices[0].message.content.strip()

    result = _parse_ai_response(raw)
    return result


def _parse_ai_response(raw: str) -> dict:
    """Parsing robusto della risposta AI in JSON."""
    import re

    # Rimuovi markdown wrapping
    cleaned = raw
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    # Tentativo 1: parse diretto
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Tentativo 2: trova il primo blocco JSON { ... } nel testo
    match = re.search(r'\{[\s\S]*\}', cleaned)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Tentativo 3: estrai campi manualmente con regex
    answer_match = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    code_match = re.search(r'"python_code"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    code_null = re.search(r'"python_code"\s*:\s*null', cleaned)

    if answer_match:
        answer = answer_match.group(1).replace('\\"', '"').replace('\\n', '\n')
        python_code = None
        if code_match:
            python_code = code_match.group(1).replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')
        followups = []
        fq_match = re.search(r'"followup_questions"\s*:\s*\[(.*?)\]', cleaned, re.DOTALL)
        if fq_match:
            followups = re.findall(r'"((?:[^"\\]|\\.)*)"', fq_match.group(1))
        return {
            "answer": answer,
            "python_code": python_code,
            "followup_questions": followups,
        }

    # Fallback: testo come answer
    return {
        "answer": raw,
        "python_code": None,
        "followup_questions": [],
    }


def _sanitize_code(code: str) -> str:
    """Rimuove ridefinizioni di DB_PATH e riferimenti matplotlib dal codice generato."""
    import re
    lines = code.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^DB_PATH\s*=\s*['\"]", stripped):
            continue
        if re.match(r"^CHART_PATH\s*=\s*['\"]", stripped):
            continue
        if "matplotlib" in stripped and "import" in stripped:
            continue
        if stripped.startswith("plt."):
            continue
        line = re.sub(
            r"plt\.savefig\([^)]*\)",
            "",
            line,
        )
        cleaned.append(line)
    return "\n".join(cleaned)


def execute_analysis_code(code: str) -> dict:
    """Esegue il codice Python generato dall'AI in modo sicuro."""
    code = _sanitize_code(code)
    db_path = get_db_path()

    chart_data = None
    output_lines = []

    namespace = {
        "DB_PATH": db_path,
        "__builtins__": __builtins__,
    }

    try:
        import contextlib
        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            exec(code, namespace)

        captured = stdout_capture.getvalue().strip()
        if captured:
            for line in captured.split("\n"):
                if line.startswith("CHART_DATA:"):
                    try:
                        chart_data = json.loads(line[len("CHART_DATA:"):])
                    except json.JSONDecodeError:
                        pass
                else:
                    output_lines.append(line)

    except Exception as e:
        output_lines = [f"Errore: {str(e)}"]

    # Fallback: se non c'e' CHART_DATA ma ci sono dati, prova a costruire un bar chart
    if not chart_data and output_lines:
        chart_data = _auto_chart_from_output(output_lines)

    return {
        "output": "\n".join(output_lines),
        "chart_data": chart_data,
    }


def _auto_chart_from_output(lines: list) -> dict:
    """Tenta di costruire un chart automatico dall'output del codice."""
    import re
    items = []
    for line in lines:
        if line.startswith("Errore"):
            continue
        # Cerca pattern come "categoria: €123.45" o "categoria 123.45"
        m = re.match(r'^[\s]*([^:€\d]+?)[\s:]+€?\s*([\d]+\.?\d*)', line)
        if m:
            name = m.group(1).strip().capitalize()
            value = float(m.group(2))
            if name and value > 0:
                items.append({"name": name, "value": round(value, 2)})
    if len(items) >= 2:
        return {"type": "bar", "data": items[:15], "title": "Analisi spese"}
    return None


def chat_with_ai(question: str, history=None) -> dict:
    """Pipeline completa: domanda -> AI -> esecuzione codice -> risposta."""
    ai_result = generate_analytics(question, history)

    answer = ai_result.get("answer", "")
    chart_data = None
    followups = ai_result.get("followup_questions", [])

    python_code = ai_result.get("python_code")
    if python_code:
        exec_result = execute_analysis_code(python_code)
        if exec_result["output"]:
            answer += "\n\n" + exec_result["output"]
        if exec_result["chart_data"]:
            chart_data = exec_result["chart_data"]

    return {
        "answer": answer,
        "chart_data": chart_data,
        "data_table": None,
        "followup_questions": followups,
    }
