# NetSage AI — Requirements Document

## 1. Purpose
Define what the system must do before any code is written, so implementation has a clear target.

## 2. Primary users
- Network engineering students in a lab environment (e.g., Cisco Packet Tracer)
- Junior network engineers troubleshooting multi-layer faults

## 3. Functional requirements

### FR-1: Case ingestion
The system SHALL load a dataset of network fault scenarios from `data/cases.csv`, each containing:
- `case_id`, `symptom`, `topology_note`, `concept_tag`, `severity`, `show_outputs`, `expected_fault`

### FR-2: Deterministic diagnosis
The system SHALL first attempt to diagnose a fault using regex/pattern rules against `show_outputs`.
Known patterns to detect at minimum:
- Interface administratively down
- Line protocol down
- VLAN ID mismatch between switch and router sub-interface
- Missing/incorrect ACL entry
- Incorrect wildcard mask
- Missing or incorrect default route / next-hop

### FR-3: LLM fallback diagnosis
IF the deterministic checker finds no match, THEN the system SHALL pass the case to an LLM using
the prompt defined in `prompts/diagnose_prompt.md`, requesting a structured JSON response.

### FR-4: Structured output schema
Every diagnosis (rule-based or LLM-based) SHALL be normalized to:
```json
{
  "case_id": "string",
  "root_cause": "string",
  "osi_layer": "string",
  "confidence": "float 0-1",
  "evidence": "string",
  "next_command": "string",
  "fix_steps": ["string", "..."],
  "source": "checker | llm"
}
```

### FR-5: Human-in-the-loop approval
The dashboard SHALL present each diagnosis and require the operator to choose one of:
- **Approve & Deploy** — accept fix as-is
- **Edit Commands** — modify proposed CLI before accepting
- **Reject** — flag as false positive / incorrect diagnosis
No fix is ever auto-applied without one of these explicit actions.

### FR-6: Audit logging
Every decision SHALL be appended to `docs/model_audit_log.md` (or a structured log file) with:
timestamp, case_id, diagnosis source, confidence, operator decision, and whether the
operator's decision agreed with the AI's proposed diagnosis.

### FR-7: Metrics
The system SHALL be able to compute, from the audit log:
- Agreement rate (% of cases where operator approved without edits)
- False positive rate (% rejected)
- Override rate (% edited)
- Breakdown of accuracy by OSI layer / fault type

## 4. Non-functional requirements
- **Safety:** No command is ever executed against a live device by this system — CLI output is
  display-only, copy/paste by the human.
- **Determinism first:** Rule-based path must always be attempted before LLM fallback, to
  minimize hallucination risk and API cost.
- **Transparency:** Every diagnosis must show its evidence (the specific line(s) of `show` output
  that led to the conclusion) — no black-box conclusions.
- **Portability:** File paths must work cross-platform (use `pathlib`, not hardcoded slashes).

## 5. Out of scope (v1)
- Live device integration (SSH/Netmiko execution) — explicitly NOT part of this system
- Multi-vendor support (Juniper, Arista, etc.) — Cisco IOS only for v1
- Real-time monitoring / alerting — this is a diagnose-on-demand tool, not a monitoring system

## 6. Success criteria
- All 30 cases in `cases.csv` produce a structured diagnosis (via checker or LLM)
- Agreement rate is measurable and logged
- A user with no prior context can open the dashboard and complete one full diagnosis →
  decision → log cycle without instruction
