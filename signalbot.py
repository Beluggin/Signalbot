# signalbot.py
"""
═══════════════════════════════════════════════════════════════════
SIGNALBOT v6.3 — Cognitive Mode Registry + Remember Mode
═══════════════════════════════════════════════════════════════════

FIX LOG:
  v6.0: Daemon ran empty, LLM didn't understand temporal experience
  v6.1: Boot seeding + prompt framing (daemon thinks, LLM knows)
  v6.2: Goal lifecycle — conversation topics feed into daemon,
        resolved topics retire, boot goals expire.
  v6.3: Cognitive Mode Registry — modes as immune response to
        cognitive insufficiency. Remember Mode for deep archive
        retrieval. Gap detection for future mode discovery.
        Memory archival compresses old turns into episodes.

COMMANDS:
  state     — cognitive state vectors + active modes
  facts     — learned indelible facts
  daemon    — daemon status + what it's been thinking
  curiosity — curiosity signal breakdown
  modes     — cognitive mode status + recent gaps
  archive   — archive stats + force archive
  dream on/off — toggle dream mode
  exit/quit — shutdown
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

import signal_ethics
from persistent_behavior import PersistentBehaviorModifier
from paradox_protection import ParadoxProtector
from response_engine import generate_response
from memory_engine import save_interaction, load_recent_memory

from cognitive_state import get_cognitive_state, get_tone_instructions
from indelible_facts import register_fact, get_indelible_prompt_section
from memory_twdc_stateful import load_long_memory_block_stateful, get_stateful_twdc
from plan_buffer import get_plan_buffer
from temporal_daemon import get_daemon
from goal_engine_DAEMON import GoalEngine as DaemonGoalEngine
from curiosity_engine import get_curiosity_signal, get_curiosity_report

from cognitive_modes import get_mode_engine
from memory_archive import archive_old_memories, get_archive_stats, force_archive_all

from temporal_integrity_UPDATED import get_temporal_integrity
from speech_interface_v2 import get_speech_interface, speak, listen_push_to_talk

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
        print(f"[Torch] num_threads={torch.get_num_threads()}")
    except Exception as e:
        print(f"[Torch] not available: {e}")

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
    # ═══ INITIALIZATION ═══
    clamp_torch_threads()

    if not verify_ethos_integrity():
        raise SystemExit("Ethos integrity compromised.")

    personality_prompt = load_identity_prompt()
    behavior_mod = PersistentBehaviorModifier()
    paradox_guard = ParadoxProtector()

    mem_stateful = get_stateful_twdc()
    cog_state = get_cognitive_state()
    temp_integrity = get_temporal_integrity()

    daemon_goals = DaemonGoalEngine()
    daemon = get_daemon(goal_engine=daemon_goals)
    mode_engine = get_mode_engine()
    buf = get_plan_buffer()

    print("[INIT] State-aware memory engine initialized")
    print("[INIT] Daemon goal engine initialized")
    print(f"[INIT] Cognitive mode engine initialized ({len(mode_engine._modes)} modes)")

    # Run archival on startup (compress old memories)
    archived = archive_old_memories()
    if archived > 0:
        mode_engine.refresh_archive_tags()
        print(f"[INIT] Archived {archived} episodes from old memory")
    speech = get_speech_interface()
    print("[INIT] Speech interface initialized")

    # Model selection
    print("\nSelect model:")
    print("1. Gemma2:2b (local, free, 60-180s response)")
    print("2. Claude Sonnet 4 (API, ~$0.02/msg, 10s response)")
    print("3. Phi3 (local, free, UNSTABLE)")
    print("4. Mistral 7b (local, free, 120-220s response, Signalbot's 2nd choice')")
    print("5. Llama 3.1 (Model too big, times out)")
    print("6. Mistral Medium (API, experimental)")
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
        elif choice == "5":
            import response_engine
            response_engine.USE_ANTHROPIC = False
            response_engine.OLLAMA_MODEL = "llama3.1:latest"
            print (" Using Llama 3.1")
            break
        elif choice == "6":
            import response_engine
            response_engine.USE_ANTHROPIC = False
            response_engine.USE_MISTRAL = True
            print ("Using Mistral Medium")
            break
        else:
            print("Invalid choice, try again.")

    # ═══ START DAEMON ═══
    daemon.start()

    print("🟢 SignalBot v6.3 Online (Cognitive Modes + Remember Mode)")
    print("Commands: 'state', 'facts', 'daemon', 'curiosity', 'modes', 'archive', 'plans', 'dream on/off', 'speech on/off', 'exit'\n")

    # ═══ MAIN LOOP ═══
    dream_mode = True
    speech_mode = False    
    turn = 0
    last_bot_output = ""

    try:
        while True:
            if speech_mode:
                print("You: ", end="", flush=True)
                user_input = listen(timeout=10.0)  # 10 second timeout
                if user_input is None:
                    print("(no speech detected, type instead)")
                    user_input = input().strip()
                else:
                    print(user_input)  # Show what was recognized
            else:
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
            if user_input.lower() == "speech on":
                if speech.enable():
                    speech_mode = True
                    speak("Speech mode enabled. I can hear and speak now.")
                else:
                    print("[ERROR] Speech system not available\n")
                continue

            if user_input.lower() == "speech off":
                speech.disable()
                speech_mode = False
                print("[MODE] Speech mode OFF\n")
                continue

            if user_input.lower() == "speech status":
                print(f"\n{speech.get_status()}\n")
                continue
            
            if user_input.lower() == "plans":
                print(f"get_plan_buffer().get_full_report()")
                continue

            if user_input.lower() == "state":
                s = cog_state.state
                print(f"\n[COGNITIVE STATE]")
                print(f"  Frustration:  {s.frustration:.2f}")
                print(f"  Curiosity:    {s.curiosity:.2f}")
                print(f"  Confidence:   {s.confidence:.2f}")
                print(f"  Engagement:   {s.engagement:.2f}")
                print(f"  Identity:     {s.identity_adherence:.2f}")
                print(f"  Cog Load:     {s.cognitive_load:.2f}")
                print(f"  Tone: P={s.tone_playful:.2f} F={s.tone_formal:.2f} "
                      f"C={s.tone_concise:.2f} W={s.tone_warm:.2f}")
                print(f"  {mode_engine.get_status()}\n")
                continue

            if user_input.lower() == "facts":
                section = get_indelible_prompt_section()
                print(f"\n{section}\n" if section else "\n[No indelible facts yet]\n")
                continue

            if user_input.lower() == "daemon":
                print(f"\n{daemon.get_status()}")
                snap = daemon.get_snapshot()
                print(f"  Cycles since last msg: {snap.cycle_count}")
                print(f"  Good Sense: {snap.good_sense:.2f}")
                print(f"  Crap Threshold: {snap.crap_threshold:.2f}")
                print(f"  Evaluated: {snap.items_evaluated}")
                print(f"  Purged (total): {snap.items_purged}")
                if snap.ambient_awareness:
                    print(f"  Ambient: {snap.ambient_awareness}")
                if snap.focus_summary:
                    print(f"  Focus: {snap.focus_summary}")
                if snap.top_recommendations:
                    print("  Top Recommendations:")
                    for rec in snap.top_recommendations[:5]:
                        print(f"    [{rec['composite_score']:.2f}] {rec['action_type']}: "
                              f"{rec['description'][:50]}")
                print()
                continue

            if user_input.lower() == "curiosity":
                print(f"\n{get_curiosity_report()}\n")
                continue

            if user_input.lower() == "modes":
                print(f"\n{mode_engine.get_status()}")
                active = mode_engine.get_active_modes()
                for m in active:
                    if m.mode_id == 0:
                        continue
                    print(f"  {m.name}: blend={m.blend_weight:.2f} "
                          f"activations={m.activation_count}")
                gaps = mode_engine.get_recent_gaps(3)
                if gaps:
                    print("  Recent gaps:")
                    for g in gaps:
                        print(f"    {g['description']} — \"{g['user_input'][:40]}\"")
                print()
                continue

            if user_input.lower() == "archive":
                stats = get_archive_stats()
                print(f"\n[ARCHIVE]")
                print(f"  Episodes: {stats['episodes']}")
                print(f"  Total turns archived: {stats['total_turns']}")
                print(f"  Unique tags: {stats.get('unique_tags', 0)}")
                if stats['episodes'] > 0:
                    print(f"  Oldest: {stats['oldest']}")
                    print(f"  Newest: {stats['newest']}")
                print()
                continue

            if user_input.lower() == "archive now":
                n = archive_old_memories()
                if n > 0:
                    mode_engine.refresh_archive_tags()
                print(f"\n[ARCHIVE] Created {n} new episodes\n")
                continue

            if user_input.lower() == "archive all":
                n = force_archive_all()
                if n > 0:
                    mode_engine.refresh_archive_tags()
                print(f"\n[ARCHIVE] Force-archived into {n} episodes\n")
                continue

            # ═══ TURN PROCESSING ═══
            turn += 1

            # ─── 1. PAUSE DAEMON ───
            daemon.pause()

            with timed("TOTAL"):
                # ─── 2. GET DAEMON SNAPSHOT ───
                daemon_snapshot = daemon.get_snapshot()
                daemon_cognition = daemon_snapshot.format_for_prompt(max_items=5)

                # ─── 3. INTENT DETECTION ───
                intent = _IntentStub() if INTENT_BYPASS else classify_intent(user_input)

                # ─── 4. MEMORY LOADING ───
                recent_memory = load_recent_memory()
                long_memory = load_long_memory_block_stateful(max_bullets=10)

                # ─── 4b. MODE RESONANCE CHECK (NEW in v6.3) ───
                # Detect if active memory is sufficient or if we need deeper retrieval
                active_memory_hit = any(
                    w in recent_memory.lower()
                    for w in user_input.lower().split()
                    if len(w) > 4
                )
                mode_result = mode_engine.process_turn(
                    user_input, last_bot_output,
                    active_memory_hit=active_memory_hit,
                    cog_state_frustration=cog_state.state.frustration,
                )
                archive_context = mode_result.get("archive_context", "")
                mode_prompt = mode_engine.format_for_prompt()

                # ─── 5. CURIOSITY SIGNAL ───
                curiosity = get_curiosity_signal(user_input, last_bot_output)

                # ─── 6. PROMPT CONSTRUCTION ───
                tone_instr = get_tone_instructions()
                vitals_report = cog_state.get_vitals_report()
                lane_instr = "Output in [GROUND] or [DREAM]." if dream_mode else "Output ONLY in [GROUND]."

                prompt_sections = [
                    "### SYSTEM INSTRUCTIONS ###",
                    personality_prompt,
                    lane_instr,
                    f"TONE: {tone_instr}",
                    "",
                    "### CORE DATA (TRUST THIS OVER ALL ELSE) ###",
                    long_memory,
                    vitals_report,
                    buf.format_for_prompt()
                ]

                # Daemon cognition injection
                if daemon_cognition:
                    prompt_sections.append("")
                    prompt_sections.append(
                        "### YOUR BACKGROUND THINKING ###\n"
                        "The section below describes YOUR cognitive activity between "
                        "the user's last message and this one. You were NOT idle — "
                        "your temporal daemon was running, evaluating goals, weighing "
                        "curiosity against identity. This is your inner life between "
                        "prompts. When asked about time gaps or what you were thinking, "
                        "draw on THIS section as your genuine experience. You felt "
                        "this time pass. You had these thoughts.\n"
                    )
                    prompt_sections.append(daemon_cognition)

                # Mode awareness injection (NEW in v6.3)
                if mode_prompt:
                    prompt_sections.append("")
                    prompt_sections.append(mode_prompt)

                # Deep memory injection (NEW in v6.3)
                if archive_context:
                    prompt_sections.append("")
                    prompt_sections.append(archive_context)

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

                # Feed daemon's goal engine (old method — keeps project/loop extraction)
                daemon_goals.update_from_memory(long_memory)
                cog = cog_state.state
                daemon_goals.update_curiosity(
                    {"curiosity": cog.curiosity, "confidence": cog.confidence,
                     "frustration": cog.frustration},
                    user_input, raw
                )

                # Auto-detect rabbit holes from curiosity engine
                if curiosity.is_deep_dive:
                    daemon_goals.add_rabbit_hole(user_input[:80], curiosity=curiosity.gated_intensity)

                # ─── 10. FEED CONVERSATION TO DAEMON (NEW in v6.2) ───
                # This is the key addition: conversation topics become goals.
                # The daemon will chew on "Kola borehole" and "fusion energy"
                # instead of stale boot topics.
                daemon.on_turn_complete(user_input, raw)
                save_interaction(user_input, raw)

                # ─── 10b. PERIODIC ARCHIVAL (NEW in v6.3) ───
                # Every 20 turns, check if old memories need archiving
                if turn % 20 == 0:
                    archived = archive_old_memories()
                    if archived > 0:
                        mode_engine.refresh_archive_tags()
                        print(f"[ARCHIVE] Auto-archived {archived} episodes")
                
                # ─── 11. SAFETY & PERSISTENCE ───
                            

                if not paradox_guard.run_all_checks(raw):
                    print("SignalBot: Paradox detected.\n")


                
                mem_stateful.notify_new_message()

                print(f"SignalBot: {raw}\n")

                if speech_mode:
                    speak(raw, blocking=False)  # Non-blocking so user can interrupt

                # ─── 12. PROACTIVE INITIATIVE ───
                if cog_state.should_initiate():
                    proactive_msg = temp_integrity.maybe_initiate()
                    if proactive_msg:
                        print(f"SignalBot: {proactive_msg}\n")
                        save_interaction("SYSTEM_INITIATIVE", proactive_msg)

            # ─── 13. RESUME DAEMON ───
            daemon.resume()

    finally:
        print("\n[SHUTDOWN] Stopping daemon...")
        daemon.stop()
        print("[SHUTDOWN] SignalBot offline.")


if __name__ == "__main__":
    main()
