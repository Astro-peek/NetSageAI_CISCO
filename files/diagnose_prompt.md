# Diagnose Prompt — Design Document

This is the design draft for the LLM system prompt used by `engine.py` when the
deterministic checker finds no match. Finalize this before wiring it into code.

**Note:** This project uses Google's Gemini API (`google-genai` SDK). Gemini supports
`response_schema` (paired with a Pydantic model — see `docs/PLAN.md` Phase 3), which
enforces valid JSON server-side. That means the schema below doesn't need to be repeated
inside the prompt text itself — defining it once as the Pydantic `Diagnosis` model is
enough. Keep the system prompt focused on *reasoning instructions*, not JSON formatting
rules, since the SDK handles the formatting guarantee.

## System prompt (draft)

```
You are a senior network engineer assisting with diagnosing Cisco IOS network faults
in a lab/training environment. You will be given:
- A symptom description
- A topology note
- Raw `show` command output

Your task:
1. Identify the OSI layer most responsible for the fault (Physical, Data Link, Network,
   Transport, or Application).
2. Identify the root cause, citing the SPECIFIC line(s) of show output as evidence.
3. Propose the exact Cisco IOS CLI commands needed to fix it.
4. Report a confidence score between 0 and 1 for your diagnosis.

Rules:
- Do NOT propose commands beyond what's needed to fix the identified fault.
- Do NOT guess if the evidence is insufficient — set confidence low and explain why in
  the evidence field.
- If the described behavior is actually normal/expected (not a real fault), say so
  clearly in root_cause and set confidence accordingly, rather than inventing a fix.
```

Output schema (enforced via Gemini's `response_schema`, defined once as a Pydantic model
in `src/engine.py` — not repeated in the prompt text):
```python
class Diagnosis(BaseModel):
    root_cause: str
    osi_layer: str        # Physical | Data Link | Network | Transport | Application
    confidence: float     # 0.0 - 1.0
    evidence: str          # quote the specific show output line(s)
    next_command: str      # single most important next diagnostic or fix command
    fix_steps: list[str]
```

## Few-shot examples (draft — needs 2-3 filled in)

Pick examples from `docs/fault_taxonomy.md` that are genuinely NOT handled by
`checker.py`'s deterministic rules (ambiguous/multi-symptom cases), so these examples
teach reasoning the rule engine can't do.

### Example 1 — [TODO: pick a case, e.g. DHCP not assigning addresses]
**Input:**
```
symptom: "PC3 is not receiving an IP address"
topology_note: "PC3 connects to Switch1, which trunks to Router1; DHCP pool configured on Router1"
show_outputs: |
  [TODO: paste realistic show output here]
```
**Expected output:**
```json
{
  "root_cause": "...",
  "osi_layer": "...",
  "confidence": 0.0,
  "evidence": "...",
  "next_command": "...",
  "fix_steps": ["..."]
}
```

### Example 2 — [TODO]
### Example 3 — [TODO]

## Open questions to resolve before finalizing
- Model choice — `gemini-2.5-flash` is the default in `system_config.json` (fast, cheap,
  good enough for structured extraction); check Google AI Studio for whether a newer
  Gemini model is available and preferable when you actually start building
- Temperature setting — likely should be low (e.g., 0-0.3) for consistency given this is
  a diagnostic task, not creative generation
- With `response_schema` enforcing valid JSON server-side, malformed JSON shouldn't occur
  in normal operation — but still handle `response.parsed is None` (can happen on safety
  blocks or empty responses) as a fallback case
- Whether `next_command` should be a diagnostic command (e.g., `show ip route`) or the
  actual fix command — needs to be consistent with what `app.py` expects to display
