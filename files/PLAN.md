# NetSage AI — Implementation Plan

This is the execution plan for building NetSage AI from the current state (documentation +
data schema complete) to a working system. Follow the phases in order — each one depends
on the previous being done and tested.

## Current state (as of this plan)
✅ Done:
- `README.md`, `docs/requirements.md`, `docs/ARCHITECTURE.md`, `docs/fault_taxonomy.md`,
  `docs/model_audit_log.md` — all finalized
- `data/system_config.json` — config skeleton defined
- `data/cases.csv` — 30 fault scenarios fully populated

🚧 Not started:
- `prompts/diagnose_prompt.md` — system prompt drafted, few-shot examples still `[TODO]`
- `src/checker.py`, `src/engine.py`, `src/app.py` — no code written yet

---

## Phase 0 — Environment setup
**Goal:** A working Python environment with dependencies installed.

1. Create virtual environment: `python -m venv venv`
2. Create `requirements.txt`:
   ```
   streamlit
   pandas
   google-genai
   python-dotenv
   pydantic
   ```
3. Install: `pip install -r requirements.txt`
4. Get a free API key from Google AI Studio (aistudio.google.com/app/apikey)
5. Create `.env` file (gitignored) for `GEMINI_API_KEY`
6. Create `.gitignore` (venv/, .env, __pycache__/, *.pyc)
7. Initialize git repo, commit current state (docs + data)

**Acceptance:** `python -c "import streamlit, pandas; from google import genai"` runs with no errors.

---

## Phase 1 — Finalize the prompt (before writing any orchestration code)
**Goal:** `prompts/diagnose_prompt.md` has real few-shot examples, ready to be loaded by code.

1. From `data/cases.csv`, select 2-3 cases that require genuine reasoning, not simple
   pattern matching. Recommended: `NET-011` (STP blocking — false positive test),
   `NET-021` (STP root bridge judgment call), `NET-029` (NAT exhaustion — needs inference
   from statistics, not a keyword match).
2. Fill in the `[TODO]` blocks in `diagnose_prompt.md` with those cases' real
   `show_outputs` as input and a hand-written correct JSON diagnosis as expected output.
3. Manually test the prompt in Google AI Studio (aistudio.google.com) or a quick throwaway
   script against 2-3 cases NOT in the few-shot set, to sanity check the model follows the
   JSON schema reliably before wiring it into code. Prefer defining the schema as a Pydantic
   model and using Gemini's native `response_schema` support (see Phase 3) rather than
   relying on prompt instructions alone to enforce JSON — this guarantees valid JSON instead
   of just hinting at it.

**Acceptance:** Calling Gemini with the system prompt + a sample case (using
`response_schema`) reliably returns a validated `Diagnosis` object on 5/5 manual tries,
with sensible (not generic/hedging) values in `root_cause` and `evidence`.

---

## Phase 2 — Build `src/checker.py` (deterministic rule engine)
**Goal:** A pure-Python module that takes `show_outputs` text and returns either a
structured diagnosis dict or `None` (no match).

1. Write one function per fault pattern from `docs/fault_taxonomy.md`, e.g.:
   - `check_admin_down(show_output: str) -> dict | None`
   - `check_line_protocol_down(show_output: str) -> dict | None`
   - `check_vlan_mismatch(show_output: str) -> dict | None`
   - `check_wildcard_mask(show_output: str) -> dict | None`
   - `check_missing_default_route(show_output: str) -> dict | None`
   - `check_missing_acl_entry(show_output: str) -> dict | None`
   - (continue for each row in the taxonomy table)
2. Write a top-level `run_checker(show_output: str) -> dict | None` that tries each
   function in order and returns the first match, tagged `"source": "checker"` and
   `"confidence": 1.0`.
3. Write unit tests (`tests/test_checker.py`) using the actual `show_outputs` strings
   from `cases.csv` as fixtures — one test per case where `checker.py` SHOULD catch it.
4. Deliberately verify `NET-011` (STP blocking, not really a fault) returns `None` or a
   "no action needed" result rather than a false-positive fix.

**Acceptance:** Running `checker.py` against all 30 cases in `cases.csv`, it correctly
identifies matches for every case tagged as an obvious pattern-matchable fault (admin
down, line protocol down, missing route, etc.), and correctly returns no-match or
"not a fault" for ambiguous/judgment cases meant for the LLM.

---

## Phase 3 — Build `src/engine.py` (orchestrator)
**Goal:** Given a `case_id`, produce one final structured diagnosis, trying checker first.

1. Load `data/cases.csv` via pandas.
2. Load `data/system_config.json` for model name, temperature, thresholds.
3. Load `prompts/diagnose_prompt.md`, parse out system prompt text.
4. Define the diagnosis schema as a Pydantic model (this doubles as validation AND the
   schema handed to Gemini):
   ```python
   from pydantic import BaseModel

   class Diagnosis(BaseModel):
       root_cause: str
       osi_layer: str
       confidence: float
       evidence: str
       next_command: str
       fix_steps: list[str]
   ```
5. Write `diagnose(case_id: str) -> dict`:
   - Look up the case row
   - Call `checker.run_checker(show_outputs)`
   - If match → normalize to shared schema, tag `source: checker`, `confidence: 1.0`, return
   - If no match → call the Gemini API using the client pattern below, tag `source: llm`,
     return
   ```python
   from google import genai
   from google.genai import types
   import os

   client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

   response = client.models.generate_content(
       model=config["model"]["model_name"],   # e.g. "gemini-2.5-flash"
       contents=f"{case_symptom}\n\n{topology_note}\n\n{show_outputs}",
       config=types.GenerateContentConfig(
           system_instruction=system_prompt,   # loaded from diagnose_prompt.md
           temperature=config["model"]["temperature"],
           response_mime_type="application/json",
           response_schema=Diagnosis,          # enforces the schema server-side
       ),
   )
   diagnosis: Diagnosis = response.parsed        # already validated against the schema
   ```
   Using `response_schema` with a Pydantic model means Gemini enforces valid JSON matching
   the schema server-side — `response.parsed` gives back a validated `Diagnosis` object
   directly, no manual JSON parsing/retry loop needed for malformed structure.
6. Handle remaining failure modes: API timeout/network error, or `response.parsed` being
   `None` (can still happen on refusals or empty responses) — return a fallback dict with
   `confidence: 0` and a clear "diagnosis failed" message. Never let this crash the dashboard.
7. Write `tests/test_engine.py` running `diagnose()` against all 30 cases and asserting
   every case returns a valid schema-conformant dict (regardless of source).

**Acceptance:** `python -c "from src.engine import diagnose; print(diagnose('NET-001'))"`
returns valid JSON matching the schema in `docs/requirements.md` FR-4, for every case_id
in `cases.csv`. Verify this specifically for a case that routes to Gemini (e.g. NET-011),
not just checker-handled cases.

---

## Phase 4 — Build `src/app.py` (Streamlit dashboard)
**Goal:** A working HITL UI per the flowchart in `docs/ARCHITECTURE.md`.

1. Page layout:
   - Sidebar or dropdown: case selector (populated from `cases.csv`)
   - Main panel: symptom, topology_note, and show_outputs displayed clearly
   - "Run Diagnosis" button → calls `engine.diagnose(case_id)`
   - Diagnosis result panel: root_cause, osi_layer, confidence (with visual indicator if
     below `system_config.json`'s `show_confidence_warning_below` threshold), evidence,
     fix_steps as an editable text area
2. Decision buttons: **Approve & Deploy**, **Edit Commands** (unlocks the editable CLI
   text area before confirming), **Reject**
3. On any decision, append a row to the audit log (see Phase 5) and show a confirmation
   message. Do not allow re-submitting the same case+decision twice without a fresh run.
4. Use `st.session_state` to hold the current diagnosis between button clicks so the UI
   doesn't lose state on rerun.

**Acceptance:** A user can open the dashboard, pick any of the 30 cases, run a diagnosis,
see it displayed with evidence, and complete all three decision paths (approve/edit/reject)
without errors.

---

## Phase 5 — Wire up audit logging
**Goal:** Every decision from Phase 4 is durably recorded per the format in
`docs/model_audit_log.md`.

1. Decide storage format for the actual running log: a `docs/audit_log.csv` (structured,
   easy to compute metrics from) is recommended over hand-editing the `.md` file. Keep
   `model_audit_log.md` as the human-readable template/spec; log real data to CSV.
2. Write `src/audit.py` with `log_decision(case_id, source, root_cause, confidence,
   decision, edited: bool) -> None` that appends a timestamped row.
3. Wire this into each of the three decision buttons in `app.py`.
4. Write a small `src/metrics.py` (or a Streamlit expander section in `app.py`) that reads
   `audit_log.csv` and computes: agreement rate, override rate, false positive rate,
   accuracy broken down by `osi_layer` and by `source` (checker vs. llm).

**Acceptance:** After running through all 30 cases in the dashboard and making a decision
on each, `audit_log.csv` has 30 rows, and the metrics view correctly computes the
agreement rate from that data.

---

## Phase 6 — End-to-end validation
**Goal:** Confirm the full system meets `docs/requirements.md`'s success criteria.

1. Run all 30 cases through the dashboard from a cold start.
2. Confirm every case produces a diagnosis (no crashes, no unhandled exceptions).
3. Confirm `NET-011` does not get force-fit into a false "fix."
4. Compute the overall agreement rate; compare against the documented 76.6% baseline —
   this run is your real baseline going forward, not the number from the original doc.
5. Have someone unfamiliar with the project open the dashboard and complete one full
   diagnosis cycle with zero explanation — this validates FR from the requirements doc
   ("a user with no prior context can operate it").

**Acceptance:** All items above pass. Document the actual results in
`docs/model_audit_log.md` as the new baseline.

---

## Phase 7 — Polish & stretch goals (optional, after core works)
- Add filtering/search to the case selector (by severity, OSI layer, concept_tag)
- Add a summary dashboard tab showing metrics from Phase 5 as charts (bar chart of
  agreement rate by fault type, etc.)
- Add export of a single case's diagnosis as a PDF/text report
- Add confidence-based visual flagging (e.g., red banner for low-confidence LLM diagnoses)
- Expand `cases.csv` beyond 30 if more fault variety is wanted
- Add multi-vendor support (explicitly out of scope for v1 per requirements.md — only
  attempt if v1 is fully validated first)

---

## Summary checklist

| Phase | Deliverable | Depends on |
|---|---|---|
| 0 | Working Python env | — |
| 1 | Finalized `diagnose_prompt.md` with few-shot examples | Phase 0 |
| 2 | `src/checker.py` + tests | Phase 0 |
| 3 | `src/engine.py` + tests | Phase 1, 2 |
| 4 | `src/app.py` dashboard | Phase 3 |
| 5 | Audit logging + metrics | Phase 4 |
| 6 | End-to-end validation | Phase 5 |
| 7 | Polish (optional) | Phase 6 |

**Do not skip ahead.** Each phase's acceptance criteria should pass before starting the
next — this is a small project but the HITL safety guarantee only holds if every layer
(checker → engine → dashboard → audit) is actually tested, not assumed to work.
