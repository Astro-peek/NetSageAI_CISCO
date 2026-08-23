from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG_PATH = ROOT / "data" / "audit_log.csv"

def compute_metrics() -> dict:
    if not AUDIT_LOG_PATH.exists():
        return {}
    try:
        df = pd.read_csv(AUDIT_LOG_PATH)
        if df.empty:
            return {}

        total = len(df)
        if total == 0:
            return {}

        agreement_count = len(df[df["agreement"] == "Yes"])
        override_count = len(df[df["edited"] == "Yes"])
        false_positive_count = len(df[df["agreement"] == "No"])

        agreement_rate = (agreement_count / total) * 100
        override_rate = (override_count / total) * 100
        false_positive_rate = (false_positive_count / total) * 100

        metrics_by_source = {}
        for src in df["source"].dropna().unique():
            src_df = df[df["source"] == src]
            src_total = len(src_df)
            if src_total > 0:
                src_agreement = len(src_df[src_df["agreement"] == "Yes"])
                metrics_by_source[src] = {
                    "total": src_total,
                    "agreement_rate": (src_agreement / src_total) * 100
                }

        metrics_by_osi = {}
        for osi in df["osi_layer"].dropna().unique():
            osi_df = df[df["osi_layer"] == osi]
            osi_total = len(osi_df)
            if osi_total > 0:
                osi_agreement = len(osi_df[osi_df["agreement"] == "Yes"])
                metrics_by_osi[osi] = {
                    "total": osi_total,
                    "agreement_rate": (osi_agreement / osi_total) * 100
                }

        return {
            "total_cases": total,
            "agreement_rate": agreement_rate,
            "override_rate": override_rate,
            "false_positive_rate": false_positive_rate,
            "by_source": metrics_by_source,
            "by_osi": metrics_by_osi
        }
    except Exception as e:
        print(f"Error computing metrics: {e}")
        return {}


def compute_ai_metrics() -> dict:
    if not AUDIT_LOG_PATH.exists():
        return {}
    try:
        df = pd.read_csv(AUDIT_LOG_PATH)
        if df.empty:
            return {}

        ai_df = df[df["source"] == "llm"]
        total_ai = len(ai_df)
        if total_ai == 0:
            return {
                "total_ai_cases": 0,
                "ai_agreement_rate": 100.0,
                "ai_override_rate": 0.0,
                "ai_reject_rate": 0.0
            }

        ai_agreement = len(ai_df[ai_df["agreement"] == "Yes"])
        ai_override = len(ai_df[ai_df["edited"] == "Yes"])
        ai_reject = len(ai_df[ai_df["agreement"] == "No"])

        return {
            "total_ai_cases": total_ai,
            "ai_agreement_rate": (ai_agreement / total_ai) * 100,
            "ai_override_rate": (ai_override / total_ai) * 100,
            "ai_reject_rate": (ai_reject / total_ai) * 100
        }
    except Exception as e:
        print(f"Error computing AI metrics: {e}")
        return {}
