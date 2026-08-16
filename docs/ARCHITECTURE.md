# NetSage AI — Architecture

## 1. Overview
Four-tier architecture: Data → Diagnostic Core → Human-in-the-Loop Gate → Audit & Logging.

## 2. Tier breakdown

### Tier 1 — Data
| File | Purpose |
|---|---|
| `data/cases.csv` | 30 structured fault scenarios |
| `data/system_config.json` | Model name, confidence thresholds, execution params |

### Tier 2 — Diagnostic Core Engine
| File | Purpose |
|---|---|
| `src/checker.py` | Deterministic regex/rule engine. Runs first on every case. |
| `src/engine.py` | Orchestrator. Calls checker; if no match, builds prompt and calls LLM; normalizes both outputs to the shared JSON schema. |
| `prompts/diagnose_prompt.md` | System prompt, few-shot examples, OSI-layer mapping, output schema for LLM calls. |

### Tier 3 — Human-in-the-Loop (HITL) Gate
| File | Purpose |
|---|---|
| `src/app.py` | Streamlit dashboard. Case selector, evidence viewer, diagnosis display, decision buttons (Approve & Deploy / Edit Commands / Reject). |

### Tier 4 — Audit & Logging
| File | Purpose |
|---|---|
| `docs/model_audit_log.md` | Append-only log of every decision, used to compute agreement/override/false-positive rates. |

## 3. Data flow (control flow)

```
Operator opens dashboard
        │
        ▼
Load cases.csv → operator selects case_id
        │
        ▼
Display symptom, topology_note, show_outputs
        │
        ▼
Run checker.py (deterministic rules)
        │
   ┌────┴────┐
   │         │
 Match    No match
   │         │
   ▼         ▼
Flag      Pass to engine.py → build prompt from
error     diagnose_prompt.md → call LLM API
   │         │
   └────┬────┘
        ▼
Normalize to structured JSON
(root_cause, osi_layer, confidence,
 evidence, next_command, fix_steps, source)
        │
        ▼
Display diagnosis + fix on dashboard UI
        │
        ▼
Operator decision gate
   │        │         │
Approve   Edit      Reject
   │        │         │
   └────────┼─────────┘
        ▼
Append decision to model_audit_log.md
        │
        ▼
End — action recorded
```

## 4. Design principles
1. **Deterministic-first.** Cheap, fast, zero hallucination risk — always tried before the LLM.
2. **Shared schema.** Both diagnostic paths (checker and LLM) MUST output the same JSON shape,
   so `app.py` doesn't need to know or care which one produced a result.
3. **No silent automation.** Every fix, however confident, stops at the HITL gate.
4. **Everything is auditable.** If a decision isn't logged, it didn't happen, as far as the
   system's metrics are concerned.

## 5. Open design questions (resolve before coding `engine.py`)
- What confidence threshold (if any) should influence how a diagnosis is visually flagged
  in the dashboard (e.g., low-confidence LLM diagnoses shown with a warning)?
- Should `checker.py` be allowed to have partial matches (e.g., detects a VLAN issue but
  can't determine severity), and if so, does that route to LLM as well for enrichment?
- Which LLM provider/model, and what's the fallback if the API call fails or times out?
