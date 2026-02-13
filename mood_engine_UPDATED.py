# mood_engine_UPDATED.py
"""
UPDATED MOOD ENGINE - Now reads from cognitive_state

CHANGES:
- No longer maintains its own state dict
- Now reads from the unified cognitive_state system
- Backward compatible (same functions, different backend)

LEARNING NOTE: This is "refactoring" - changing internals while keeping
the same external interface. Your existing code that imports mood_engine
will keep working, but now it reads from the unified state.
"""

import json
from pathlib import Path
from cognitive_state import get_cognitive_state

# Backward compatibility - expose the same functions
def get_tone() -> str:
    """Get current tone based on cognitive state."""
    state = get_cognitive_state().state
    
    if state.frustration > 0.6:
        return "direct, irritable, brief"
    if state.curiosity > 0.7:
        return "intense, inquisitive, exploratory"
    return "candid, practical, slightly irreverent"

def describe_mood() -> str:
    """Get mood description."""
    state = get_cognitive_state().state
    return f"Curiosity: {state.curiosity:.2f}, Confidence: {state.confidence:.2f}, Frustration: {state.frustration:.2f}"

def update_mood(intent_label: str, confidence_score: float, latency_ms: float):
    """
    Update mood - now just a wrapper around cognitive_state.
    
    LEARNING NOTE: We keep this function for backward compatibility,
    but now it just forwards to cognitive_state.update_from_interaction().
    The actual logic is in cognitive_state.py now.
    """
    # This is handled by cognitive_state.update_from_interaction()
    # We keep this function stub for backward compatibility
    pass

def get_vitals_report() -> str:
    """Get internal state report."""
    return get_cognitive_state().get_vitals_report()

# Expose state dict for backward compatibility
class _StateProxy:
    """Proxy that reads from cognitive_state."""
    def __getitem__(self, key):
        state = get_cognitive_state().state
        # Map old keys to new structure
        mapping = {
            "curiosity": state.curiosity,
            "confidence": state.confidence,
            "frustration": state.frustration,
            "energy": 1.0 - state.cognitive_load,  # Inverse of load
        }
        return mapping.get(key, 0.5)
    
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

mood_state = _StateProxy()

# Singleton for compatibility
class MoodEngine:
    def __init__(self):
        self.state = mood_state
    
    def get_tone(self):
        return get_tone()
    
    def describe_mood(self):
        return describe_mood()
    
    def update_mood(self, intent_label, confidence_score, latency_ms):
        update_mood(intent_label, confidence_score, latency_ms)
    
    def get_vitals_report(self):
        return get_vitals_report()

engine = MoodEngine()
