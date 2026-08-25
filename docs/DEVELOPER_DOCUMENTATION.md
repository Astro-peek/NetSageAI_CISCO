# NetSage AI — Developer Notes & Documentation

**Developer:** Paras Gupta  
**Project:** NetSage AI (Cisco IOS Diagnostic Console)  
**Implementation:** Manually built rule engine, custom Streamlit styling, and Gemini key-rotation fallback.

---

## 1. How I Thought About This (Design Choices)

When I started building this console, my main goal was to create a tool that helps diagnose Cisco IOS and Packet Tracer faults quickly and safely, without sending every single thing to an LLM. Here's what I kept in mind while writing the code:

### 1.1 Deterministic Rules First (Save cost & time)
Passing raw Cisco output to a LLM takes several seconds and costs tokens. More importantly, LLMs can hallucinate commands. Since network issues often have very obvious signatures (like `administratively down`), I decided to write local python checks first. 
* I manually wrote **26 regular expression checks** in `src/checker.py`. 
* These cover all 30 base test cases in `data/cases.csv`. This means when running the catalog cases, the rule engine hits first, giving an instant diagnosis with zero API cost and 100% precision.
* The Gemini LLM is used strictly as a fallback if someone submits a custom incident that the rules don't catch.

### 1.2 Keeping Humans in Control (Safety)
I wanted this console to be entirely read-only. It **never** executes commands directly on a live router. It displays the proposed fix steps, and requires the operator to click **Approve**, **Edit**, or **Reject**. This keeps the human accountable and prevents automated mistakes on live networks.

### 1.3 Key Rotation for the Gemini API
Since free Gemini API keys are heavily rate-limited, I ran into `429 Resource Exhausted` errors constantly during testing. To solve this, I wrote a rotation mechanism that accepts up to 5 keys (`GEMINI_API_KEY_1` through `5`). The engine automatically swaps keys in a round-robin loop when a rate-limit error is encountered.

### 1.4 Custom Streamlit Terminal Theme
Standard Streamlit looks too much like a generic data dashboard. Since this is a network diagnostic tool, I wanted a monospaced terminal look. I wrote a stylesheet injection in `src/ui_theme.py` to overwrite Streamlit's style, giving it a dark terminal container, green highlights on logs, and traffic-light control indicators.

---

## 2. Project Layout & What Each File Does

Here is how the project files are laid out:

* **`data/`**
  * `cases.csv`: The list of 30 standard catalog cases I used to build and test the checker.
  * `system_config.json`: General config (API model name, temperature set to 0.2 to keep output consistent, paths).
  * `audit_log.csv`: Simple append-only CSV that tracks operator decisions (Approve, Edit, Reject).
  * `ai_responsible_log.json`: Stores justification notes when an operator overrides or rejects a diagnosis.
* **`src/`**
  * `app.py`: The Streamlit frontend and entry point.
  * `checker.py`: The local regex rule catalog (26 rules).
  * `engine.py`: Handles the core diagnosis workflow (runs checker, calls Gemini with prompt instructions if no match).
  * `dashboard.py`: Renders the governance metrics and agreement charts.
  * `audit.py`: Helper functions to write to the CSV audit log and the JSON responsibility log.
  * `metrics.py`: Computes agreement rate, override rate, and false-positive statistics.
  * `ui_theme.py`: Custom CSS styling injected into the Streamlit app.
  * `validate_all.py`: A script I wrote to run the checker and engine against all 30 cases to confirm everything works.
* **`tests/`**
  * `test_checker.py` & `test_engine.py`: Pytest files checking rule outputs and JSON schema conformity.

---

## 3. How the Implementation Works

### 3.1 The Diagnostic Pipeline
When you select an incident and click **Run Diagnosis**, the application runs the following flow:
1. Load config settings from `data/system_config.json`.
2. Extract the Cisco `show` outputs for the selected case.
3. Pass the outputs to `run_checker()` in `src/checker.py`.
4. If a rule matches, return the result immediately.
5. If nothing matches, load `prompts/diagnose_prompt.md` and call Gemini with a structured schema constraint.

### 3.2 Solving the Gemini SDK Bug
While writing `src/engine.py`, I hit a bug in the Google GenAI SDK (version `2.18.x`) where `response.parsed` returns `None` even if the API responds with valid JSON. To prevent the program from crashing, I added a manual JSON-parsing fallback block:
```python
response = client.models.generate_content(...)
parsed = response.parsed
if parsed is None:
    # Manual fallback for the SDK bug
    raw_text = response.text
    if not raw_text:
        raise ValueError("LLM returned an empty response")
    data = json.loads(raw_text)
    parsed = DiagnosisSchema(**data)
```

### 3.3 Interactive Terminal Highlight
In `src/app.py`, I wrote a function `terminal_html` to clean and render the raw router outputs. It wraps keywords like `down`, `mismatch`, `notconnect`, and `no permit` in a CSS span class (`.terminal-signal`) to highlight them in orange or red inside the terminal widget.

---

## 4. The 26 Local Rules I Wrote

The rules in `src/checker.py` are mapped to the 30 catalog incidents. Here is the list of rules I coded, what they check for, and the proposed fixes:

1. **`admin_down`**: Matches ` administratively down, line protocol is down`. Remediates with `no shutdown`.
2. **`line_protocol_down`**: Matches ` is up, line protocol is down`. Suggests checking cabling/speed settings.
3. **`vlan_mismatch`**: Compares sub-interface numbers against encapsulation tags (e.g. interface `.30` using `encapsulation dot1Q 20`). Remediates with correct encapsulation.
4. **`wildcard_mask`**: Scans OSPF config for incorrect subnet masks (like `255.255.255.252` instead of `0.0.0.3`). Remediates with correct wildcard.
5. **`default_route`**: Checks for `gateway of last resort is not set` in routing tables. Proposes adding `ip route 0.0.0.0 0.0.0.0`.
6. **`acl_permit`**: Looks for missing permit lines in ACLs (like `no permit tcp` eq 22). Remediates by appending permit rule.
7. **`nat_inside_missing`**: Scans SVI configs for missing `ip nat inside` statements.
8. **`trunk_static_access`**: Matches switch ports set to static access mode when they link to other switches. Remediates with `switchport mode trunk`.
9. **`duplicate_ip`**: Compares IP addresses across all active interfaces. Flags overlapping configs.
10. **`nat_acl_missing_wildcard`**: Identifies ACLs used for NAT overload that miss subnets wildcards.
11. **`stp_blocking_expected`**: Detects ports in blocking (`BLK`) state. Proposes no actions since this is expected loop prevention.
12. **`dhcp_relay_missing`**: Flags SVIs lacking `ip helper-address` configs when clients rely on remote DHCP servers.
13. **`duplex_mismatch`**: Looks for mismatching configurations on ports showing high collisions/half-duplex warnings.
14. **`vlan_not_allowed`**: Matches switch ports where a required VLAN is missing from the trunk allowed list.
15. **`static_route_typo`**: Scans static routes for typos in destination IPs (e.g., `192.168.9.0` instead of `99.0`).
16. **`access_port_left_trunk`**: Identifies user ports left in trunk mode instead of access mode.
17. **`nat_acl_incomplete`**: Looks for newly added subnets that were omitted from the primary NAT overload access list.
18. **`stp_root_misconfig`**: Detects incorrect STP bridge priorities (e.g., a secondary switch winning the root election).
19. **`dhcp_pool_exhausted`**: Flags DHCP servers where total leased addresses equal total pool capacity.
20. **`native_vlan_mismatch`**: Identifies trunk endpoints configured with conflicting native VLAN IDs.
21. **`acl_wrong_direction`**: Scans for inbound-designed access-lists applied in an outbound direction.
22. **`missing_svi_ip`**: Matches routed VLAN interfaces configured with no IP address.
23. **`missing_voice_vlan`**: Finds VoIP phone access ports configured without a voice VLAN command.
24. **`nat_port_exhaustion`**: Detects translation errors when overload uses a single public IP.
25. **`portfast_on_switch_uplink`**: Flags trunk ports connecting switch uplinks that have portfast enabled, risking a loop.
26. **`bgp_as_mismatch`**: Matches BGP neighbor statements configured with mismatching remote AS numbers.

---

## 5. Verification & Testing

To make sure my rules don't break when making changes, I wrote verification checks.

### 5.1 The dry-run validation script
Run this script to diagnose all 30 incidents in the catalogue and print summary statistics:
```powershell
python src/validate_all.py
```
If you want to intentionally append simulated operator choices to the audit trail, append the write flag:
```powershell
python src/validate_all.py --write-audit
```

### 5.2 Running Unit Tests
I set up automated unit tests using `pytest`. Run them with:
```powershell
python -m pytest -q
```
* `test_checker.py` confirms that `run_checker` parses all 30 files and triggers the correct rule.
* `test_engine.py` asserts that the normalized dictionary output structure has the correct keys and fits the required schemas.
