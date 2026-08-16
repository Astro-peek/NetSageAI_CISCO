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

## Few-shot examples

### Example 1 — STP blocking (Expected Behavior)
**Input:**
symptom: "Redundant link between Switch1 and Switch3 is unexpectedly unused, no load balancing"
topology_note: "Two switches connected via two trunk links for redundancy, STP running default settings"
show_outputs: "show spanning-tree vlan 10: Gi0/2 role Altn state BLK | Gi0/1 role Root state FWD"

**Expected output:**
```json
{
  "root_cause": "Spanning Tree Protocol (STP) has blocked port Gi0/2 to prevent a layer 2 loop. This is normal, expected behavior for redundant links in a spanning tree topology and is not a fault.",
  "osi_layer": "Data Link",
  "confidence": 1.0,
  "evidence": "Gi0/2 role Altn state BLK | Gi0/1 role Root state FWD",
  "next_command": "show spanning-tree summary",
  "fix_steps": [
    "No action required. STP is functioning correctly to prevent network loops.",
    "If load balancing is desired across links, consider configuring EtherChannel (Link Aggregation) or Per-VLAN Spanning Tree (PVST) to utilize different paths for different VLANs."
  ]
}
```

### Example 2 — STP root bridge misconfiguration
**Input:**
symptom: "Switch3 unexpectedly became the STP root bridge for VLAN 10, causing suboptimal traffic paths"
topology_note: "Switch1 was intended to be root bridge but had its priority changed during troubleshooting and never reverted"
show_outputs: "show spanning-tree vlan 10: Switch3 Bridge ID Priority 4096 | Switch1 Bridge ID Priority 32768 (default)"

**Expected output:**
```json
{
  "root_cause": "Switch3 has been configured with a lower STP bridge priority (4096) than the default priority (32768) on Switch1, causing Switch3 to win the root bridge election for VLAN 10.",
  "osi_layer": "Data Link",
  "confidence": 0.95,
  "evidence": "Switch3 Bridge ID Priority 4096 | Switch1 Bridge ID Priority 32768 (default)",
  "next_command": "configure terminal",
  "fix_steps": [
    "configure terminal",
    "spanning-tree vlan 10 root primary",
    "Or manually adjust priority on Switch1: spanning-tree vlan 10 priority 4096 (or lower than Switch3's priority)"
  ]
}
```

### Example 3 — NAT port exhaustion
**Input:**
symptom: "NAT translations stop being created once approximately 250 internal hosts are active simultaneously"
topology_note: "NAT overload configured using a single outside interface IP address"
show_outputs: "show ip nat statistics: Total active translations: 0 (max reached, prior peak ~64000 exceeded due to session churn) | Outside interface: GigabitEthernet0/1 (single public IP)"

**Expected output:**
```json
{
  "root_cause": "NAT translation table has reached its maximum capacity (port exhaustion) under heavy session churn, preventing new translations from being created for the ~250 active hosts on the single public IP interface Gi0/1.",
  "osi_layer": "Network",
  "confidence": 0.9,
  "evidence": "Total active translations: 0 (max reached, prior peak ~64000 exceeded due to session churn)",
  "next_command": "show ip nat statistics",
  "fix_steps": [
    "configure terminal",
    "Define a NAT pool with multiple public IP addresses instead of overloading a single interface IP, or adjust the NAT translation timeouts to clear inactive translations faster."
  ]
}
```

## Configuration Notes
- Model choice — `gemini-3.5-flash` is configured in `system_config.json` (fast, cost-effective,
  good for structured extraction)
- Temperature setting — set to 0.2 in config for consistency in diagnostic tasks
- Response schema is enforced via Gemini's `response_schema` with Pydantic model in `src/engine.py`
- `next_command` should be the single most important next diagnostic OR fix command to guide the operator
