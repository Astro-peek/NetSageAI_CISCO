# NetSage AI — Automated Network Diagnostic Platform

## What this is
A hybrid diagnostic tool for Cisco/Packet Tracer network faults. It combines:
- A **deterministic rule engine** (`src/checker.py`) that pattern-matches known error signatures in `show` command output
- An **LLM reasoning layer** (`src/engine.py` + `prompts/diagnose_prompt.md`) for cases the rule engine doesn't recognize
- A **Human-in-the-Loop dashboard** (`src/app.py`) where an engineer reviews, edits, or rejects every proposed fix before anything is "deployed"
- An **audit log** (`docs/model_audit_log.md`) tracking how often the AI's diagnosis matched the human's final decision

The AI never executes commands directly. It only ever proposes.

## Project status
🚧 Planning phase — documentation and data schema being finalized before implementation begins.

## Folder structure
```
netsage-ai/
├── README.md
├── data/
│   ├── cases.csv              # 30 test scenarios (to be authored)
│   └── system_config.json     # thresholds, model params
├── prompts/
│   └── diagnose_prompt.md     # LLM system prompt + few-shot examples
├── docs/
│   ├── requirements.md        # functional requirements / PRD
│   ├── ARCHITECTURE.md        # system design
│   ├── fault_taxonomy.md      # symptom → OSI layer → fix reference
│   └── model_audit_log.md     # decision log template
└── src/
    ├── checker.py              # deterministic rule engine (not yet written)
    ├── engine.py                # orchestrator (not yet written)
    └── app.py                    # Streamlit dashboard (not yet written)
```

## How to run (once code exists)
```bash
python -m venv venv
source venv/bin/activate       # on Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run src/app.py
```

## Requirements (to install later)
- Python 3.10+
- streamlit
- pandas
- google-genai (Gemini API SDK)

## Next steps
1. Finalize `data/cases.csv` schema and populate with realistic fault scenarios
2. Finalize `prompts/diagnose_prompt.md` — system prompt + few-shot examples + JSON schema
3. Build `src/checker.py` against the fault taxonomy
4. Build `src/engine.py` to orchestrate checker → LLM fallback
5. Build `src/app.py` dashboard
6. Wire up `docs/model_audit_log.md` logging
