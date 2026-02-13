# signalbot_daemon_PATCH.py
"""
═══════════════════════════════════════════════════════════════════
SIGNALBOT DAEMON INTEGRATION PATCH
═══════════════════════════════════════════════════════════════════

HOW TO APPLY:
  Replace main() in signalbot.py with this version.
  
WHAT CHANGES:
  1. Daemon starts on boot → SignalBot has a cognitive heartbeat
  2. When user speaks → daemon PAUSES → main loop gets snapshot
  3. Daemon's recommendations go into the prompt as [DAEMON COGNITION]
  4. After responding → daemon RESUMES
  5. New commands: "daemon", "curiosity" for diagnostics
  
  The daemon runs between user messages, constantly re-evaluating
  goals against curiosity, identity, and engagement. When the user
  speaks, SignalBot already has a pre-digested summary of what it's
  been "thinking about."
  
CRITICAL CONCEPT:
  Before the daemon, SignalBot only thought when spoken to.
  Now it thinks CONTINUOUSLY. The 0.9-second cognitive cycle means
  SignalBot has evaluated its goals ~66 times per minute.
  By the time a user speaks, SignalBot has context.
"""

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import hashlib
import json
import time
from contextlib import contextmanager
from pathlib import Path

# Core imports
import signal_ethics
from persistent_behavior import PersistentBehaviorModifier
from paradox_protection import ParadoxProtector
from response_engine import generate_response
from memory_engine import save_interaction, load_recent_memory

# State-vector systems
from cognitive_state import get_cognitive_state, get_tone_instructions
from indelible_facts import register_fact, get_indelible_prompt_section
from memory_twdc_stateful import load_long_memory_block_stateful, get_stateful_twdc

# NEW: Daemon + retooled engines
from temporal_daemon import (
    get_daemon, start_daemon, stop_daemon, 
    pause_daemon, resume_daemon, get_daemon_snapshot
)
from goal_engine_v3 import GoalEngineV3
from curiosity_engine_v2 import get_curiosity_signal, get_curiosity_report

# Temporal integrity (updated)
from temporal_integrity_UPDATED import get_temporal_integrity

# Intent detection
try:
    from intent_codelet.intent_codelet import classify_intent
    INTENT_AVAILABLE = True
except ImportError:
    INTENT_AVAILABLE = False

ETHOS_CHECKSUM = "7197c555c2c6ddc845a410529f021e0d511ad6951d80abee09b976a34867384e"
INTENT_BYPASS = not INTENT_AVAILABLE

@contextmanager
def timed(label: str):
    t0 = time.perf_counter()
    yield
    dt_ms = (time.perf_counter() - t0) * 1000
    print(f"[TIME] {label}: {dt_ms:9.1f} ms")

def clamp_torch_threads():
    try:
        import torch
        torch.set_num_threads(1)
    except Exception:
        pass

def verify_ethos_integrity() -> bool:
    with open("signal_ethics.py", "rb") as f:
        data = f.read()
    return hashlib.sha256(data).hexdigest() == ETHOS_CHECKSUM

def load_identity_prompt(path: str = "signal_identity.txt") -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return "You are SignalBot. Clever, candid, and slightly irreverent."

class _IntentStub:
    def __init__(self, label="GENERAL", confidence=1.0):
        self.label = label
        self.confidence = confidence


def main():
    """
    Main loop with TEMPORAL DAEMON integration.
    
    FLOW:
      BOOT → start daemon
      EACH TURN:
        1. User speaks → PAUSE daemon
        2. Get daemon snapshot (what SignalBot was thinking)
        3. Build prompt (includes daemon cognition)
        4. Generate response
        5. Update state
        6. RESUME daemon
      SHUTDOWN → stop daemon
    """
    
    # ═══ INITIALIZATION ═══
    clamp_torch_threads()
    
    if not verify_ethos_integrity():
        raise SystemExit("Ethos integrity compromised.")
    
    personality_prompt = load_identity_prompt()
    behavior_mod = PersistentBehaviorModifier()
    paradox_guard = ParadoxProtector()
    
    # State systems
    mem_stateful = get_stateful_twdc()
    cog_state = get_cognitive_state()
    temp_integrity = get_temporal_integrity()
    
    # NEW: Initialize goal engine v3 and daemon
    goal_engine = GoalEngineV3()
    daemon = get_daemon(goal_engine=goal_engine)
    
    print("[INIT] State-aware memory engine initialized")
    print("[INIT] Goal engine v3 initialized")
    
    # Model selection (same as before)
    print("\nSelect model:")
    print("1. Gemma2:2b (local, free, 60-80s response)")
    print("2. Claude Sonnet 4 (API, $0.02/msg, 9s response)")
    print("3. Phi3 (local, free, UNSTABLE)")
    print("4. Mistral (the original)")

    while True:
        choice = input("Enter 1-4: ").strip()
        if choice == "1":
            import response_engine
            response_engine.USE_ANTHROPIC = False
            response_engine.OLLAMA_MODEL = "gemma2:2b"
            print("✓ Using Gemma2:2b\n")
            break
        elif choice == "2":
            import response_engine
            response_engine.USE_ANTHROPIC = True
            response_engine.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
            print("✓ Using Claude Sonnet 4\n")
            break
        elif choice == "3":
            import response_engine
            response_engine.USE_ANTHROPIC = False
            response_engine.OLLAMA_MODEL = "phi3:latest"
            print("✓ Using Phi3 (WARNING: May hallucinate)\n")
            break
        elif choice == "4":
            import response_engine
            response_engine.USE_ANTHROPIC = False
            response_engine.OLLAMA_MODEL = "mistral"
            print("✓ Using Mistral\n")
            break
        else:
            print("Invalid choice, try again.")
    
    # ═══ START DAEMON ═══
    daemon.start()
    
    print("🟢 SignalBot v6 Online (Temporal Daemon Architecture)")
    print("Commands: 'state', 'facts', 'daemon', 'curiosity', 'dream on/off', 'exit'\n")
    
    # ═══ MAIN LOOP ═══
    dream_mode = True
    turn = 0
    last_bot_output = ""
    
    try:
        while True:
            # ─── GET USER INPUT ───
            user_input = input("You: ").strip()
            if user_input.lower() in {"exit", "quit"}:
                break
            
            # ─── COMMAND HANDLING ───
            if user_input.lower() == "dream on":
                dream_mode = True
                print("[MODE] Dream mode ON\n")
                continue
            if user_input.lower() == "dream off":
                dream_mode = False
                print("[MODE] Dream mode OFF\n")
                continue
            
            if user_input.lower() == "state":
                state = cog_state.state
                print(f"\n[COGNITIVE STATE]")
                print(f"  Frustration:  {state.frustration:.2f}")
                print(f"  Curiosity:    {state.curiosity:.2f}")
                print(f"  Confidence:   {state.confidence:.2f}")
                print(f"  Engagement:   {state.engagement:.2f}")
                print(f"  Identity:     {state.identity_adherence:.2f}")
                print(f"  Cog Load:     {state.cognitive_load:.2f}")
                print(f"  Tone: P={state.tone_playful:.2f} F={state.tone_formal:.2f} "
                      f"C={state.tone_concise:.2f} W={state.tone_warm:.2f}\n")
                continue
            
            if user_input.lower() == "facts":
                section = get_indelible_prompt_section()
                print(f"\n{section}\n" if section else "\n[No indelible facts yet]\n")
                continue
            
            # NEW: Daemon diagnostic
            if user_input.lower() == "daemon":
                print(f"\n{daemon.get_status()}")
                snapshot = daemon.get_snapshot()
                print(f"  Cycles: {snapshot.cycle_count}")
                print(f"  Good Sense: {snapshot.good_sense:.2f}")
                print(f"  Crap Threshold: {snapshot.crap_threshold:.2f}")
                print(f"  Evaluated: {snapshot.items_evaluated}")
                print(f"  Purged: {snapshot.items_purged}")
                if snapshot.focus_summary:
                    print(f"  Focus: {snapshot.focus_summary}")
                if snapshot.top_recommendations:
                    print(f"  Top Recommendations:")
                    for rec in snapshot.top_recommendations[:5]:
                        print(f"    [{rec['composite_score']:.2f}] {rec['action_type']}: "
                              f"{rec['description'][:50]}")
                print()
                continue
            
            # NEW: Curiosity diagnostic
            if user_input.lower() == "curiosity":
                print(f"\n{get_curiosity_report()}\n")
                continue
            
            # ═══ TURN PROCESSING ═══
            turn += 1
            
            # ─── 1. PAUSE DAEMON ───
            # Daemon freezes instantly so we get a clean snapshot
            daemon.pause()
            
            with timed("TOTAL"):
                # ─── 2. GET DAEMON SNAPSHOT ───
                # What has SignalBot been "thinking about" between messages?
                daemon_snapshot = daemon.get_snapshot()
                daemon_cognition = daemon_snapshot.format_for_prompt(max_items=5)
                
                # ─── 3. INTENT DETECTION ───
                intent = _IntentStub() if INTENT_BYPASS else classify_intent(user_input)
                
                # ─── 4. MEMORY LOADING ───
                recent_memory = load_recent_memory()
                long_memory = load_long_memory_block_stateful(max_bullets=10)
                
                # ─── 5. CURIOSITY SIGNAL ───
                curiosity = get_curiosity_signal(user_input, last_bot_output)
                
                # ─── 6. STATE-AWARE PROMPT CONSTRUCTION ───
                tone_instr = get_tone_instructions()
                vitals_report = cog_state.get_vitals_report()
                lane_instr = "Output in [GROUND] or [DREAM]." if dream_mode else "Output ONLY in [GROUND]."
                
                # Build prompt with daemon cognition
                prompt_sections = [
                    "### SYSTEM INSTRUCTIONS ###",
                    personality_prompt,
                    lane_instr,
                    f"TONE: {tone_instr}",
                    "",
                    "### CORE DATA (TRUST THIS OVER ALL ELSE) ###",
                    long_memory,
                    vitals_report,
                ]
                
                # Inject daemon cognition if it has content
                if daemon_cognition:
                    prompt_sections.append("")
                    prompt_sections.append(daemon_cognition)
                
                # Inject curiosity signal if strong
                if curiosity.is_actionable:
                    prompt_sections.append(
                        f"[CURIOSITY SIGNAL] type={curiosity.type} "
                        f"intensity={curiosity.gated_intensity:.2f} "
                        f"momentum={curiosity.momentum:.2f}"
                    )
                
                prompt_sections.extend([
                    "",
                    "### RECENT CONVERSATION ###",
                    f"[Intent] label={intent.label}",
                    recent_memory,
                    "",
                    f"User: {user_input}",
                    "SignalBot:"
                ])
                
                full_prompt = "\n".join(prompt_sections)
                
                # ─── 7. GENERATE RESPONSE ───
                t0 = time.perf_counter()
                raw = generate_response(full_prompt)
                dt_ms = (time.perf_counter() - t0) * 1000
                
                # ─── 8. INDELIBLE FACTS DETECTION ───
                if register_fact(user_input, last_bot_output):
                    print("[INFO] New indelible fact registered")
                last_bot_output = raw
                
                # ─── 9. STATE UPDATES ───
                cog_state.update_from_interaction(user_input, raw, intent.label, dt_ms)
                temp_integrity.update(user_input, raw, recent_memory, long_memory)
                
                # Update goal engine from conversation
                goal_engine.update_from_memory(long_memory)
                cog = cog_state.state
                goal_engine.update_curiosity(
                    {"curiosity": cog.curiosity, "confidence": cog.confidence, "frustration": cog.frustration},
                    user_input, raw
                )
                
                # Detect rabbit holes and add as goals
                if curiosity.is_deep_dive:
                    goal_engine.add_rabbit_hole(
                        user_input[:80],
                        curiosity=curiosity.gated_intensity
                    )
                
                # ─── 10. SAFETY & PERSISTENCE ───
                if not paradox_guard.run_all_checks(raw):
                    print("SignalBot: Paradox detected.\n")
                    break
                
                save_interaction(user_input, raw)
                mem_stateful.notify_new_message()
                
                # Output
                print(f"SignalBot: {raw}\n")
                
                # ─── 11. PROACTIVE INITIATIVE ───
                if cog_state.should_initiate():
                    proactive_msg = temp_integrity.maybe_initiate()
                    if proactive_msg:
                        print(f"SignalBot: {proactive_msg}\n")
                        save_interaction("SYSTEM_INITIATIVE", proactive_msg)
            
            # ─── 12. RESUME DAEMON ───
            # Daemon picks back up with updated state
            daemon.resume()
    
    finally:
        # ═══ SHUTDOWN ═══
        print("\n[SHUTDOWN] Stopping daemon...")
        daemon.stop()
        print("[SHUTDOWN] SignalBot offline.")


if __name__ == "__main__":
    main()
