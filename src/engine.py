# pyrefly: ignore [missing-import]
import os
import re
import json
import time
from pathlib import Path
import pandas as pd
import streamlit as st
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv
from src.checker import run_checker

# Load environment variables from .env file (for local development)
load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "system_config.json"

def _load_api_keys() -> list[str]:
    """Load up to 5 Gemini API keys from Streamlit secrets or environment variables.
    Supports GEMINI_API_KEY_1..5 or falls back to GEMINI_API_KEY."""
    keys = []
    # Try Streamlit secrets first (for cloud deployment)
    try:
        for i in range(1, 6):
            k = st.secrets.get(f"GEMINI_API_KEY_{i}", "").strip()
            if k:
                keys.append(k)
    except Exception:
        # Fallback to environment variables (for local development)
        for i in range(1, 6):
            k = os.environ.get(f"GEMINI_API_KEY_{i}", "").strip()
            if k:
                keys.append(k)
    
    if not keys:
        # Try fallback to single GEMINI_API_KEY
        try:
            fallback = st.secrets.get("GEMINI_API_KEY", "").strip()
        except Exception:
            fallback = os.environ.get("GEMINI_API_KEY", "").strip()
        if fallback:
            keys.append(fallback)
    return keys

_API_KEYS = _load_api_keys()
_key_index = 0  # global round-robin pointer

def _next_client():
    """Return a Gemini client using the next available API key (round-robin)."""
    global _key_index
    if not _API_KEYS:
        raise ValueError("No Gemini API keys found. Set GEMINI_API_KEY or GEMINI_API_KEY_1..5 in .env")
    key = _API_KEYS[_key_index % len(_API_KEYS)]
    _key_index += 1
    return genai.Client(api_key=key)


# Schema for the LLM output
class DiagnosisSchema(BaseModel):
    root_cause: str
    osi_layer: str
    confidence: float
    evidence: str
    next_command: str
    fix_steps: list[str]

def load_system_prompt_with_few_shots(path: str) -> str:
    prompt_path = Path(path)
    if not prompt_path.exists():
        return "You are a senior network engineer assisting with diagnosing Cisco IOS network faults in a lab/training environment. Identify the OSI layer, root cause with evidence, exact fix commands, and confidence score."
    
    with prompt_path.open("r", encoding="utf-8") as f:
        content = f.read()
    
    # 1. Extract system prompt block
    sys_match = re.search(r'## System prompt \(draft\)\s+```(?:markdown)?\n(.*?)```', content, re.DOTALL | re.IGNORECASE)
    sys_prompt = sys_match.group(1).strip() if sys_match else ""
    
    # 2. Extract few-shot examples section
    few_shot_match = re.search(r'## Few-shot examples\s+(.*?)(?=\n## Open questions|\Z)', content, re.DOTALL | re.IGNORECASE)
    few_shots = few_shot_match.group(1).strip() if few_shot_match else ""
    
    full_instruction = sys_prompt
    if few_shots:
        full_instruction += "\n\n### Few-Shot Examples\n" + few_shots
        
    return full_instruction

def diagnose(case_id: str) -> dict:
    # 1. Load config
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        config = json.load(f)
        
    cases_path = ROOT / config["paths"]["cases_csv"]
    prompt_path = ROOT / config["paths"]["prompt_template"]
    
    # 2. Load cases and find the selected case
    df = pd.read_csv(cases_path)
    case_row = df[df["case_id"] == case_id]
    if case_row.empty:
        return {
            "case_id": case_id,
            "root_cause": f"Case ID {case_id} not found",
            "osi_layer": "N/A",
            "confidence": 0.0,
            "evidence": "N/A",
            "next_command": "",
            "fix_steps": [],
            "source": "error"
        }
    
    case = case_row.iloc[0]
    show_outputs = case["show_outputs"]
    symptom = case["symptom"]
    topology_note = case["topology_note"]
    
    # 3. Try deterministic checker first
    checker_res = run_checker(show_outputs)
    if checker_res:
        # Normalize and merge case_id
        checker_res["case_id"] = case_id
        return checker_res

    # 4. LLM Fallback — rotate through all available API keys on 429
    if not _API_KEYS:
        return {
            "case_id": case_id, "root_cause": "No API keys configured",
            "osi_layer": "Application", "confidence": 0.0,
            "evidence": "Set GEMINI_API_KEY or GEMINI_API_KEY_1..5 in .env",
            "next_command": "", "fix_steps": [], "source": "error"
        }

    system_instruction = load_system_prompt_with_few_shots(prompt_path)
    user_content = (
        f"symptom: \"{symptom}\"\n"
        f"topology_note: \"{topology_note}\"\n"
        f"show_outputs: |\n  {show_outputs}"
    )

    n_keys = len(_API_KEYS)
    last_err = None

    # Try each key in rotation; do up to 2 full rounds max
    for attempt in range(n_keys * 2):
        client = _next_client()
        try:
            response = client.models.generate_content(
                model=os.environ.get("GEMINI_MODEL", config["model"]["model_name"]),
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=config["model"]["temperature"],
                    max_output_tokens=config["model"]["max_output_tokens"],
                    response_mime_type="application/json",
                    response_schema=DiagnosisSchema,
                )
            )
            parsed: DiagnosisSchema = response.parsed
            if parsed is None:
                raise ValueError("LLM returned an empty or unparseable response")
            return {
                "case_id": case_id,
                "root_cause": parsed.root_cause,
                "osi_layer": parsed.osi_layer,
                "confidence": float(parsed.confidence),
                "evidence": parsed.evidence,
                "next_command": parsed.next_command,
                "fix_steps": parsed.fix_steps,
                "source": "llm"
            }
        except Exception as e:
            last_err = e
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                # Rotate to next key; if we just finished a full round, wait for the reset window
                if (attempt + 1) % n_keys == 0:
                    delay_match = re.search(r"retryDelay.*?'(\d+)s'", err_str)
                    wait_sec = int(delay_match.group(1)) + 2 if delay_match else 65
                    print(f"  [All keys exhausted] Waiting {wait_sec}s for quota reset...")
                    time.sleep(wait_sec)
                else:
                    print(f"  [Key {(attempt % n_keys)+1} rate-limited] Rotating to next key...")
            else:
                break  # Non-rate-limit error; don't retry

    return {
        "case_id": case_id,
        "root_cause": f"Diagnosis failed: {str(last_err)}",
        "osi_layer": "Application",
        "confidence": 0.0,
        "evidence": f"API Error: {str(last_err)}",
        "next_command": "",
        "fix_steps": [],
        "source": "error"
    }
