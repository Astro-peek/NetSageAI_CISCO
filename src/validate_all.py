"""Run catalogue-wide diagnosis validation.

By default this script is read-only: it diagnoses every catalogue case and
prints coverage without modifying the operator audit log. Pass --write-audit
only when you intentionally want to append simulated review decisions.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.audit import log_decision
from src.checker import run_checker
from src.engine import diagnose
from src.metrics import compute_metrics


def simulated_decision(case_id: str, source: str, confidence: float) -> tuple[str, bool]:
    if source == "checker":
        return "Approve & Deploy", False
    if case_id in {"NET-002", "NET-010", "NET-020"}:
        return "Edit Commands", True
    if case_id == "NET-029" and confidence < 0.5:
        return "Reject", False
    return "Approve & Deploy", False


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate NetSage AI against every case in data/cases.csv.")
    parser.add_argument("--write-audit", action="store_true", help="append simulated operator decisions to data/audit_log.csv")
    args = parser.parse_args()

    cases_df = pd.read_csv(ROOT / "data" / "cases.csv")
    print(f"Starting validation of {len(cases_df)} cases...")
    if args.write_audit:
        print("Audit mode enabled: simulated decisions will be appended to data/audit_log.csv.")

    results = []
    for _, row in cases_df.iterrows():
        case_id = str(row["case_id"])
        checker_result = run_checker(str(row["show_outputs"]))
        diagnosis = diagnose(case_id)

        results.append(
            {
                "case_id": case_id,
                "source": diagnosis["source"],
                "rule_id": checker_result.get("rule_id", "") if checker_result else "",
                "confidence": diagnosis["confidence"],
            }
        )

        if args.write_audit:
            decision, edited = simulated_decision(case_id, str(diagnosis["source"]), float(diagnosis["confidence"]))
            log_decision(
                case_id=case_id,
                source=str(diagnosis["source"]),
                root_cause=str(diagnosis["root_cause"]),
                osi_layer=str(diagnosis["osi_layer"]),
                confidence=float(diagnosis["confidence"]),
                decision=decision,
                edited=edited,
            )

        print(f"{case_id}: {diagnosis['source']} ({diagnosis.get('rule_id', 'fallback')})")

    summary = pd.DataFrame(results)
    print("\nValidation completed.")
    print(summary.groupby("source").size().rename("count").to_string())

    if args.write_audit:
        metrics = compute_metrics()
        print("\n--- Audit Metrics After Append ---")
        print(f"Total Decisions Logged: {metrics.get('total_cases', 0)}")
        print(f"Agreement Rate: {metrics.get('agreement_rate', 0.0):.2f}%")
        print(f"Override Rate: {metrics.get('override_rate', 0.0):.2f}%")
        print(f"False Positive Rate: {metrics.get('false_positive_rate', 0.0):.2f}%")


if __name__ == "__main__":
    main()
