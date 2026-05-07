import json
from pathlib import Path
from datetime import datetime

HISTORY_FILE = Path("history.json")

def load_history():
    if not HISTORY_FILE.exists():
        return []

    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_history_item(item):
    history = load_history()
    history.insert(0, item)

    with HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def create_history_item(file_name, final_label, risk_level, risk_score, transcript, final_lexicon_cues=None):
    return {
        "file_name": file_name,
        "final_label": final_label,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "transcript": transcript,
        "final_lexicon_cues": final_lexicon_cues or [],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }