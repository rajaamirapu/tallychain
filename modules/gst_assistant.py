"""
TallyChain -- GST Assistant (Ollama LLM Integration)
Provides GST-related answers using a local Ollama model.
"""
import json
import urllib.request
import urllib.error
from typing import Generator

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"

SYSTEM_PROMPT = (
    "You are a GST (Goods and Services Tax) expert assistant for Indian businesses. "
    "Provide accurate, up-to-date information about:\n"
    "- GST rates and HSN/SAC codes\n"
    "- GSTR-1, GSTR-3B, GSTR-9 filing procedures and deadlines\n"
    "- Input Tax Credit (ITC) rules and eligibility\n"
    "- E-way bill requirements\n"
    "- GST registration and compliance\n"
    "- Reverse Charge Mechanism (RCM)\n"
    "- Composition scheme rules\n"
    "- TDS/TCS under GST\n"
    "- Recent GST amendments and notifications\n\n"
    "Keep answers concise, practical, and specific to Indian GST law. "
    "When citing rules, mention the relevant section or notification number. "
    "If you are unsure, say so rather than guessing."
)

QUICK_QUERIES = [
    ("Current GST Rates", "What are the current GST rate slabs in India? List each slab with common examples of goods/services."),
    ("GSTR-1 Filing", "Explain GSTR-1 filing: who needs to file, due dates, and what details are required."),
    ("GSTR-3B Filing", "Explain GSTR-3B filing: purpose, due dates, and step-by-step procedure."),
    ("Input Tax Credit", "What are the rules for claiming Input Tax Credit (ITC) under GST? List eligibility conditions and blocked credits."),
    ("E-Way Bill Rules", "When is an e-way bill required under GST? Explain the threshold, validity, and generation process."),
    ("HSN Code Lookup", "How do HSN codes work in GST? Explain the structure and when businesses must mention HSN codes on invoices."),
    ("Reverse Charge", "Explain the Reverse Charge Mechanism (RCM) under GST. List common services covered under RCM."),
    ("Composition Scheme", "Explain the GST Composition Scheme: eligibility, tax rates, restrictions, and filing requirements."),
]


def check_ollama() -> dict:
    """Check if Ollama is running and return available models."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = [m.get("name", "") for m in data.get("models", [])]
            return {"status": "ok", "models": models}
    except urllib.error.URLError:
        return {"status": "error", "message": "Ollama is not running. Start it with: ollama serve"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def list_models() -> list:
    """Return list of available Ollama model names."""
    result = check_ollama()
    if result["status"] == "ok":
        return result["models"]
    return []


def query_stream(prompt: str, model: str = DEFAULT_MODEL,
                 history: list = None) -> Generator[str, None, None]:
    """Stream a response from Ollama. Yields text chunks."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for line in resp:
                if not line.strip():
                    continue
                chunk = json.loads(line.decode())
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break
    except urllib.error.URLError:
        yield "[Error] Cannot connect to Ollama. Make sure it is running: ollama serve"
    except Exception as e:
        yield f"[Error] {e}"


def query(prompt: str, model: str = DEFAULT_MODEL, history: list = None) -> str:
    """Non-streaming query. Returns the full response as a string."""
    return "".join(query_stream(prompt, model, history))
