from google import genai
from google.genai import types
from pydantic import BaseModel
from dotenv import load_dotenv
import os, json

load_dotenv()
key = os.environ.get("GEMINI_API_KEY_1")
client = genai.Client(api_key=key)

class DiagnosisSchema(BaseModel):
    root_cause: str
    osi_layer: str
    confidence: float
    evidence: str
    next_command: str
    fix_steps: list[str]

symptom = "iBGP peer 10.1.1.2 is configured on Core1 but the BGP session status is stuck in Active."
topology_note = "Full-mesh iBGP within AS 65000. Core1 Loopback0 is 10.1.1.1, Core2 Loopback0 is 10.1.1.2."
show_outputs = "* 10.0.12.2, from 2.2.2.2, 00:15:30 ago, via GigabitEthernet0/1\n|\nshow run | section bgp:\nrouter bgp 65000\n bgp log-neighbor-changes"

from pathlib import Path
ROOT = Path(".").resolve()
with open("data/system_config.json", encoding="utf-8") as f:
    config = json.load(f)

from src.engine import load_system_prompt_with_few_shots
system_instruction = load_system_prompt_with_few_shots("prompts/diagnose_prompt.md")

user_content = (
    f'symptom: "{symptom}"\n'
    f'topology_note: "{topology_note}"\n'
    f"show_outputs: |\n  {show_outputs}"
)

resp = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=user_content,
    config=types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=config["model"]["temperature"],
        max_output_tokens=config["model"]["max_output_tokens"],
        response_mime_type="application/json",
        response_schema=DiagnosisSchema,
    )
)

print("raw response text:")
print(resp.text)
if resp.candidates:
    print("finish reason:", resp.candidates[0].finish_reason)
