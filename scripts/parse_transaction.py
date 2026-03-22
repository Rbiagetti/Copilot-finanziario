import os
import json
from openai import OpenAI

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

def parse_transaction(text: str) -> dict:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        temperature=0,
        max_tokens=100
    )
    raw = response.choices[0].message.content.strip()
    return json.loads(raw)

if __name__ == "__main__":
    tests = [
        "ho speso 12 euro caffè da Luca",
        "benzina 45€",
        "cena con amici 67 euro ristorante giapponese",
        "abbonamento netflix 13.99"
    ]
    print("\n🧪 Test parsing LLM\n" + "=" * 40)
    for text in tests:
        result = parse_transaction(text)
        print(f"\nInput:  {text}")
        print(f"Output: {result}")
