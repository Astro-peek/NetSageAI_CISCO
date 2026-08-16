# NetSage AI — Model Audit Log

This file (or its structured equivalent, e.g. `audit_log.csv`) records every diagnosis
decision made through the dashboard. It's the source of truth for measuring whether the
system can be trusted.

## Log format

| Timestamp | Case ID | Diagnosis Source | Root Cause (proposed) | Confidence | Operator Decision | Edited? | Agreement |
|---|---|---|---|---|---|---|---|
| _(example)_ 2026-08-14T10:03:00 | NET-001 | checker | Gi0/0.30 administratively down | 1.00 | Approve & Deploy | No | Yes |
| _(example)_ 2026-08-14T10:11:00 | NET-004 | llm | Wildcard mask incorrect in ACL 101 | 0.82 | Edit Commands | Yes | Partial |
| _(example)_ 2026-08-14T10:15:00 | NET-007 | llm | Missing default route | 0.65 | Reject | — | No |

**Column definitions:**
- **Diagnosis Source** — `checker` (deterministic) or `llm`
- **Confidence** — from the structured JSON output (checker outputs 1.00 for exact matches)
- **Operator Decision** — Approve & Deploy / Edit Commands / Reject
- **Edited?** — Yes/No — did the operator change the proposed CLI commands?
- **Agreement** — Yes (approved as-is), Partial (approved after edit), No (rejected)

## Metrics to compute from this log (once populated)
- **Agreement rate** = Approved-as-is ÷ Total cases
- **Override rate** = Edited ÷ Total cases
- **False positive rate** = Rejected ÷ Total cases
- **Accuracy by OSI layer** = Agreement rate grouped by `osi_layer`
- **Accuracy by source** = Agreement rate for `checker` vs `llm` diagnoses separately
  (this tells you whether the LLM fallback is pulling its weight or dragging accuracy down)

## Target (per project doc)
Current documented baseline: **76.6% agreement rate**. Track whether changes to the
prompt, rules, or few-shot examples move this number up or down over time.

## Review cadence
Recommend reviewing this log after every ~10 cases processed to catch systematic
misdiagnosis patterns early (e.g., if all wildcard-mask cases are being rejected, the
taxonomy or prompt needs revision).
