## License

SignalBot is dual-licensed:

- **AGPL-3.0** for open source / research / personal use
- **Commercial license** for proprietary use or closed-source distribution

**Patent Pending:** Canadian Patent Application No. 3304098 filed March 6, 2026

For commercial licensing inquiries: crater_noggin@hotmail.com

# SignalBot v6.2 - Autonomous Cognitive Architecture

Temporal daemon with continuous background cognition.

## What's New in v6.2
- 9-phase daemon cycle (0.9s loop)
- Self-diagnostic capability
- Retooled goal/curiosity engines
- Proven stability (127-turn session)

## Prior Versions
- v5.2pgi: Unified state vectors, model agnosticism
- v4.1ML: TWDC memory implementation
- See CHANGELOG.md for full history

## Files
See source comments for architecture details.

## Dependencies
pip install requests numpy anthropic
ollama pull mistral:N phi3 gemma2:N

## Status
EXPERIMENTAL - Daemon integration working, needs extended testing.

My experiment layering cognitive overlays to create a stateful baseline in open source LLM models. Model agnostic.

run in .venv (python3 -m venv .venv)

source .venv/bin/activate

pip install numpy requests

python3 signalbot.py

## Notes
Claude API is ideal, low level cross session persistence across all models.  Watch out for Phi...it gets weird.

## System requirements
2-6 minute response time on a 10 year old laptop with no GPU.  20s-180s response time based on 4060 8gb and 16gb DDR5 on an intel i5-14400.
