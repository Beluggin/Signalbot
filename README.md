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

## Status
EXPERIMENTAL - Daemon integration working, needs extended testing.

My experiment layering cognitive overlays to create a stateful baseline in open source LLM models. Model agnostic.

run in .venv (python3 -m venv .venv)

source .venv/bin/activate

pip install numpy requests

python3 signalbot.py

torch placeholder for when i actually get around to learning that

code is subject to rapid (possibly breaking) change. values need tweaking depending on system.

Feb 10 successfully tested Phi3 and gemma2:2b instead of Mistral7b. Signalbot definitely likes Phi3 least and gemma best.  Claude API is ideal, around 0.02 a message.
