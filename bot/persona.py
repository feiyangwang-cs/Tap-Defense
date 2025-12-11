INTENT_DIFFICULTY = "SetDifficulty"
INTENT_VOLUME     = "SetVolume"
INTENT_RULES      = "ExplainRules"
INTENT_FALLBACK   = "FallbackIntent"
INTENT_PAUSE      = "PauseGame"
INTENT_RESUME     = "ResumeGame"

import random

def format_reply(intent: str, slots: dict) -> str:

    if intent == INTENT_DIFFICULTY:
        lvl = slots.get("level", "normal")
        if lvl == "easy":
            return "Easy mode, got it. I'll go easy on you… for now."
        if lvl == "hard":
            return "Hard mode locked in. Don't say I didn't warn you."
        return f"Okay, difficulty set to {lvl}."

    if intent == INTENT_VOLUME:
        pct = slots.get("percent", 50)
        try:
            pct_int = int(pct)
        except (TypeError, ValueError):
            pct_int = 50
        pct_int = max(0, min(100, pct_int))
        return f"Volume adjusted to {pct_int} percent. Hope that sounds better."

    if intent == INTENT_RULES:
        return (
            "Here's the short version: reach the goal without losing all your lives. "
            "Avoid enemies, grab useful items, and watch your health bar."
        )

    if intent == INTENT_PAUSE:
        return random.choice([
            "Fine, pausing the chaos. Catch your breath, hero.",
            "Game paused. Try not to forget what you were doing.",
            "Paused. Don't take forever, I do get bored."
        ])

    if intent == INTENT_RESUME:
        return "Back into the chaos. Try not to embarrass us again."

    if intent == INTENT_FALLBACK:
        return (
            "I didn't quite catch that. "
            "Try saying things like set difficulty to hard or volume forty percent."
        )

    return "I'm ready whenever you are."
