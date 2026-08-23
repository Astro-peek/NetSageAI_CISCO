import csv
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG_PATH = ROOT / "data" / "audit_log.csv"

def log_decision(case_id: str, source: str, root_cause: str, osi_layer: str, confidence: float, decision: str, edited: bool) -> None:
    edited_str = "Yes" if edited else "No"

    if decision == "Approve & Deploy":
        agreement = "Yes"
    elif decision == "Edit Commands":
        agreement = "Partial"
    else:
        agreement = "No"

    timestamp = datetime.now().isoformat()
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_exists = AUDIT_LOG_PATH.exists()

    with AUDIT_LOG_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "case_id", "source", "root_cause", "osi_layer", "confidence", "decision", "edited", "agreement"])
        writer.writerow([timestamp, case_id, source, root_cause, osi_layer, confidence, decision, edited_str, agreement])


def append_responsible_log(case_id: str, title: str, ai_proposed: str, operator_correction: str, severity: str, lesson: str) -> None:
    log_file = ROOT / "data" / "ai_responsible_log.json"
    logs = []

    if log_file.exists():
        try:
            with log_file.open("r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            pass

    new_log = {
        "case_id": case_id,
        "title": title,
        "ai_proposed_root_cause": ai_proposed,
        "operator_correction": operator_correction,
        "severity": severity,
        "responsible_ai_lesson": lesson
    }

    logs.append(new_log)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    with log_file.open("w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)
