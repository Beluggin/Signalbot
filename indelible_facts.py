# indelible_facts.py
"""
═══════════════════════════════════════════════════════════════════
INDELIBLE FACTS - Learned Identity Anchoring (NON-CHEATING VERSION)
═══════════════════════════════════════════════════════════════════

This is how SignalBot LEARNS important facts organically instead of having
them hardcoded. When you say "My name is Adam", SignalBot detects this is
an identity statement and LOCKS it as "indelible" (never decays).

WHY THIS ISN'T CHEATING:
- SignalBot must detect the pattern in your language
- SignalBot must recognize it's important (explicit directive, correction, etc.)
- SignalBot must store it and retrieve it later
- This tests the ENTIRE memory pipeline

WHAT GETS LOCKED AS INDELIBLE:
1. Name statements: "My name is X"
2. Relationships: "My children are X, Y, Z"
3. Explicit directives: "Remember that...", "Never forget..."
4. Corrections: When you fix SignalBot's mistakes

INDELIBLE FACTS GET:
- Decay rate of 0.0 (they don't fade)
- Importance score of 5.0 (massive boost in TWDC)
- Always included in prompt when identity_adherence > 0.6
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

INDELIBLE_PATH = Path("indelible_facts.json")

@dataclass
class IndelibleFact:
    """A fact that should never be forgotten."""
    id: str
    fact: str
    category: str  # "name", "relationship", "directive", "custom"
    first_mentioned: float
    last_confirmed: float
    confirmation_count: int = 1
    locked: bool = True
    importance: float = 5.0  # Massively high
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "fact": self.fact,
            "category": self.category,
            "first_mentioned": self.first_mentioned,
            "last_confirmed": self.last_confirmed,
            "confirmation_count": self.confirmation_count,
            "locked": self.locked,
            "importance": self.importance
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'IndelibleFact':
        return cls(**d)


class IndelibleFactsEngine:
    """Detects and manages facts that should never decay."""
    
    def __init__(self):
        self.facts: Dict[str, IndelibleFact] = {}
        self._load()
    
    def _load(self):
        if INDELIBLE_PATH.exists():
            try:
                data = json.loads(INDELIBLE_PATH.read_text(encoding="utf-8"))
                for fact_dict in data.get("facts", []):
                    fact = IndelibleFact.from_dict(fact_dict)
                    self.facts[fact.id] = fact
            except Exception:
                pass
    
    def _save(self):
        data = {
            "facts": [f.to_dict() for f in self.facts.values()],
            "last_updated": time.time()
        }
        INDELIBLE_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    #═══════════════════════════════════════════════════════════
    # PATTERN DETECTION
    #═══════════════════════════════════════════════════════════
    
    def _detect_name_statement(self, text: str) -> Optional[Dict]:
        """Detect 'My name is X' or 'I am X' patterns."""
        t = text.lower().strip()
        
        # "my name is X"
        if "my name is" in t:
            parts = t.split("my name is", 1)
            if len(parts) == 2:
                name = parts[1].strip().strip(".,!?").split()[0] if parts[1].strip() else None
                if name and len(name) > 1:
                    return {
                        "category": "name",
                        "fact": f"User's name is {name.capitalize()}"
                    }
        
        # "I'm X" or "I am X" at start
        if t.startswith("i'm ") or t.startswith("i am "):
            parts = t.split(" ", 2)
            if len(parts) >= 2:
                name = parts[1].strip(".,!?")
                if name and len(name) > 1 and name not in ["a", "going", "thinking"]:
                    return {
                        "category": "name",
                        "fact": f"User's name is {name.capitalize()}"
                    }
        return None
    
    def _detect_relationship_statement(self, text: str) -> Optional[Dict]:
        """Detect 'My children are X, Y, Z' patterns."""
        t = text.lower().strip()
        
        if "my children are" in t or "my kids are" in t:
            parts = t.split("are", 1)
            if len(parts) == 2:
                names_part = parts[1].strip().strip(".,!?")
                return {
                    "category": "relationship",
                    "fact": f"User's children: {names_part}"
                }
        
        # "my son/daughter is X"
        for marker in ["my son", "my daughter"]:
            if marker in t:
                parts = t.split(marker, 1)
                if len(parts) == 2:
                    rest = parts[1].strip()
                    if rest.startswith("is "):
                        name = rest.replace("is ", "").strip().strip(".,!?").split()[0]
                        if name and len(name) > 1:
                            return {
                                "category": "relationship",
                                "fact": f"User's {marker.replace('my ', '')} is {name.capitalize()}"
                            }
        return None
    
    def _detect_explicit_directive(self, text: str) -> Optional[Dict]:
        """Detect explicit memory commands."""
        t = text.lower().strip()
        patterns = [
            ("remember that", "directive"),
            ("never forget", "directive"),
            ("always remember", "directive"),
            ("from now on", "directive"),
            ("don't forget", "directive")
        ]
        
        for pattern, category in patterns:
            if pattern in t:
                parts = t.split(pattern, 1)
                if len(parts) == 2:
                    directive = parts[1].strip().strip(".,!?")
                    if directive and len(directive) > 3:
                        return {"category": category, "fact": directive}
        return None
    
    def _detect_correction(self, user_text: str, bot_previous: str) -> Optional[Dict]:
        """Detect when user corrects the bot."""
        u = user_text.lower().strip()
        if any(marker in u for marker in ["no,", "actually,", "wrong", "incorrect"]):
            name_info = self._detect_name_statement(user_text)
            if name_info:
                return name_info
            rel_info = self._detect_relationship_statement(user_text)
            if rel_info:
                return rel_info
        return None
    
    #═══════════════════════════════════════════════════════════
    # REGISTRATION
    #═══════════════════════════════════════════════════════════
    
    def register_fact(self, user_input: str, bot_output: str = "") -> bool:
        """
        Scan user input for indelible facts and register them.
        Returns True if a new fact was registered.
        """
        detected = []
        detected.append(self._detect_name_statement(user_input))
        detected.append(self._detect_relationship_statement(user_input))
        detected.append(self._detect_explicit_directive(user_input))
        detected.append(self._detect_correction(user_input, bot_output))
        
        detected = [d for d in detected if d is not None]
        if not detected:
            return False
        
        now = time.time()
        registered_new = False
        
        for info in detected:
            fact_text = info["fact"]
            category = info["category"]
            fact_id = self._generate_id(fact_text)
            
            if fact_id in self.facts:
                # Update confirmation
                self.facts[fact_id].last_confirmed = now
                self.facts[fact_id].confirmation_count += 1
            else:
                # New fact
                self.facts[fact_id] = IndelibleFact(
                    id=fact_id,
                    fact=fact_text,
                    category=category,
                    first_mentioned=now,
                    last_confirmed=now
                )
                registered_new = True
        
        self._save()
        return registered_new
    
    def _generate_id(self, fact_text: str) -> str:
        """Generate stable ID from fact text."""
        normalized = fact_text.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()[:12]
    
    #═══════════════════════════════════════════════════════════
    # RETRIEVAL
    #═══════════════════════════════════════════════════════════
    
    def get_all_facts(self) -> List[IndelibleFact]:
        """Get all facts, sorted by importance."""
        facts = list(self.facts.values())
        facts.sort(key=lambda f: (f.importance, f.confirmation_count), reverse=True)
        return facts
    
    def format_for_prompt(self, max_facts: int = 20) -> str:
        """
        Format for injection into prompt.
        These go at the TOP of CORE DATA section.
        """
        facts = self.get_all_facts()[:max_facts]
        if not facts:
            return ""
        
        lines = ["[INDELIBLE FACTS - NEVER FORGET]"]
        
        # Group by category (names first, then relationships, then directives)
        by_category: Dict[str, List] = {}
        for fact in facts:
            if fact.category not in by_category:
                by_category[fact.category] = []
            by_category[fact.category].append(fact)
        
        for category in ["name", "relationship", "directive"]:
            if category in by_category:
                for fact in by_category[category]:
                    lines.append(f"- {fact.fact}")
        
        return "\n".join(lines)
    
    def extract_identity_keywords(self) -> List[str]:
        """
        Extract keywords for TWDC alignment scoring.
        This REPLACES reading from signal_identity.txt for identity keywords.
        """
        keywords = []
        for fact in self.facts.values():
            words = fact.fact.lower().split()
            for word in words:
                word = word.strip(".,!?:;")
                if len(word) > 2 and word not in ["the", "is", "are", "and"]:
                    keywords.append(word)
        
        # Deduplicate
        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        return unique[:60]


# SINGLETON
_engine: Optional[IndelibleFactsEngine] = None

def get_indelible_engine() -> IndelibleFactsEngine:
    global _engine
    if _engine is None:
        _engine = IndelibleFactsEngine()
    return _engine

# CONVENIENCE FUNCTIONS
def register_fact(user_input: str, bot_output: str = "") -> bool:
    return get_indelible_engine().register_fact(user_input, bot_output)

def get_indelible_prompt_section(max_facts: int = 20) -> str:
    return get_indelible_engine().format_for_prompt(max_facts)

def get_indelible_keywords() -> List[str]:
    return get_indelible_engine().extract_identity_keywords()
