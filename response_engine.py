# response_engine.py
"""
Multi-model response engine supporting both Ollama and Anthropic API
"""

from __future__ import annotations
import time
import os
from typing import Any, Dict
import requests

# Model configuration
USE_ANTHROPIC = False  # Set to False to use Ollama
ANTHROPIC_API_KEY = "YOUR_KEY_HERE"  # Replace with your actual key
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"  # or claude-opus-4-20250514

# Ollama config (fallback)
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma2:2b"

# Timeouts
CONNECT_TIMEOUT = 2
READ_TIMEOUT = 600

# Performance knobs
NUM_CTX = 1200
NUM_PREDICT = 1200
TEMPERATURE = 0.7


def generate_response(prompt: str) -> str:
    """Generate response using either Anthropic or Ollama."""
    
    if USE_ANTHROPIC:
        return _generate_anthropic(prompt)
    else:
        return _generate_ollama(prompt)


def _generate_anthropic(prompt: str) -> str:
    """Call Anthropic API."""
    try:
        from anthropic import Anthropic
        
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        
        t0 = time.perf_counter()
        
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1200,
            temperature=TEMPERATURE,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        dt_ms = (time.perf_counter() - t0) * 1000
        
        text = message.content[0].text if message.content else ""
        
        print(f"[LLM] Anthropic ok in {dt_ms:.1f} ms | model={ANTHROPIC_MODEL}")
        
        if not text:
            return "[GROUND] Anthropic returned empty response."
        
        return text
        
    except ImportError:
        return "[GROUND] Anthropic SDK not installed. Run: pip install anthropic --break-system-packages"
    except Exception as e:
        return f"[GROUND] Anthropic API error: {e}"


def _generate_ollama(prompt: str) -> str:
    """Call Ollama (original implementation)."""
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

        if not text:
            return "[GROUND] Ollama returned an empty response."

        return text

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
