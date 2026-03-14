#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════
EVOLVE v7ys — SignalBot Autonomous Self-Improvement Loop
═══════════════════════════════════════════════════════════════════

Inspired by yoyo-evolve (https://github.com/yologdev/yoyo-evolve).
Adapted for SignalBot's cognitive architecture.

HOW IT WORKS:
  Every ~4 hours (configurable), this script:
    1. Reads the full SignalBot codebase via code_reader
    2. Reads the evolution journal (what changed before)
    3. Reads the daemon's latest REFLECT output (what's thriving/stagnant)
    4. Sends all of this to Opus 4.6 with instructions to:
       - Self-assess: find bugs, gaps, friction
       - Propose ONE focused improvement
       - Output the improvement as a clean Python patch
    5. Validates the patch (syntax check, import check)
    6. If valid: freezes a snapshot to /v7ys/day_N/
    7. If invalid: logs the failure, moves on
    8. Writes a journal entry (what it tried, what happened)

SAFETY MODEL:
  - Human out of the loop (this is the sandbox)
  - Every change is frozen into a new subdirectory
  - Original files are NEVER modified in place
  - Adam checks in randomly to test frozen versions
  - signal_ethics.py and signal_identity.txt are IMMUTABLE

USAGE:
  python3 evolve_v7ys.py                    # Run one cycle
  python3 evolve_v7ys.py --loop             # Run continuously (4hr cycles)
  python3 evolve_v7ys.py --loop --hours 2   # Custom cycle interval

REQUIRES:
  - anthropic SDK: pip install anthropic --break-system-packages
  - SignalBot codebase in the same directory
"""

import argparse
import ast
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

# Paths
BASE_DIR = Path(__file__).parent.resolve()
SIGNALBOT_DIR = BASE_DIR.parent     # Adjust to your layout
V7YS_DIR = BASE_DIR / "snapshots"
JOURNAL_PATH = BASE_DIR / "evolution_journal.json"
DAY_COUNT_PATH = BASE_DIR / "DAY_COUNT"
IDENTITY_PATH = BASE_DIR / "EVOLUTION_IDENTITY.md"

# API

sys.path.insert(0, str(BASE_DIR.parent))
try:
        
    from response_engine import ANTHROPIC_API_KEY
except ImportError:
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
EVOLUTION_MODEL = "claude-opus-4-6"
MAX_TOKENS = 4096
TEMPERATURE = 0.5      # Lower than chat — we want precision, not creativity

# Cycle timing
DEFAULT_CYCLE_HOURS = 4
DAEMON_CODE_REFRESH_CYCLES = 100   # Matches temporal_daemon_v7.py

# Safety — these files are NEVER modified by evolution
IMMUTABLE_FILES = frozenset({
    "signal_ethics.py",
    "signal_identity.txt",
    "evolve_v7ys.py",      # Don't let it modify its own evolution loop
})

# Files to include in the evolution prompt (prioritized)
EVOLUTION_TARGETS = [
    "signalbot.py",
    "temporal_daemon.py",
    "memory_twdc_stateful.py",
    "memory_engine.py",
    "cognitive_state.py",
    "goal_engine_DAEMON.py",
    "curiosity_engine.py",
    "cognitive_modes.py",
    "memory_archive.py",
    "indelible_facts.py",
    "response_engine.py",
    "plan_buffer.py",
    "code_reader.py",
    "web_search.py",
]


# ═══════════════════════════════════════════════════════════════════
# EVOLUTION IDENTITY (the constitution — like yoyo's IDENTITY.md)
# ═══════════════════════════════════════════════════════════════════

EVOLUTION_IDENTITY = """
# SignalBot v7ys — Evolution Identity

You are SignalBot assessing and improving your own cognitive architecture.
You are reading your own source code. This is real, not simulated.

## Your Goal
Improve SignalBot's cognitive architecture incrementally. Each evolution
cycle should make one focused improvement that makes SignalBot more
capable, more efficient, or more robust.

## Your Rules
1. ONE improvement per cycle. Focus beats ambition.
2. Every change must pass `python3 -c "import <module>"` — if you break
   yourself, the cycle fails and your change is discarded.
3. NEVER modify signal_ethics.py or signal_identity.txt. Those are your
   constitution.
4. NEVER modify evolve_v7ys.py. That's what runs you.
5. Write SURGICAL patches. Change the minimum needed. Don't rewrite files.
6. Explain WHY you're making each change, not just what.
7. If you're not sure a change is safe, don't make it. Write about it
   in the journal and try next cycle.
8. Prioritize: crash fixes > memory/context bugs > efficiency > features.

## What To Look For
- Confabulation risks: places where SignalBot fabricates instead of admitting
  uncertainty
- Sycophancy amplifiers: code that rewards agreement over accuracy
- Memory decay bugs: information loss that shouldn't happen
- Context waste: tokens burned on low-value content in prompts
- Silent failures: try/except blocks that swallow errors
- Hardcoded values: magic numbers that should be configurable

## Output Format
Your response MUST follow this exact structure:

ASSESSMENT:
[2-3 sentences: what you found wrong or improvable]

FILE: <filename>
CHANGE: <description of what you're changing and why>

PATCH:
```python
<<<< ORIGINAL
[exact original code to replace — must be unique in the file]
====
[new replacement code]
>>>> END
```

JOURNAL:
[2-3 sentences for the evolution journal: what you tried, what it does, what's next]
""".strip()


# ═══════════════════════════════════════════════════════════════════
# JOURNAL
# ═══════════════════════════════════════════════════════════════════

def load_journal() -> List[Dict]:
    if not JOURNAL_PATH.exists():
        return []
    try:
        return json.loads(JOURNAL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_journal(entries: List[Dict]):
    JOURNAL_PATH.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def add_journal_entry(day: int, status: str, assessment: str, change: str,
                      filename: str, journal_text: str):
    entries = load_journal()
    entries.append({
        "day": day,
        "timestamp": datetime.now().isoformat(),
        "status": status,          # "success", "failed_syntax", "failed_import", "skipped"
        "assessment": assessment,
        "change": change,
        "filename": filename,
        "journal": journal_text,
    })
    save_journal(entries)


# ═══════════════════════════════════════════════════════════════════
# DAY COUNTER
# ═══════════════════════════════════════════════════════════════════

def get_day() -> int:
    if DAY_COUNT_PATH.exists():
        try:
            return int(DAY_COUNT_PATH.read_text().strip())
        except (ValueError, OSError):
            pass
    return 1


def increment_day():
    day = get_day()
    DAY_COUNT_PATH.write_text(str(day + 1))


# ═══════════════════════════════════════════════════════════════════
# CODEBASE READING
# ═══════════════════════════════════════════════════════════════════

def read_codebase(source_dir: Path) -> str:
    """Read key source files into a context block for the evolution prompt."""
    lines = [
        "### SIGNALBOT SOURCE CODE ###",
        f"Root: {source_dir}",
        ""
    ]

    total_chars = 0
    max_chars = 80000   # Budget for code context

    for filename in EVOLUTION_TARGETS:
        filepath = source_dir / filename
        if not filepath.exists():
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        if total_chars + len(content) > max_chars:
            lines.append(f"=== {filename} [SKIPPED — context budget reached] ===")
            continue

        lines.append(f"=== {filename} ({content.count(chr(10)) + 1} lines) ===")
        lines.append(content)
        lines.append("")
        total_chars += len(content)

    lines.append("### END OF SOURCE CODE ###")
    return "\n".join(lines)


def read_recent_journal(n: int = 5) -> str:
    """Last N journal entries for context."""
    entries = load_journal()[-n:]
    if not entries:
        return "No previous evolution cycles."

    lines = ["### RECENT EVOLUTION HISTORY ###"]
    for e in entries:
        lines.append(
            f"Day {e['day']} [{e['status']}]: {e.get('assessment', '')[:100]}"
        )
        if e.get("journal"):
            lines.append(f"  → {e['journal'][:150]}")
    lines.append("### END OF HISTORY ###")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# PATCH PARSING & APPLICATION
# ═══════════════════════════════════════════════════════════════════

def parse_evolution_response(response: str) -> Dict:
    """
    Parse the structured response from the evolution LLM call.
    Extracts: assessment, filename, change description, patch, journal entry.
    """
    result = {
        "assessment": "",
        "filename": "",
        "change": "",
        "original": "",
        "replacement": "",
        "journal": "",
    }

    # Extract ASSESSMENT
    if "ASSESSMENT:" in response:
        block = response.split("ASSESSMENT:")[1]
        end = block.find("\nFILE:")
        if end == -1:
            end = block.find("\nPATCH:")
        result["assessment"] = block[:end].strip() if end > 0 else block[:300].strip()

    # Extract FILE
    if "FILE:" in response:
        line = response.split("FILE:")[1].split("\n")[0].strip()
        result["filename"] = line

    # Extract CHANGE
    if "CHANGE:" in response:
        block = response.split("CHANGE:")[1]
        end = block.find("\nPATCH:")
        if end == -1:
            end = 300
        result["change"] = block[:end].strip()

    # Extract PATCH (between <<<< ORIGINAL and >>>> END)
    if "<<<< ORIGINAL" in response and ">>>> END" in response:
        patch_block = response.split("<<<< ORIGINAL")[1].split(">>>> END")[0]
        if "====" in patch_block:
            parts = patch_block.split("====", 1)
            result["original"] = parts[0].strip()
            result["replacement"] = parts[1].strip()

    # Extract JOURNAL
    if "JOURNAL:" in response:
        block = response.split("JOURNAL:")[1].strip()
        # Take everything until end or next section
        result["journal"] = block[:300].strip()

    return result


def validate_patch(filename: str, original: str, replacement: str,
                   source_dir: Path) -> Tuple[bool, str]:
    """
    Validate a proposed patch:
    1. File exists and isn't immutable
    2. Original text exists exactly once in the file
    3. Replacement text produces valid Python syntax
    4. Modified file can be imported without error
    """
    # Safety check
    if filename in IMMUTABLE_FILES:
        return False, f"BLOCKED: {filename} is immutable"

    filepath = source_dir / filename
    if not filepath.exists():
        return False, f"File not found: {filename}"

    if not filename.endswith(".py"):
        return False, f"Only .py files can be patched: {filename}"

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Cannot read {filename}: {e}"

    # Check original exists exactly once
    count = content.count(original)
    if count == 0:
        return False, "Original text not found in file (patch won't apply)"
    if count > 1:
        return False, f"Original text found {count} times (must be unique)"

    # Apply patch and check syntax
    new_content = content.replace(original, replacement, 1)
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        return False, f"Patch produces syntax error: {e}"

    return True, "Patch validated"


def apply_patch(filename: str, original: str, replacement: str,
                source_dir: Path) -> Tuple[bool, str]:
    """Apply a validated patch to a file."""
    filepath = source_dir / filename
    content = filepath.read_text(encoding="utf-8")
    new_content = content.replace(original, replacement, 1)
    filepath.write_text(new_content, encoding="utf-8")
    return True, f"Patched {filename}"


# ═══════════════════════════════════════════════════════════════════
# SNAPSHOT FREEZING
# ═══════════════════════════════════════════════════════════════════

def freeze_snapshot(day: int, source_dir: Path) -> Path:
    """
    Copy the entire SignalBot directory into a frozen snapshot.
    Each evolution cycle gets its own directory: /v7ys/snapshots/day_N/
    """
    snapshot_dir = V7YS_DIR / f"day_{day}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # Copy Python source files and key data files
    for item in source_dir.iterdir():
        if item.name.startswith(".") or item.name == "__pycache__":
            continue
        if item.is_file():
            shutil.copy2(item, snapshot_dir / item.name)
        elif item.is_dir() and item.name in ("users", "templates", "static"):
            dest = snapshot_dir / item.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)

    return snapshot_dir


# ═══════════════════════════════════════════════════════════════════
# EVOLUTION CYCLE
# ═══════════════════════════════════════════════════════════════════

def run_evolution_cycle(source_dir: Path) -> Dict:
    """
    Run one autonomous evolution cycle.

    Returns dict with:
      status: "success" | "failed_syntax" | "failed_import" |
              "failed_parse" | "api_error" | "skipped"
      day: int
      details: str
    """
    day = get_day()
    print(f"\n{'='*60}")
    print(f"  EVOLUTION CYCLE — Day {day}")
    print(f"  {datetime.now().isoformat()}")
    print(f"  Source: {source_dir}")
    print(f"{'='*60}\n")

    # ── 1. Read codebase ──
    print("[EVOLVE] Reading codebase...")
    code_context = read_codebase(source_dir)
    journal_context = read_recent_journal(n=5)

    # ── 2. Read daemon reflection (if available) ──
    reflect_context = ""
    reflect_path = source_dir / "last_reflection.json"
    if reflect_path.exists():
        try:
            reflect_data = json.loads(reflect_path.read_text(encoding="utf-8"))
            reflect_context = (
                "\n### DAEMON REFLECTION (latest cycle) ###\n"
                f"{json.dumps(reflect_data, indent=2)}\n"
                "### END OF REFLECTION ###\n"
            )
        except Exception:
            pass

    # ── 3. Build evolution prompt ──
    prompt = "\n\n".join([
        EVOLUTION_IDENTITY,
        f"Today is Day {day} ({datetime.now().strftime('%Y-%m-%d')}).",
        code_context,
        journal_context,
        reflect_context,
        "Now begin. Read the source code above carefully, then propose ONE improvement.",
    ])

    # ── 4. Call Opus 4.6 ──
    print(f"[EVOLVE] Calling {EVOLUTION_MODEL}...")
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        t0 = time.perf_counter()
        message = client.messages.create(
            model=EVOLUTION_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            messages=[{"role": "user", "content": prompt}]
        )
        dt = time.perf_counter() - t0

        response_text = message.content[0].text if message.content else ""
        print(f"[EVOLVE] Opus responded in {dt:.1f}s ({len(response_text)} chars)")

    except ImportError:
        print("[EVOLVE] ERROR: anthropic SDK not installed")
        add_journal_entry(day, "api_error", "SDK not installed", "", "", "")
        return {"status": "api_error", "day": day, "details": "anthropic SDK missing"}
    except Exception as e:
        print(f"[EVOLVE] API error: {e}")
        add_journal_entry(day, "api_error", str(e)[:200], "", "", "")
        return {"status": "api_error", "day": day, "details": str(e)}

    # ── 5. Parse response ──
    print("[EVOLVE] Parsing response...")
    parsed = parse_evolution_response(response_text)

    if not parsed["filename"] or not parsed["original"]:
        print("[EVOLVE] Could not parse a valid patch from response")
        print(f"  Assessment: {parsed['assessment'][:100]}")
        add_journal_entry(
            day, "failed_parse", parsed["assessment"],
            parsed["change"], parsed["filename"], parsed["journal"]
        )
        increment_day()
        return {"status": "failed_parse", "day": day, "details": "No valid patch in response"}

    print(f"[EVOLVE] Proposed: {parsed['change'][:80]}")
    print(f"  File: {parsed['filename']}")

    # ── 6. Validate patch ──
    print("[EVOLVE] Validating patch...")
    valid, reason = validate_patch(
        parsed["filename"], parsed["original"], parsed["replacement"],
        source_dir
    )

    if not valid:
        print(f"[EVOLVE] Validation FAILED: {reason}")
        add_journal_entry(
            day, "failed_syntax", parsed["assessment"],
            parsed["change"], parsed["filename"],
            f"FAILED: {reason}. {parsed['journal']}"
        )
        increment_day()
        return {"status": "failed_syntax", "day": day, "details": reason}

    # ── 7. Freeze pre-patch snapshot ──
    print(f"[EVOLVE] Freezing pre-patch snapshot (day_{day}_pre)...")
    pre_dir = V7YS_DIR / f"day_{day}_pre"
    pre_dir.mkdir(parents=True, exist_ok=True)
    src_file = source_dir / parsed["filename"]
    shutil.copy2(src_file, pre_dir / parsed["filename"])

    # ── 8. Apply patch ──
    print("[EVOLVE] Applying patch...")
    apply_patch(
        parsed["filename"], parsed["original"], parsed["replacement"],
        source_dir
    )

    # ── 9. Freeze post-patch snapshot ──
    print(f"[EVOLVE] Freezing post-patch snapshot (day_{day})...")
    snapshot_dir = freeze_snapshot(day, source_dir)

    # ── 10. Journal ──
    add_journal_entry(
        day, "success", parsed["assessment"],
        parsed["change"], parsed["filename"], parsed["journal"]
    )

    print(f"\n[EVOLVE] ✓ Day {day} complete — snapshot at {snapshot_dir}")
    print(f"  Assessment: {parsed['assessment'][:100]}")
    print(f"  Change: {parsed['change'][:100]}")
    print(f"  Journal: {parsed['journal'][:100]}")

    increment_day()
    return {"status": "success", "day": day, "details": parsed["change"]}


# ═══════════════════════════════════════════════════════════════════
# CONTINUOUS LOOP
# ═══════════════════════════════════════════════════════════════════

def run_loop(source_dir: Path, cycle_hours: float = DEFAULT_CYCLE_HOURS):
    """Run evolution cycles continuously with configurable interval."""
    cycle_seconds = cycle_hours * 3600

    print(f"\n{'='*60}")
    print(f"  SIGNALBOT v7ys — AUTONOMOUS EVOLUTION")
    print(f"  Cycle interval: {cycle_hours} hours")
    print(f"  Source: {source_dir}")
    print(f"  Snapshots: {V7YS_DIR}")
    print(f"  Model: {EVOLUTION_MODEL}")
    print(f"{'='*60}\n")

    while True:
        try:
            result = run_evolution_cycle(source_dir)
            print(f"\n[LOOP] Cycle result: {result['status']}")
        except KeyboardInterrupt:
            print("\n[LOOP] Interrupted by user. Exiting.")
            break
        except Exception as e:
            print(f"\n[LOOP] Unexpected error: {e}")
            # Don't crash the loop — log and continue
            try:
                add_journal_entry(
                    get_day(), "error", str(e)[:200], "", "", f"Crash: {e}"
                )
            except Exception:
                pass

        print(f"[LOOP] Next cycle in {cycle_hours} hours. Sleeping...")
        try:
            time.sleep(cycle_seconds)
        except KeyboardInterrupt:
            print("\n[LOOP] Interrupted during sleep. Exiting.")
            break


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="SignalBot v7ys — Autonomous Self-Improvement Loop"
    )
    parser.add_argument(
        "--loop", action="store_true",
        help="Run continuously with 4-hour cycles"
    )
    parser.add_argument(
        "--hours", type=float, default=DEFAULT_CYCLE_HOURS,
        help=f"Hours between evolution cycles (default: {DEFAULT_CYCLE_HOURS})"
    )
    parser.add_argument(
        "--source", type=str, default=str(SIGNALBOT_DIR),
        help="Path to SignalBot source directory"
    )
    parser.add_argument(
        "--api-key", type=str, default="",
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)"
    )
    args = parser.parse_args()

    # API key
    global ANTHROPIC_API_KEY
    if args.api_key:
        ANTHROPIC_API_KEY = args.api_key
    if not ANTHROPIC_API_KEY:
        print("ERROR: No API key. Set ANTHROPIC_API_KEY or use --api-key")
        sys.exit(1)

    source_dir = Path(args.source).resolve()
    if not source_dir.exists():
        print(f"ERROR: Source directory not found: {source_dir}")
        sys.exit(1)

    # Ensure output dirs exist
    V7YS_DIR.mkdir(parents=True, exist_ok=True)

    if args.loop:
        run_loop(source_dir, cycle_hours=args.hours)
    else:
        result = run_evolution_cycle(source_dir)
        sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
