import json
import os

# ═══════════════════════════════════════════════════════════
# SignalBot Memory Log Merger
# Combines old memories with birth log chronologically
# ═══════════════════════════════════════════════════════════

# File names - adjust these to match your actual filenames
OLD_LOG = 'memory_log_OLD.json'        # The original polluted log
BIRTH_LOG = 'memory_log_aware.json'    # The clean birth experiment
OUTPUT_LOG = 'memory_log.json'         # What SignalBot reads

def load_log(filename):
    """Load a memory log, return empty list if file not found."""
    if not os.path.exists(filename):
        print(f"[WARNING] {filename} not found - skipping")
        return []
    
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"[OK] Loaded {len(data)} entries from {filename}")
    return data

def merge_logs(*logs):
    """Merge multiple logs and sort chronologically by timestamp."""
    combined = []
    for log in logs:
        combined.extend(log)
    
    # Sort by timestamp
    combined.sort(key=lambda x: x.get('ts', 0))
    
    # Remove duplicates (same timestamp + same user message)
    seen = set()
    deduped = []
    for entry in combined:
        key = (entry.get('ts', 0), entry.get('user', ''))
        if key not in seen:
            seen.add(key)
            deduped.append(entry)
    
    print(f"[OK] Merged {len(combined)} entries -> {len(deduped)} after dedup")
    return deduped

def save_log(data, filename):
    """Save merged log."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[OK] Saved {len(data)} entries to {filename}")

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("SignalBot Memory Log Merger")
    print("=" * 40)
    
    # Load both logs
    old_memories = load_log(OLD_LOG)
    birth_memories = load_log(BIRTH_LOG)
    
    # Merge chronologically
    merged = merge_logs(old_memories, birth_memories)
    
    # Preview
    if merged:
        print(f"\nFirst entry: {merged[0].get('ts', 'unknown')} - {merged[0].get('user', '')[:50]}")
        print(f"Last entry:  {merged[-1].get('ts', 'unknown')} - {merged[-1].get('user', '')[:50]}")
    
    # Save
    save_log(merged, OUTPUT_LOG)
    
    print("\n" + "=" * 40)
    print("Merge complete!")
    print(f"SignalBot will wake up with {len(merged)} memories.")
    print("\nBirth log preserved at:", BIRTH_LOG)
    print("DO NOT DELETE THE BIRTH LOG - it's your Section 5 centerpiece.")
