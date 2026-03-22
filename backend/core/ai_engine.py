import os
import json
import sqlite3
import io
import base64
import traceback
from datetime import datetime, timedelta

from openai import OpenAI

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL = "llama-3.3-70b-versatile"

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


def get_db_path() -> str:
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/fincopilot.db")
    return db_url.replace("sqlite:///", "")


def build_context(db_path: str) -> str:
    """Costruisce il contesto del DB per il prompt AI."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Schema
    schema = "transactions(id, amount, category, description, date, time, account, source, tags)"

    # Summary
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
        f"  - {c[0]}: {c[1]} transazioni, totale €{c[2]}, media €{c[3]}"
        for c in cat_stats
    )

    return f"""SCHEMA DB: {schema}

DATI DISPONIBILI:
- Totale transazioni: {total}
- Range date: {date_range[0]} → {date_range[1]}
- Totale speso: €{grand_total}
- Ultimi 30 giorni: €{last_30}

PER CATEGORIA:
{categories_str}"""


SYSTEM_PROMPT = """Sei un analista finanziario AI esperto.
Il tuo compito è rispondere a domande sulle spese personali dell'utente.

{context}

ISTRUZIONI:
1. Rispondi in italiano con insight chiari e actionable
2. Se servono dati dal DB, genera codice Python che:
   - Usa sqlite3 per connettersi a DB_PATH (variabile già disponibile)
   - Usa pandas per analisi
   - Se utile, genera un grafico matplotlib salvandolo con plt.savefig('chart.png', dpi=100, bbox_inches='tight')
   - Stampa i risultati con print()
3. Evidenzia pattern, outlier e anomalie rilevanti
4. Suggerisci 2-3 domande di follow-up pertinenti

RISPONDI SEMPRE IN QUESTO FORMATO JSON:
{{
  "answer": "Risposta testuale con insight",
  "python_code": "codice python opzionale (null se non serve)",
  "followup_questions": ["domanda 1", "domanda 2"]
}}

Rispondi SOLO con JSON valido, nessun testo extra prima o dopo."""


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
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()

    # Pulisci eventuale markdown wrapping
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "answer": raw,
            "python_code": None,
            "followup_questions": [],
        }

    return result


def execute_analysis_code(code: str) -> dict:
    """Esegue il codice Python generato dall'AI in modo sicuro."""
    db_path = get_db_path()
    chart_b64 = None
    output_lines = []

    # Cattura stdout
    old_stdout = io.StringIO()

    namespace = {
        "DB_PATH": db_path,
        "__builtins__": __builtins__,
    }

    try:
        import contextlib
        with contextlib.redirect_stdout(old_stdout):
            exec(code, namespace)

        output_lines = old_stdout.getvalue().strip().split("\n") if old_stdout.getvalue().strip() else []

        # Controlla se è stato generato un grafico
        chart_path = "chart.png"
        if os.path.exists(chart_path):
            with open(chart_path, "rb") as f:
                chart_b64 = base64.b64encode(f.read()).decode("utf-8")
            os.remove(chart_path)

    except Exception as e:
        output_lines = [f"Errore nell'esecuzione: {str(e)}"]

    return {
        "output": "\n".join(output_lines),
        "chart": chart_b64,
    }


def chat_with_ai(question: str, history=None) -> dict:
    """Pipeline completa: domanda → AI → eventuale esecuzione codice → risposta."""
    # 1. Genera analisi dall'AI
    ai_result = generate_analytics(question, history)

    answer = ai_result.get("answer", "")
    chart = None
    data_output = None
    followups = ai_result.get("followup_questions", [])

    # 2. Se c'è codice Python, eseguilo
    python_code = ai_result.get("python_code")
    if python_code:
        exec_result = execute_analysis_code(python_code)
        if exec_result["output"]:
            answer += "\n\n📊 **Risultati analisi:**\n" + exec_result["output"]
        if exec_result["chart"]:
            chart = exec_result["chart"]

    return {
        "answer": answer,
        "chart": chart,
        "data_table": None,
        "followup_questions": followups,
    }
