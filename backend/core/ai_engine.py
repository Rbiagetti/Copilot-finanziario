import os
import json
import sqlite3
import io
import base64
import tempfile
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

    schema = "transactions(id, amount REAL, category TEXT, description TEXT, date TEXT, time TEXT, account TEXT, source TEXT)"

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


SYSTEM_PROMPT = """Sei un analista finanziario personale. Rispondi in italiano, in modo CONCISO e diretto.

{context}

REGOLE:
1. Rispondi con max 2-3 frasi di insight. NON spiegare il codice o il processo.
2. GENERA SEMPRE codice Python quando servono dati dal DB o grafici.
3. Il codice Python DEVE:
   - Importare: import sqlite3, pandas as pd, matplotlib.pyplot as plt
   - DB_PATH e CHART_PATH sono variabili GIA' DEFINITE. NON ridefinirle! Usale direttamente:
     conn = sqlite3.connect(DB_PATH)
     plt.savefig(CHART_PATH, ...)
   - SEMPRE generare un grafico matplotlib:
     plt.figure(figsize=(10, 6))
     plt.style.use('dark_background')
     [... plot ...]
     plt.tight_layout()
     plt.savefig(CHART_PATH, dpi=100, bbox_inches='tight', facecolor='#1a1a2e')
     plt.close()
   - Stampare i dati chiave con print()
   - IMPORTANTE: NON fare DB_PATH = '...' o CHART_PATH = '...'. Sono gia' impostati!
4. Colori grafici: sfondo '#1a1a2e', griglia '#2a2a40', colori barre/linee da ['#6366f1','#f43f5e','#10b981','#f59e0b','#8b5cf6','#06b6d4','#ec4899','#f97316']
5. Suggerisci 2-3 follow-up

RISPONDI SOLO con JSON valido (no markdown, no backtick):
{{"answer": "insight conciso", "python_code": "codice completo", "followup_questions": ["q1", "q2"]}}

Se non servono dati dal DB, metti python_code: null."""


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
    """Rimuove ridefinizioni di DB_PATH e CHART_PATH dal codice generato."""
    import re
    lines = code.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip lines that reassign DB_PATH or CHART_PATH
        if re.match(r"^(DB_PATH|CHART_PATH)\s*=\s*['\"]", stripped):
            continue
        # Fix hardcoded savefig paths
        line = re.sub(
            r"plt\.savefig\(\s*['\"][^'\"]+['\"]\s*,",
            "plt.savefig(CHART_PATH,",
            line,
        )
        line = re.sub(
            r"plt\.savefig\(\s*['\"][^'\"]+['\"]\s*\)",
            "plt.savefig(CHART_PATH)",
            line,
        )
        cleaned.append(line)
    return "\n".join(cleaned)


def execute_analysis_code(code: str) -> dict:
    """Esegue il codice Python generato dall'AI in modo sicuro."""
    code = _sanitize_code(code)
    db_path = get_db_path()

    # Usa un file temporaneo per il chart
    chart_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    chart_path = chart_file.name
    chart_file.close()

    # Rimuovi il file vuoto, verra' creato da matplotlib
    os.remove(chart_path)

    chart_b64 = None
    output_lines = []

    namespace = {
        "DB_PATH": db_path,
        "CHART_PATH": chart_path,
        "__builtins__": __builtins__,
    }

    try:
        import contextlib
        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            exec(code, namespace)

        captured = stdout_capture.getvalue().strip()
        if captured:
            output_lines = captured.split("\n")

        # Controlla se e' stato generato un grafico
        if os.path.exists(chart_path):
            with open(chart_path, "rb") as f:
                chart_b64 = base64.b64encode(f.read()).decode("utf-8")
            os.remove(chart_path)

    except Exception as e:
        output_lines = [f"Errore: {str(e)}"]
        # Cleanup
        if os.path.exists(chart_path):
            os.remove(chart_path)

    return {
        "output": "\n".join(output_lines),
        "chart": chart_b64,
    }


def chat_with_ai(question: str, history=None) -> dict:
    """Pipeline completa: domanda -> AI -> esecuzione codice -> risposta."""
    ai_result = generate_analytics(question, history)

    answer = ai_result.get("answer", "")
    chart = None
    followups = ai_result.get("followup_questions", [])

    python_code = ai_result.get("python_code")
    if python_code:
        exec_result = execute_analysis_code(python_code)
        if exec_result["output"]:
            answer += "\n\n📊 **Dati:**\n" + exec_result["output"]
        if exec_result["chart"]:
            chart = exec_result["chart"]

    return {
        "answer": answer,
        "chart": chart,
        "data_table": None,
        "followup_questions": followups,
    }
