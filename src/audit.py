import csv
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG_PATH = ROOT / "data" / "audit_log.csv"

def log_decision(case_id: str, source: str, root_cause: str, osi_layer: str, confidence: float, decision: str, edited: bool) -> None:
    # Determine edited string
    edited_str = "Yes" if edited else "No"
    
    # Determine agreement
    if decision == "Approve & Deploy":
        agreement = "Yes"
    elif decision == "Edit Commands":
        agreement = "Partial"
    else:  # Reject
        agreement = "No"
        
    timestamp = datetime.now().isoformat()
    
    # Ensure directory exists
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if file exists to write header
    file_exists = AUDIT_LOG_PATH.exists()
    
    with AUDIT_LOG_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "case_id", "source", "root_cause", "osi_layer", "confidence", "decision", "edited", "agreement"])
        writer.writerow([timestamp, case_id, source, root_cause, osi_layer, confidence, decision, edited_str, agreement])
