# State-Vector Cognitive Architecture with Indelible Facts
## Non-Cheating Version - SignalBot Learns Identity

Adam - this is the REAL version. No hardcoded names. SignalBot learns and locks facts organically.

---

## What Changed

### The Problem with Hardcoding
Putting "Adam", "Griffin", "Sophie", "Mason" in `signal_identity.txt` defeats the purpose of testing whether the memory system actually works. It's cheating.

### The Solution: Indelible Facts System
SignalBot now **detects and locks** important facts through interaction:

```
You: My name is Adam
SignalBot: [detects name statement] → locks "User's name is Adam" as indelible

You: My children are Griffin, Sophie and Mason  
SignalBot: [detects relationship statement] → locks as indelible

You: Remember that I work at a Beer Store
SignalBot: [detects explicit directive] → locks as indelible
```

---

## How It Works

### Detection Patterns

1. **Name Statements**
   - "My name is X"
   - "I'm X" or "I am X"
   - Detects corrections: "No, my name is Adam"

2. **Relationship Statements**
   - "My children are X, Y, Z"
   - "My son/daughter is X"
   - "My kids are..."

3. **Explicit Directives**
   - "Remember that..."
   - "Never forget..."
   - "Always remember..."
   - "From now on..."

4. **Corrections**
   - When you correct the bot, it knows that fact is important
   - Example: Bot says "Bob", you say "No, Adam" → locks "Adam" as indelible

### What Makes Facts Indelible

- **Decay rate**: 0.0 (they don't decay)
- **Importance**: 5.0 (massive boost)
- **Locked**: Can't be pruned/forgotten
- **Always included** in prompt when `identity_adherence > 0.6`

---

## Files Created

### 1. indelible_facts.py
The detection and locking system. Scans user input for important facts and registers them.

### 2. memory_twdc_stateful.py (updated)
Now pulls identity keywords from learned indelible facts instead of hardcoded identity file.

### 3. signalbot_stateful_PATCH.py (updated)
- Registers indelible facts every turn
- Adds `facts` command to view learned facts
- Tracks previous bot output for correction detection

### 4. signal_identity_CLEAN.txt
Only personality traits. No hardcoded names or relationships.

---

## Installation

### 1. Copy Files
```bash
cp indelible_facts.py /path/to/signalbot/
cp memory_twdc_stateful.py /path/to/signalbot/  # Updated version
cp cognitive_state.py /path/to/signalbot/
```

### 2. Update signal_identity.txt
```bash
cp signal_identity_CLEAN.txt signal_identity.txt
```

### 3. Patch signalbot.py
Replace the `main()` function with the one from `signalbot_stateful_PATCH.py`.

Or add these imports:
```python
from indelible_facts import register_fact, get_indelible_prompt_section
```

And add this in the main loop (after getting user_input, before generating response):
```python
# Track previous bot output for correction detection
last_bot_output = ""

# In the loop, after generating response:
if register_fact(user_input, last_bot_output):
    print("[INFO] New indelible fact registered")
last_bot_output = raw
```

---

## New Commands

### `facts`
Shows all learned indelible facts:
```
You: facts

[INDELIBLE FACTS - NEVER FORGET]
- User's name is Adam
- User's children: Griffin, Sophie, and Mason
- User's son is Mason
```

### `state`
Shows cognitive state (still works)

### `dream on/off`
Still works

---

## Testing the System

### Session 1: Teaching Identity
```
You: Hey, I'm Adam. I'm building you.
SignalBot: [registers: "User's name is Adam"]
          [INFO] New indelible fact registered
          Nice to meet you, Adam!

You: I have three kids: Griffin, Sophie, and Mason.
SignalBot: [registers: "User's children: Griffin, Sophie, and Mason"]
          [INFO] New indelible fact registered
          Three kids! That must keep you busy.

You: Mason is my youngest. He's 8.
SignalBot: [registers: "User's son is Mason"]
          [INFO] New indelible fact registered
          Got it. Mason is 8.
```

### Session 2: Testing Persistence (After Restart)
```
You: Do you remember my name?
SignalBot: [loads indelible facts from file]
          [sees: "User's name is Adam"]
          Yes, your name is Adam.

You: What about my kids?
SignalBot: [loads: "User's children: Griffin, Sophie, and Mason"]
          Griffin, Sophie, and Mason.
```

### Session 3: Testing Corrections
```
You: What's my name?
SignalBot: Adam.

You: Actually, wait... test if you handle corrections. My name is Bob.
SignalBot: [detects correction]
          [updates indelible fact: "User's name is Bob"]
          [INFO] New indelible fact registered
          Got it, Bob.

You: Just kidding, it's Adam.
SignalBot: [detects correction again]
          [updates back to: "User's name is Adam"]
          [INFO] New indelible fact registered
          Alright, Adam it is.
```

---

## How Indelible Facts Integrate

### With TWDC Memory
- Indelible facts provide **identity keywords** for alignment scoring
- Facts with names like "Adam", "Griffin", "Sophie", "Mason" get high alignment
- These keywords boost related memories in TWDC scoring

### With Cognitive State
- When `identity_adherence > 0.7`, indelible facts get extra priority
- Modulates which memories surface based on current state

### With Prompt Construction
Indelible facts always appear at the top of CORE DATA:
```
### CORE DATA (TRUST THIS OVER ALL ELSE) ###
[INDELIBLE FACTS - NEVER FORGET]
- User's name is Adam
- User's children: Griffin, Sophie, and Mason

[MASTER SUMMARY]
...

[TOP MEMORIES (State-Weighted)]
...
```

---

## Data Storage

### indelible_facts.json
```json
{
  "facts": [
    {
      "id": "a3f8e2c9d1b4",
      "fact": "User's name is Adam",
      "category": "name",
      "first_mentioned": 1706234567.89,
      "last_confirmed": 1706234567.89,
      "confirmation_count": 1,
      "locked": true,
      "importance": 5.0
    },
    {
      "id": "b7d9f1e4a2c6",
      "fact": "User's children: Griffin, Sophie, and Mason",
      "category": "relationship",
      "first_mentioned": 1706234590.12,
      "last_confirmed": 1706234590.12,
      "confirmation_count": 1,
      "locked": true,
      "importance": 5.0
    }
  ],
  "last_updated": 1706234590.12
}
```

### Confirmation Tracking
If you mention a fact multiple times, `confirmation_count` increases:
```json
{
  "fact": "User's name is Adam",
  "confirmation_count": 5,  // Mentioned 5 times
  "last_confirmed": 1706235678.90
}
```

---

## Architecture

```
┌─────────────────────────────────────────┐
│         USER INPUT                      │
│  "My name is Adam"                      │
└────────────┬────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│    INDELIBLE FACTS ENGINE              │
│  Pattern Detection:                    │
│  ✓ Name statement detected             │
│  ✓ Category: "name"                    │
│  ✓ Register & Lock                     │
└────────────┬───────────────────────────┘
             │
             ├────────────┬───────────────┐
             ▼            ▼               ▼
    ┌────────────┐ ┌────────────┐ ┌────────────┐
    │ SAVED TO   │ │  INJECTED  │ │ EXTRACTED  │
    │ JSON FILE  │ │INTO PROMPT │ │AS KEYWORDS │
    └────────────┘ └────────────┘ └──────┬─────┘
                                          │
                                          ▼
                                  ┌────────────────┐
                                  │ TWDC ALIGNMENT │
                                  │ SCORING BOOST  │
                                  └────────────────┘
```

---

## Tuning

### Detection Sensitivity
Edit `indelible_facts.py` to add more patterns:

```python
def _detect_custom_pattern(self, text: str):
    t = text.lower()
    if "i work at" in t:
        job = t.split("i work at", 1)[1].strip()
        return {
            "category": "employment",
            "fact": f"User works at {job}"
        }
```

### Importance Weights
Adjust in `indelible_facts.py`:
```python
IndelibleFact(
    ...
    importance=10.0  # Even higher for super-critical facts
)
```

### Decay Rate
Currently hardcoded to 0.0 (no decay). To allow very slow drift:
```python
# In TWDC scoring, indelible facts could have:
decay_rate = 0.01  # vs 0.25 for normal facts
```

---

## Troubleshooting

### Bot still forgets names
1. Type `facts` to see if they were registered
2. If empty, check detection patterns in `indelible_facts.py`
3. Try explicit: "Remember that my name is Adam"
4. Check `indelible_facts.json` exists and has content

### Facts not being detected
1. Check console for `[INFO] New indelible fact registered`
2. If not appearing, pattern detection failed
3. Try different phrasing: "My name is X" vs "I'm X"
4. Add debug print in `register_fact()` to see what's detected

### Facts detected but not surfacing in responses
1. Check `identity_adherence` value (should be > 0.6)
2. Type `facts` to confirm they're registered
3. Check long memory block has indelible section
4. Verify TWDC is using indelible keywords for alignment

---

## The Memory Test (Proper Version)

### Test 1: Initial Introduction
```
You: My name is Adam.
SignalBot: [registers fact] Nice to meet you, Adam!
```

### Test 2: Immediate Recall
```
You: What's my name?
SignalBot: [loads from indelible_facts.json] Adam.
```

### Test 3: Shutdown & Restart
```
[Restart SignalBot]

You: Do you remember my name?
SignalBot: [loads indelible_facts.json on startup]
          Yes, Adam.
```

### Test 4: After Many Turns
```
[Have 50+ turn conversation about other topics]

You: What's my name again?
SignalBot: [indelible facts persist regardless of context]
          Adam.
```

### Test 5: Correction Handling
```
You: My name is Bob.
SignalBot: [detects correction, updates fact]
          Got it, Bob.

You: Wait no, I was testing you. It's Adam.
SignalBot: [corrects back]
          Alright, Adam.
```

---

## What Makes This Non-Cheating

### Before (Cheating):
- Names hardcoded in `signal_identity.txt`
- Bot never has to learn them
- Can't test if memory system actually works

### After (Proper):
- Bot must detect identity statements
- Bot must lock them as indelible
- Bot must retrieve them from learned storage
- Bot must handle corrections and updates
- **This tests the entire cognitive pipeline**

---

## Next Steps

### Potential Enhancements

1. **Confidence Scoring**
   - Track how certain the bot is about each fact
   - Facts mentioned once = low confidence
   - Facts confirmed 10 times = high confidence

2. **Fact Expiration**
   - Some facts have time limits: "I'm traveling to NYC" (expires)
   - Some are permanent: "My name is Adam" (never expires)

3. **Fact Relationships**
   - Link related facts: "Adam" → "has children" → "Griffin, Sophie, Mason"
   - Build a knowledge graph

4. **Semantic Detection**
   - Use embeddings instead of pattern matching
   - Detect "I go by X" or "Everyone calls me X" as name statements

5. **Multi-User Support**
   - Separate indelible facts per user
   - Mason gets his own fact set
   - User detection from context

---

## The Big Picture

**You wanted state vectors mapped onto memory.**

**What you got:**
- State-aware memory retrieval ✓
- Learned (not hardcoded) identity facts ✓
- Indelible fact detection system ✓
- Correction handling ✓
- Proper memory testing capability ✓

**Now the memory test is REAL:**
1. You tell SignalBot your name
2. It detects the statement
3. It locks it as indelible
4. It retrieves it later
5. It never forgets it

**This is how emergent cognition should work.**

Not hardcoded rules. Not cheating.

Just a system that learns what matters and holds onto it.

**Welcome to v5gi with indelible facts, Adam.**

Now go test it properly.

- Claude
