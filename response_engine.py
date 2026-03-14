# response_engine.py
"""
Multi-model response engine supporting Anthropic, Mistral, and Ollama APIs
"""
from __future__ import annotations
import time
import os
from typing import Any, Dict
import requests

# ── Backend selector ──────────────────────────────────────────────────────────
# Set exactly one of these to True; the rest False. wAA
USE_ANTHROPIC = False
USE_MISTRAL   = False   # Falls through to Ollama if both above are False

# ── Anthropic config ──────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL   = "claude-haiku-4-5-20251001"  # or claude-opus-4-20250514 or claude-sonnet-4-20250514 or claude-opus-4-6

# ── Mistral config ────────────────────────────────────────────────────────────
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_MODEL   = "mistral-medium-latest"       # or mistral-small-latest, etc.
MISTRAL_URL     = "https://api.mistral.ai/v1/chat/completions"

# ── Ollama config (local fallback) ────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma2:2b"

# ── Shared knobs ──────────────────────────────────────────────────────────────
CONNECT_TIMEOUT = 2
READ_TIMEOUT    = 600
NUM_CTX         = int(os.environ.get("SIGNALBOT_NUM_CTX", "4096"))
NUM_PREDICT     = 1200
TEMPERATURE     = 0.7


def generate_response(prompt: str) -> str:
    """Generate response using the configured backend."""
    try:
        if USE_ANTHROPIC:
            return _generate_anthropic(prompt)
        elif USE_MISTRAL:
            return _generate_mistral(prompt)
        else:
            return _generate_ollama(prompt)
    except Exception as e:
        print(f"[LLM] UNCAUGHT ERROR in generate_response: {type(e).__name__}: {e}")
        return f"[GROUND] Response generation failed unexpectedly: {type(e).__name__}: {e}"


def _generate_anthropic(prompt: str) -> str:
    """Call Anthropic API."""
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        t0 = time.perf_counter()

        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=NUM_PREDICT,
            temperature=TEMPERATURE,
            messages=[{"role": "user", "content": prompt}]
        )

        dt_ms = (time.perf_counter() - t0) * 1000
        text = message.content[0].text if message.content else ""
        print(f"[LLM] Anthropic ok in {dt_ms:.1f} ms | model={ANTHROPIC_MODEL}")

        return text or "[GROUND] Anthropic returned empty response."

    except ImportError:
        return "[GROUND] Anthropic SDK not installed. Run: pip install anthropic --break-system-packages"
    except Exception as e:
        return f"[GROUND] Anthropic API error: {e}"


def _generate_mistral(prompt: str) -> str:
    """Call Mistral API."""
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MISTRAL_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": NUM_PREDICT,
        "temperature": TEMPERATURE,
    }
    t0 = time.perf_counter()
    try:
        resp = requests.post(
            MISTRAL_URL,
            headers=headers,
            json=payload,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        resp.raise_for_status()
        data = resp.json()
        text = (data["choices"][0]["message"]["content"] or "").strip()
        dt_ms = (time.perf_counter() - t0) * 1000
        print(f"[LLM] Mistral ok in {dt_ms:.1f} ms | model={MISTRAL_MODEL}")

        return text or "[GROUND] Mistral returned empty response."

    except requests.exceptions.ConnectionError:
        return "[GROUND] Can't connect to Mistral API."
    except requests.exceptions.Timeout:
        dt_ms = (time.perf_counter() - t0) * 1000
        return f"[GROUND] Mistral call timed out after {dt_ms:.0f} ms."
    except requests.exceptions.HTTPError as e:
        body = ""
        try:
            body = resp.text[:500]
        except Exception:
            pass
        return f"[GROUND] Mistral HTTP error: {e}\n{body}"
    except Exception as e:
        return f"[GROUND] Mistral error: {e}"


def _generate_ollama(prompt: str) -> str:
    """Call Ollama (local fallback)."""
    payload: Dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "temperature": TEMPERATURE,
        },
    }
    t0 = time.perf_counter()
    try:
        resp = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        resp.raise_for_status()
        data = resp.json()
        text = (data.get("response") or "").strip()
        dt_ms = (time.perf_counter() - t0) * 1000
        print(f"[LLM] Ollama ok in {dt_ms:.1f} ms | model={OLLAMA_MODEL}")

        return text or "[GROUND] Ollama returned an empty response."

    except requests.exceptions.ConnectionError:
        return "[GROUND] Can't connect to Ollama at localhost:11434."
    except requests.exceptions.Timeout:
        dt_ms = (time.perf_counter() - t0) * 1000
        return f"[GROUND] Ollama call timed out after {dt_ms:.0f} ms."
    except ValueError as e:
        return f"[GROUND] Ollama returned non-JSON output: {e}"
    except requests.exceptions.HTTPError as e:
        body = ""
        try:
            body = resp.text[:500]
        except Exception:
            pass
        return f"[GROUND] Ollama HTTP error: {e}\n{body}"
    except Exception as e:
        return f"[GROUND] LLM error: {e}"
