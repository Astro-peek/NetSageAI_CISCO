# NetSage AI - Automated Network Diagnostic Platform

NetSage AI is a human-in-the-loop diagnostic console for Cisco IOS and Packet
Tracer lab faults. It loads a catalogue of network incidents, diagnoses each
case with a deterministic rule engine first, falls back to Gemini only for
unknown patterns, and records the operator's final review decision.

The system never executes Cisco commands. Proposed fixes are display-only.

## Current Functionality

- Streamlit operator console in `src/app.py`
- 30 structured test scenarios in `data/cases.csv`
- Deterministic checker in `src/checker.py`
- Gemini fallback orchestrator in `src/engine.py`
- Structured diagnosis schema shared by checker and LLM output
- Case explorer with severity, OSI layer, and text search filters
- Rule coverage dashboard showing deterministic coverage by case
- Audit logging to `data/audit_log.csv`
- Metrics for agreement, overrides, rejections, source, and OSI layer
- Read-only catalogue validation script in `src/validate_all.py`
- Pytest coverage for checker and engine schema behavior

## How Diagnosis Works

1. The operator selects a case from the dashboard.
2. The app displays the symptom, topology note, and raw Cisco `show` output.
3. `src/checker.py` runs deterministic evidence rules first.
4. If no rule matches, `src/engine.py` calls Gemini using `prompts/diagnose_prompt.md`.
5. The result is normalized to:

```json
{
  "case_id": "NET-001",
  "root_cause": "string",
  "osi_layer": "Physical | Data Link | Network | Transport | Application",
  "confidence": 0.0,
  "evidence": "specific show output evidence",
  "next_command": "single next diagnostic or fix command",
  "fix_steps": ["command or operator step"],
  "source": "checker | llm | error"
}
```

6. The operator approves, edits, or rejects the proposal.
7. The decision is appended to `data/audit_log.csv`.

## Run The App

```powershell
venv\Scripts\python.exe -m streamlit run src\app.py
```

Then open:

```text
http://localhost:8501
```

## Install From Scratch

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run src\app.py
```

## Gemini Configuration

Gemini is only required for cases that do not match the deterministic checker.
Set one key:

```text
GEMINI_API_KEY=your-key
```

Or up to five rotating keys:

```text
GEMINI_API_KEY_1=your-key
GEMINI_API_KEY_2=your-key
```

You can override the configured model at runtime:

```text
GEMINI_MODEL=gemini-model-name
```

## Validation And Tests

Run tests:

```powershell
venv\Scripts\python.exe -m pytest -q
```

Run catalogue validation without touching the audit log:

```powershell
venv\Scripts\python.exe src\validate_all.py
```

Append simulated operator decisions intentionally:

```powershell
venv\Scripts\python.exe src\validate_all.py --write-audit
```

## Project Layout

```text
data/
  cases.csv
  system_config.json
  audit_log.csv
docs/
  ARCHITECTURE.md
  fault_taxonomy.md
  model_audit_log.md
  requirements.md
prompts/
  diagnose_prompt.md
src/
  app.py
  audit.py
  checker.py
  engine.py
  metrics.py
  validate_all.py
tests/
  test_checker.py
  test_engine.py
```
