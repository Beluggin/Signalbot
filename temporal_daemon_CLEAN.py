# temporal_daemon.py
"""
═══════════════════════════════════════════════════════════════════
TEMPORAL DAEMON — Always-On Cognitive Heartbeat
═══════════════════════════════════════════════════════════════════

SignalBot's continuous background cognition. Runs a 9-phase cycle
at 100ms ticks, constantly evaluating goals against curiosity,
identity, and engagement — even when the user isn't talking.

PHASES (each 0.1s):
  0 — CHECK_GOALS:       Pull active goals, refresh from memory
  1 — EVALUATE:          Score against curiosity + "good sense"
  2 — DETERMINE_ACTIONS: Generate candidate actions for top items
  3 — APPEND_RECOMMEND:  Push actions to recommendation queue
  4 — PRIORITIZE:        Sort queue by composite score
  5 — REEVAL_IDENTITY:   Re-check top items against core identity
  6 — USER_URGENCY:      Tag items that need user input vs autonomous
  7 — SUMMARIZE:         Build cognitive focus summary
  8 — CLEANUP:           Purge "crap items" below threshold

INTERRUPT MODEL:
  When user input arrives, the daemon PAUSES instantly.
  The main loop reads the daemon's current recommendations,
  then RESUMES the daemon after responding.

THREAD SAFETY:
  All shared state is behind threading.Lock.
  The daemon never touches the LLM — it only reorganizes cognition.

USAGE:
  daemon = TemporalDaemon()
  daemon.start()          # Begin background cognition
  daemon.pause()          # Pause when user speaks
  snapshot = daemon.get_snapshot()  # Read current cognitive state
  daemon.resume()         # Resume after responding
  daemon.stop()           # Shutdown
"""

import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import IntEnum

# Import existing systems
from cognitive_state import get_cognitive_state
from indelible_facts import get_indelible_keywords, get_indelible_engine
from goal_engine import GoalEngine, Goal, ActionCandidate


# ═══════════════════════════════════════════════════════════════════
# PHASE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════

class Phase(IntEnum):
    CHECK_GOALS      = 0
    EVALUATE         = 1
    DETERMINE_ACTIONS = 2
    APPEND_RECOMMEND  = 3
    PRIORITIZE       = 4
    REEVAL_IDENTITY  = 5
    USER_URGENCY     = 6
    SUMMARIZE        = 7
    CLEANUP          = 8

PHASE_NAMES = {
    Phase.CHECK_GOALS:      "CHECK_GOALS",
    Phase.EVALUATE:         "EVALUATE",
    Phase.DETERMINE_ACTIONS: "DETERMINE_ACTIONS",
    Phase.APPEND_RECOMMEND:  "APPEND_RECOMMEND",
    Phase.PRIORITIZE:       "PRIORITIZE",
    Phase.REEVAL_IDENTITY:  "REEVAL_IDENTITY",
    Phase.USER_URGENCY:     "USER_URGENCY",
    Phase.SUMMARIZE:        "SUMMARIZE",
    Phase.CLEANUP:          "CLEANUP",
}

NUM_PHASES = 9
TICK_INTERVAL = 0.1  # 100ms per phase → full cycle = 0.9s


# ═══════════════════════════════════════════════════════════════════
# GOOD SENSE METER
# ═══════════════════════════════════════════════════════════════════

def compute_good_sense(cog_state) -> float:
    """
    Composite "good sense" score — should I actually pursue this?
    
    Factors:
      identity_adherence — Am I staying true to who I am?
      engagement         — Am I actually interested?
      confidence         — Do I believe this is worthwhile?
      (1 - frustration)  — Am I in a good headspace for this?
    
    Returns 0.0–1.0. Below 0.3 means "bad idea right now."
    """
    s = cog_state.state
    return (
        s.identity_adherence * 0.30 +
        s.engagement         * 0.30 +
        s.confidence         * 0.20 +
        (1.0 - s.frustration) * 0.20
    )


def compute_crap_threshold(cog_state) -> float:
    """
    Dynamic threshold for purging low-value items.
    
    When cognitive load is high, we're MORE aggressive (higher threshold).
    When curious and engaged, we're MORE tolerant (lower threshold).
    """
    s = cog_state.state
    base = 0.20
    
    # High load → raise threshold (be pickier)
    if s.cognitive_load > 0.7:
        base += 0.10
    
    # High curiosity → lower threshold (keep more rabbit holes)
    if s.curiosity > 0.7:
        base -= 0.08
    
    # High frustration → raise threshold (only keep practical stuff)
    if s.frustration > 0.5:
        base += 0.12
    
    return max(0.10, min(0.50, base))


# ═══════════════════════════════════════════════════════════════════
# COGNITIVE SNAPSHOT — What the daemon hands to the main loop
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CognitiveSnapshot:
    """
    Immutable snapshot of the daemon's current thinking.
    Main loop reads this when user speaks.
    """
    timestamp: float = 0.0
    cycle_count: int = 0
    current_phase: int = 0
    
    # Top action recommendations (sorted by score)
    top_recommendations: List[Dict[str, Any]] = field(default_factory=list)
    
    # Items flagged as needing user input
    user_urgent_items: List[Dict[str, Any]] = field(default_factory=list)
    
    # Current cognitive focus summary
    focus_summary: str = ""
    
    # Good sense reading
    good_sense: float = 0.5
    crap_threshold: float = 0.25
    
    # Stats
    items_evaluated: int = 0
    items_purged: int = 0
    
    def format_for_prompt(self, max_items: int = 5) -> str:
        """Format for injection into SignalBot's prompt."""
        if not self.top_recommendations and not self.focus_summary:
            return ""
        
        lines = ["[DAEMON COGNITION — Background Thinking]"]
        
        if self.focus_summary:
            lines.append(f"Focus: {self.focus_summary}")
        
        lines.append(f"Good Sense: {self.good_sense:.2f} | Crap Threshold: {self.crap_threshold:.2f}")
        
        if self.top_recommendations:
            lines.append("Active Threads:")
            for rec in self.top_recommendations[:max_items]:
                score = rec.get("composite_score", 0.0)
                desc = rec.get("description", "?")[:60]
                action = rec.get("action_type", "think")
                urgent = " [USER_NEEDED]" if rec.get("needs_user", False) else ""
                lines.append(f"  [{score:.2f}] {action}: {desc}{urgent}")
        
        if self.user_urgent_items:
            lines.append("Waiting for User:")
            for item in self.user_urgent_items[:3]:
                lines.append(f"  → {item.get('description', '?')[:50]}")
        
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# THE DAEMON
# ═══════════════════════════════════════════════════════════════════

class TemporalDaemon:
    """
    Always-on background cognitive loop.
    
    Runs in a daemon thread. Each tick (100ms) executes one phase
    of the 9-phase cognitive cycle. Pauses instantly when interrupted.
    """
    
    def __init__(self, goal_engine: Optional[GoalEngine] = None):
        # External systems
        self._cog_state = get_cognitive_state()
        self._goals = goal_engine or GoalEngine()
        self._identity_keywords = get_indelible_keywords()
        
        # Thread control
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()      # Set = running
        self._paused = threading.Event()        # Set = paused
        self._stop_flag = threading.Event()     # Set = shutdown
        self._lock = threading.Lock()           # Protects shared state
        
        # Cycle state
        self._phase: int = 0
        self._cycle_count: int = 0
        
        # Working buffers (protected by _lock)
        self._candidate_scores: Dict[str, float] = {}       # goal_id → composite score
        self._action_queue: List[ActionCandidate] = []       # pending recommendations
        self._recommendations: List[ActionCandidate] = []    # finalized, sorted
        self._user_urgent: List[ActionCandidate] = []        # needs user input
        self._focus_summary: str = ""
        self._items_purged: int = 0
        
        # Callbacks
        self._on_urgent_callback = None  # Optional callback when urgent item found
    
    # ═══ LIFECYCLE ═══
    
    def start(self):
        """Start the daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        
        self._stop_flag.clear()
        self._paused.clear()
        self._running.set()
        
        self._thread = threading.Thread(
            target=self._run_loop,
            name="TemporalDaemon",
            daemon=True  # Dies when main process exits
        )
        self._thread.start()
        print("[DAEMON] Temporal daemon started — cognitive heartbeat active")
    
    def stop(self):
        """Stop the daemon permanently."""
        self._stop_flag.set()
        self._running.set()  # Unblock if paused
        self._paused.clear()
        if self._thread:
            self._thread.join(timeout=2.0)
        print("[DAEMON] Temporal daemon stopped")
    
    def pause(self):
        """
        Pause the daemon instantly.
        Call this when user input arrives.
        """
        self._paused.set()
        self._running.clear()
    
    def resume(self):
        """
        Resume the daemon.
        Call this after the main loop finishes responding.
        """
        # Refresh identity keywords in case new facts were learned
        self._identity_keywords = get_indelible_keywords()
        
        self._paused.clear()
        self._running.set()
    
    @property
    def is_running(self) -> bool:
        return self._running.is_set() and not self._paused.is_set()
    
    # ═══ SNAPSHOT ═══
    
    def get_snapshot(self) -> CognitiveSnapshot:
        """
        Get an immutable snapshot of current daemon state.
        Thread-safe. Call from main loop.
        """
        with self._lock:
            return CognitiveSnapshot(
                timestamp=time.time(),
                cycle_count=self._cycle_count,
                current_phase=self._phase,
                top_recommendations=[
                    {
                        "goal_id": r.goal_id,
                        "description": r.description,
                        "action_type": r.action_type,
                        "composite_score": r.composite_score,
                        "needs_user": r.needs_user,
                        "reasoning": r.reasoning,
                    }
                    for r in self._recommendations[:10]
                ],
                user_urgent_items=[
                    {
                        "goal_id": u.goal_id,
                        "description": u.description,
                        "action_type": u.action_type,
                        "reasoning": u.reasoning,
                    }
                    for u in self._user_urgent[:5]
                ],
                focus_summary=self._focus_summary,
                good_sense=compute_good_sense(self._cog_state),
                crap_threshold=compute_crap_threshold(self._cog_state),
                items_evaluated=len(self._candidate_scores),
                items_purged=self._items_purged,
            )
    
    def set_urgent_callback(self, callback):
        """Register callback for when urgent items are found."""
        self._on_urgent_callback = callback
    
    # ═══ THE LOOP ═══
    
    def _run_loop(self):
        """Main daemon loop. Runs until stop() is called."""
        while not self._stop_flag.is_set():
            # Wait if paused
            self._running.wait(timeout=0.5)
            
            if self._stop_flag.is_set():
                break
            
            if self._paused.is_set():
                continue
            
            # Execute current phase
            try:
                self._execute_phase(self._phase)
            except Exception as e:
                print(f"[DAEMON] Phase {self._phase} error: {e}")
            
            # Advance phase
            self._phase = (self._phase + 1) % NUM_PHASES
            if self._phase == 0:
                self._cycle_count += 1
            
            # Sleep for tick interval
            # Use small increments so we can break out quickly on pause
            sleep_remaining = TICK_INTERVAL
            while sleep_remaining > 0 and not self._paused.is_set() and not self._stop_flag.is_set():
                chunk = min(0.02, sleep_remaining)  # 20ms chunks
                time.sleep(chunk)
                sleep_remaining -= chunk
    
    # ═══ PHASE EXECUTION ═══
    
    def _execute_phase(self, phase: int):
        """Dispatch to the correct phase handler."""
        handlers = {
            Phase.CHECK_GOALS:       self._phase_check_goals,
            Phase.EVALUATE:          self._phase_evaluate,
            Phase.DETERMINE_ACTIONS: self._phase_determine_actions,
            Phase.APPEND_RECOMMEND:  self._phase_append_recommend,
            Phase.PRIORITIZE:        self._phase_prioritize,
            Phase.REEVAL_IDENTITY:   self._phase_reeval_identity,
            Phase.USER_URGENCY:      self._phase_user_urgency,
            Phase.SUMMARIZE:         self._phase_summarize,
            Phase.CLEANUP:           self._phase_cleanup,
        }
        handler = handlers.get(phase)
        if handler:
            handler()
    
    # ─── PHASE 0: CHECK GOALS ───
    def _phase_check_goals(self):
        """
        Pull active goals, decay curiosity, refresh from memory.
        This is the "intake" phase.
        """
        self._goals.decay_curiosity()
        
        # Refresh identity keywords periodically (every 10 cycles)
        if self._cycle_count % 10 == 0:
            self._identity_keywords = get_indelible_keywords()
    
    # ─── PHASE 1: EVALUATE ───
    def _phase_evaluate(self):
        """
        Score each goal against curiosity + good sense.
        
        composite = curiosity * 0.30
                  + good_sense * 0.25
                  + importance * 0.25
                  + engagement * 0.20
        
        "Good sense" prevents chasing rabbit holes when frustrated,
        low-confidence, or identity-drifting.
        """
        good_sense = compute_good_sense(self._cog_state)
        state = self._cog_state.state
        
        with self._lock:
            self._candidate_scores.clear()
            
            for gid, goal in self._goals.goals.items():
                composite = (
                    goal.curiosity    * 0.30 +
                    good_sense        * 0.25 +
                    goal.importance   * 0.25 +
                    state.engagement  * 0.20
                )
                self._candidate_scores[gid] = composite
    
    # ─── PHASE 2: DETERMINE ACTIONS ───
    def _phase_determine_actions(self):
        """
        For goals above threshold, generate candidate actions.
        
        Action types:
          - "think"     → Internal reflection (no user needed)
          - "ask_user"  → Need user input to proceed
          - "revisit"   → Stale thread, worth poking
          - "explore"   → Curiosity-driven deep dive
          - "resolve"   → Close an open loop
        """
        threshold = compute_crap_threshold(self._cog_state)
        state = self._cog_state.state
        
        new_actions = []
        
        with self._lock:
            scored = sorted(
                self._candidate_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )
        
        for gid, score in scored:
            if score < threshold:
                continue
            
            goal = self._goals.goals.get(gid)
            if not goal:
                continue
            
            action_type = self._pick_action_type(goal, state, score)
            
            candidate = ActionCandidate(
                goal_id=gid,
                description=goal.description,
                action_type=action_type,
                composite_score=score,
                curiosity_score=goal.curiosity,
                identity_score=self._compute_identity_relevance(goal),
                needs_user=(action_type in ("ask_user", "resolve")),
                reasoning=self._generate_reasoning(goal, action_type, score),
            )
            new_actions.append(candidate)
        
        with self._lock:
            self._action_queue = new_actions
    
    def _pick_action_type(self, goal: Goal, state, score: float) -> str:
        """Determine what kind of action makes sense for this goal."""
        
        # Unresolved loops → try to resolve
        if goal.unresolved:
            return "resolve"
        
        # High curiosity + low cognitive load → explore
        if goal.curiosity > 0.6 and state.cognitive_load < 0.6:
            return "explore"
        
        # Stale goal (not active recently) → revisit
        age = time.time() - goal.last_active
        if age > 600:  # 10 minutes stale
            return "revisit"
        
        # Low confidence on important goal → ask user
        if goal.importance > 0.7 and state.confidence < 0.5:
            return "ask_user"
        
        # Default: internal thinking
        return "think"
    
    def _compute_identity_relevance(self, goal: Goal) -> float:
        """How relevant is this goal to core identity?"""
        if not self._identity_keywords:
            return 0.5  # Neutral if no keywords yet
        
        desc_lower = goal.description.lower()
        matches = sum(1 for kw in self._identity_keywords if kw in desc_lower)
        
        # Normalize: more matches = higher relevance, capped at 1.0
        return min(1.0, matches * 0.2)
    
    def _generate_reasoning(self, goal: Goal, action_type: str, score: float) -> str:
        """Short reasoning string for debugging/prompt injection."""
        parts = [f"score={score:.2f}"]
        
        if goal.curiosity > 0.5:
            parts.append(f"curiosity={goal.curiosity:.2f}")
        if goal.unresolved:
            parts.append("unresolved")
        
        age = time.time() - goal.last_active
        if age > 300:
            parts.append(f"stale={age:.0f}s")
        
        return f"{action_type}({', '.join(parts)})"
    
    # ─── PHASE 3: APPEND RECOMMENDATIONS ───
    def _phase_append_recommend(self):
        """
        Merge new action candidates into the recommendation list.
        Deduplicates by goal_id (keeps higher score).
        """
        with self._lock:
            existing = {r.goal_id: r for r in self._recommendations}
            
            for action in self._action_queue:
                if action.goal_id in existing:
                    # Keep higher score
                    if action.composite_score > existing[action.goal_id].composite_score:
                        existing[action.goal_id] = action
                else:
                    existing[action.goal_id] = action
            
            self._recommendations = list(existing.values())
    
    # ─── PHASE 4: PRIORITIZE ───
    def _phase_prioritize(self):
        """Sort recommendations by composite score, descending."""
        with self._lock:
            self._recommendations.sort(
                key=lambda r: r.composite_score,
                reverse=True
            )
    
    # ─── PHASE 5: RE-EVALUATE AGAINST IDENTITY ───
    def _phase_reeval_identity(self):
        """
        Second pass: check top items against core identity.
        
        Items that score LOW on identity relevance get demoted
        unless curiosity is very high (preserves rabbit holes
        that might not be identity-related but are interesting).
        """
        state = self._cog_state.state
        
        with self._lock:
            for rec in self._recommendations:
                identity_score = rec.identity_score
                
                # If identity relevance is low AND curiosity isn't saving it
                if identity_score < 0.3 and rec.curiosity_score < 0.6:
                    # Demote by 30%
                    rec.composite_score *= 0.70
                
                # If identity relevance is HIGH, boost
                elif identity_score > 0.7:
                    rec.composite_score *= 1.15
                    rec.composite_score = min(1.5, rec.composite_score)
            
            # Re-sort after adjustments
            self._recommendations.sort(
                key=lambda r: r.composite_score,
                reverse=True
            )
    
    # ─── PHASE 6: USER URGENCY ───
    def _phase_user_urgency(self):
        """
        Tag items that need user-in-the-loop.
        
        Urgency factors:
        - Action type is "ask_user" or "resolve"
        - Goal importance > 0.7 and stale > 5 minutes
        - Unresolved loop older than 15 minutes
        """
        now = time.time()
        
        with self._lock:
            self._user_urgent.clear()
            
            for rec in self._recommendations:
                if not rec.needs_user:
                    continue
                
                goal = self._goals.goals.get(rec.goal_id)
                if not goal:
                    continue
                
                age = now - goal.last_active
                
                # Urgency check
                is_urgent = (
                    (goal.importance > 0.7 and age > 300) or
                    (goal.unresolved and age > 900) or
                    rec.composite_score > 0.7
                )
                
                if is_urgent:
                    self._user_urgent.append(rec)
            
            # Fire callback if we have new urgent items
            if self._user_urgent and self._on_urgent_callback:
                try:
                    self._on_urgent_callback(len(self._user_urgent))
                except Exception:
                    pass
    
    # ─── PHASE 7: SUMMARIZE ───
    def _phase_summarize(self):
        """
        Build a one-liner focus summary.
        What is SignalBot "thinking about" right now?
        """
        with self._lock:
            if not self._recommendations:
                self._focus_summary = "Idle — no active cognitive threads."
                return
            
            top = self._recommendations[:3]
            topics = [r.description[:30] for r in top]
            
            good_sense = compute_good_sense(self._cog_state)
            
            if good_sense > 0.7:
                prefix = "Actively exploring"
            elif good_sense > 0.4:
                prefix = "Considering"
            else:
                prefix = "Low-confidence on"
            
            self._focus_summary = f"{prefix}: {' | '.join(topics)}"
    
    # ─── PHASE 8: CLEANUP (CRAP FILTER) ───
    def _phase_cleanup(self):
        """
        Purge items below the crap threshold.
        
        "Crap" = items where:
          composite_score < threshold
          AND curiosity < 0.3
          AND identity_relevance < 0.3
          AND engagement (global) < 0.4
        
        We're aggressive about this — cognitive bandwidth is precious.
        """
        threshold = compute_crap_threshold(self._cog_state)
        state = self._cog_state.state
        
        with self._lock:
            before_count = len(self._recommendations)
            
            survivors = []
            for rec in self._recommendations:
                # Triple gate: must fail ALL three to be purged
                is_crap = (
                    rec.composite_score < threshold and
                    rec.curiosity_score < 0.3 and
                    rec.identity_score < 0.3
                )
                
                # But spare it if engagement is high (user was interested)
                if is_crap and state.engagement > 0.6:
                    is_crap = False
                
                if not is_crap:
                    survivors.append(rec)
            
            purged = before_count - len(survivors)
            self._items_purged += purged
            self._recommendations = survivors
            
            # Also clean user_urgent of any purged items
            surviving_ids = {r.goal_id for r in survivors}
            self._user_urgent = [
                u for u in self._user_urgent
                if u.goal_id in surviving_ids
            ]
    
    # ═══ DIAGNOSTIC ═══
    
    def get_status(self) -> str:
        """Human-readable status string."""
        state = "RUNNING" if self.is_running else "PAUSED"
        with self._lock:
            n_recs = len(self._recommendations)
            n_urgent = len(self._user_urgent)
        
        return (
            f"[DAEMON] {state} | "
            f"cycle={self._cycle_count} | "
            f"phase={PHASE_NAMES.get(self._phase, '?')} | "
            f"recs={n_recs} | urgent={n_urgent} | "
            f"good_sense={compute_good_sense(self._cog_state):.2f}"
        )


# ═══════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════

_daemon: Optional[TemporalDaemon] = None

def get_daemon(goal_engine: Optional[GoalEngine] = None) -> TemporalDaemon:
    global _daemon
    if _daemon is None:
        _daemon = TemporalDaemon(goal_engine=goal_engine)
    return _daemon

def start_daemon():
    get_daemon().start()

def stop_daemon():
    get_daemon().stop()

def pause_daemon():
    get_daemon().pause()

def resume_daemon():
    get_daemon().resume()

def get_daemon_snapshot() -> CognitiveSnapshot:
    return get_daemon().get_snapshot()
