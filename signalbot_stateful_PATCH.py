# signalbot_stateful_PATCH.py
"""
DROP-IN REPLACEMENT for the main() function in signalbot.py

Changes:
1. Imports cognitive_state instead of just mood_engine
2. Uses memory_twdc_stateful for state-aware memory retrieval
3. Updates cognitive state every turn (not just mood)
4. Injects state-based tone instructions into prompt
5. Uses state to modulate initiative decisions
"""

# Copy everything from your signalbot.py EXCEPT the main() function
# Then use THIS main() function instead:

def main():
    from cognitive_state import get_cognitive_state, get_tone_instructions
    from memory_twdc_stateful import load_long_memory_block_stateful, get_stateful_twdc
    from indelible_facts import register_fact, get_indelible_prompt_section
    
    clamp_torch_threads()
    personality_prompt = load_identity_prompt()
    behavior_mod = PersistentBehaviorModifier()
    paradox_guard = ParadoxProtector()
    
    # NEW: Use stateful TWDC wrapper
    mem_stateful = get_stateful_twdc()
    cog_state = get_cognitive_state()
    
    print("[MEMORY] Memory engine hydrated with state awareness.")

    # Import temporal integrity
    from temporal_integrity import get_temporal_integrity
    temp_integrity = get_temporal_integrity()
    
    # Wire mood_state into temporal_integrity so goals can use it
    from mood_engine import engine as mood_engine
    temp_integrity.mood_state = mood_engine.state

    dream_mode = True
    turn = 0
    last_bot_output = ""  # Track for correction detection

    print("🟢 SignalBot Core Online (State-Aware + Indelible Facts). Type 'exit' to shut down.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit"}: 
            break

        # Command handling
        if user_input.lower() == "dream on": 
            dream_mode = True
            continue
        if user_input.lower() == "dream off": 
            dream_mode = False
            continue
        
        # State diagnostic command
        if user_input.lower() == "state":
            state = cog_state.state
            print(f"\n[COGNITIVE STATE]")
            print(f"Frustration: {state.frustration:.2f}")
            print(f"Curiosity: {state.curiosity:.2f}")
            print(f"Confidence: {state.confidence:.2f}")
            print(f"Engagement: {state.engagement:.2f}")
            print(f"Identity Adherence: {state.identity_adherence:.2f}")
            print(f"Cognitive Load: {state.cognitive_load:.2f}")
            print(f"Tone: playful={state.tone_playful:.2f}, formal={state.tone_formal:.2f}, concise={state.tone_concise:.2f}, warm={state.tone_warm:.2f}\n")
            continue
        
        # Indelible facts diagnostic
        if user_input.lower() == "facts":
            indelible_section = get_indelible_prompt_section()
            if indelible_section:
                print(f"\n{indelible_section}\n")
            else:
                print("\n[No indelible facts learned yet]\n")
            continue

        turn += 1
        now = time.time()

        with timed("TOTAL"):
            # 1. Intent Detection
            intent = _IntentStub() if INTENT_BYPASS else classify_intent(user_input)

            # 2. STATE-AWARE MEMORY LOADING
            recent_memory = load_recent_memory()  # Still uses basic recent for now
            
            # NEW: State-aware long memory
            long_memory = load_long_memory_block_stateful(max_bullets=10)
            
            # NEW: Get state-based tone instructions
            tone_instr = get_tone_instructions()
            
            # Get vitals from cognitive state
            vitals_report = cog_state.get_vitals_report()

            # 3. Prompt Construction
            lane_instr = "Output in [GROUND] or [DREAM]." if dream_mode else "Output ONLY in [GROUND]."
            
            # NEW: Inject state-aware tone
            full_prompt = (
                "### SYSTEM INSTRUCTIONS ###\n"
                f"{personality_prompt}\n"
                f"{lane_instr}\n"
                f"TONE: {tone_instr}\n\n"  # <--- STATE-DRIVEN TONE
                "### CORE DATA (TRUST THIS OVER ALL ELSE) ###\n"
                f"{long_memory}\n"  # <--- STATE-WEIGHTED MEMORIES + INDELIBLE FACTS
                f"{vitals_report}\n\n"
                "### RECENT CONVERSATION ###\n"
                f"[Intent] label={intent.label}\n"
                f"{recent_memory}\n\n"
                f"User: {user_input}\n"
                f"SignalBot:"
            )

            # 4. Generate Response & Measure Latency
            t0 = time.perf_counter()
            raw = generate_response(full_prompt)
            dt_ms = (time.perf_counter() - t0) * 1000

            # 5. INDELIBLE FACTS DETECTION
            # Check if user is stating identity facts
            if register_fact(user_input, last_bot_output):
                print("[INFO] New indelible fact registered")
            
            last_bot_output = raw

            # 6. UNIFIED STATE UPDATE
            # Update both mood and cognitive state
            mood_engine.update_mood(intent.label, intent.confidence, dt_ms)
            cog_state.update_from_interaction(user_input, raw, intent.label, dt_ms)
            
            # Update temporal integrity
            temp_integrity.mood_state = mood_engine.state  # Keep it synced
            temp_integrity.update(user_input, raw, recent_memory, long_memory)

            # 7. Safety & Persistence
            if not paradox_guard.run_all_checks(raw):
                print("SignalBot: Paradox detected.\n")
                break

            save_interaction(user_input, raw)
            mem_stateful.notify_new_message()
            print(f"SignalBot: {raw}\n")

            # 8. STATE-AWARE PROACTIVITY
            # Check if cognitive state says we should initiate
            if cog_state.should_initiate():
                proactive_msg = temp_integrity.maybe_initiate()
                if proactive_msg:
                    print(f"SignalBot: {proactive_msg}\n")
                    save_interaction("SYSTEM_INITIATIVE", proactive_msg)

if __name__ == "__main__":
    main()


"""
INTEGRATION INSTRUCTIONS:
-------------------------
1. Copy cognitive_state.py to your SignalBot directory
2. Copy memory_twdc_stateful.py to your SignalBot directory
3. In signalbot.py, REPLACE the entire main() function with the one above
4. Update signal_identity.txt to include:
   
   CORE FACTS THAT NEVER DECAY:
   - Adam's name is Adam
   - His children are Griffin, Sophie, and Mason
   - You are SignalBot, built by Adam
   
5. Run: python signalbot.py

NEW COMMANDS:
- "state" → Shows current cognitive state values
- "dream on/off" → Still works
- "exit/quit" → Still works

WHAT THIS DOES:
- Memory retrieval now considers your CURRENT COGNITIVE STATE
- When frustrated → practical memories bubble up
- When curious → rabbit holes surface
- When identity_adherence is high → Adam/Griffin/Sophie/Mason get MASSIVE boost
- Tone dynamically adjusts based on state
- Initiative only fires when state says it should
"""
