import csv
import os
from datetime import datetime
from typing import Dict, Any

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_PATH = os.path.join(LOG_DIR, "interactions.csv")


FIELDNAMES = [
    "timestamp",
    "modality",         # "voice" / "text"
    "input_transcript", # ASR 
    "intent",
    "confidence",
    "slots_json",
    "action",           # "set_difficulty", "set_volume", "explain_rules", "noop", "fallback"
    "success",
    "latency_ms",
]


def _ensure_log_file():
    os.makedirs(LOG_DIR, exist_ok=True)
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()


def log_interaction(
    modality: str,
    input_transcript: str,
    intent: str,
    confidence: float,
    slots: Dict[str, Any],
    action: str,
    success: bool,
    latency_ms: float,
):
    _ensure_log_file()

    row = {
        "timestamp": datetime.utcnow().isoformat(),
        "modality": modality,
        "input_transcript": input_transcript or "",
        "intent": intent or "",
        "confidence": f"{confidence:.3f}" if confidence is not None else "",
        "slots_json": repr(slots or {}),
        "action": action,
        "success": "1" if success else "0",
        "latency_ms": f"{latency_ms:.1f}",
    }

    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(row)
