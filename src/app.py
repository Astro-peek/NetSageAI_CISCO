"""NetSage AI operator console.

The console deliberately derives its content from the case catalogue, active
checker registry, diagnosis result, and audit CSV. It is a review surface:
proposed Cisco commands are never executed from this application.
"""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.audit import log_decision
from src import checker
from src.engine import diagnose
from src.metrics import compute_metrics

# Import the checker module rather than individual registry symbols.  Streamlit
# can retain an older module instance during hot reload; this keeps the console
# available while that process catches up with an updated checker.py.
run_checker = checker.run_checker
RULE_CATALOG = getattr(checker, "RULE_CATALOG", [])

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "system_config.json"
st.set_page_config(page_title="NetSage AI | Operator Console", page_icon="NS", layout="wide", initial_sidebar_state="collapsed")

def read_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as file:
        return json.load(file)

CONFIG = read_config()
APP_TITLE = CONFIG.get("app", {}).get("dashboard_title", "NetSage AI")
CASES_PATH = ROOT / CONFIG.get("paths", {}).get("cases_csv", "data/cases.csv")
AUDIT_PATH = ROOT / "data" / "audit_log.csv"
WARNING_THRESHOLD = float(CONFIG.get("app", {}).get("show_confidence_warning_below", 0.5))

@st.cache_data(show_spinner=False)
def load_cases(path: str, modified_at: float) -> pd.DataFrame:
    """Reload automatically whenever the case catalogue changes."""
    del modified_at
    data = pd.read_csv(path).fillna("")
    required = {"case_id", "symptom", "topology_note", "concept_tag", "severity", "show_outputs"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Cases CSV is missing: {', '.join(sorted(missing))}")
    return data

@st.cache_data(show_spinner=False)
def load_audit(path: str, modified_at: float | None) -> pd.DataFrame:
    """Reload automatically whenever an operator records a decision."""
    del modified_at
    if not Path(path).exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path).fillna("")
    except (OSError, pd.errors.EmptyDataError):
        return pd.DataFrame()

def layer_for_tag(tag: str) -> str:
    tag = str(tag).lower()
    if any(word in tag for word in ("vlan", "trunk", "spanning", "native", "admin")):
        return "L2 · Data Link"
    if any(word in tag for word in ("line protocol", "duplex", "cable", "physical")):
        return "L1 · Physical"
    if any(word in tag for word in ("nat", "acl", "mask", "route", "ospf", "ip", "dhcp")):
        return "L3 · Network"
    return "L7 · Application"

def severity_class(value: str) -> str:
    return f"severity-{str(value).lower()}"

def badge(text: str, style: str = "neutral") -> str:
    return f'<span class="badge {style}">{html.escape(str(text))}</span>'

def format_time(value: object, fallback: str = "—") -> str:
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(str(value)).strftime("%d %b · %H:%M")
    except ValueError:
        return str(value)[:16]

def terminal_html(output: str, evidence: str = "") -> str:
    escaped = html.escape(str(output).replace(" | ", "\n"))
    evidence, lines = evidence.lower().strip(), []
    signals = ("down", "mismatch", "notconnect", "not set", "(empty)", "missing", "no permit", "timed out", "denied")
    for line in escaped.splitlines():
        if any(token in line.lower() for token in signals) or (evidence and evidence in line.lower()):
            lines.append(f'<span class="terminal-signal">{line}</span>')
        else:
            lines.append(line)
    return "\n".join(lines)

def audit_summary(audit: pd.DataFrame) -> pd.DataFrame:
    if audit.empty or "case_id" not in audit:
        return pd.DataFrame(columns=["case_id", "last_decision", "last_action_at"])
    ordered = audit.copy()
    ordered["_sort_time"] = pd.to_datetime(ordered.get("timestamp"), errors="coerce")
    latest = ordered.sort_values("_sort_time").groupby("case_id", as_index=False).tail(1)
    return latest.rename(columns={"decision": "last_decision", "timestamp": "last_action_at"})[["case_id", "last_decision", "last_action_at"]]

def select_case(case_id: str) -> None:
    st.session_state.selected_case = case_id
    st.session_state.diagnosis = None
    st.session_state.decision_logged = False
    st.session_state.editing = False
    st.session_state.commands = ""
    st.query_params["case"] = case_id

if not CASES_PATH.exists():
    st.error(f"Case catalogue not found: {CASES_PATH}")
    st.stop()
try:
    cases = load_cases(str(CASES_PATH), CASES_PATH.stat().st_mtime)
except (ValueError, OSError, pd.errors.ParserError) as error:
    st.error(f"Could not load the case catalogue: {error}")
    st.stop()

audit_mtime = AUDIT_PATH.stat().st_mtime if AUDIT_PATH.exists() else None
audit = load_audit(str(AUDIT_PATH), audit_mtime)
case_ids = cases["case_id"].astype(str).tolist()
requested_case = st.query_params.get("case")
initial_case = requested_case if requested_case in case_ids else case_ids[0]
for key, default in {"selected_case": initial_case, "diagnosis": None, "decision_logged": False, "editing": False, "commands": ""}.items():
    if key not in st.session_state:
        st.session_state[key] = default
if st.session_state.selected_case not in case_ids:
    select_case(case_ids[0])

st.markdown("""
<style>
:root{--ink:#e7edf9;--muted:#8d9ab7;--panel:#121b2f;--line:#263554;--cyan:#44e5cc;--red:#ff7185;--orange:#ffb86a}.stApp{background:#080d1b;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.stApp:before{content:"";position:fixed;inset:0;pointer-events:none;background:radial-gradient(circle at 8% 2%,rgba(64,101,196,.26),transparent 29%),radial-gradient(circle at 93% 15%,rgba(48,202,181,.13),transparent 24%)}[data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer{display:none}.block-container{max-width:1500px;padding:1.45rem 2.4rem 3rem!important}@media(max-width:760px){.block-container{padding:1rem!important}}
.brandbar{display:flex;justify-content:space-between;align-items:center;gap:1rem;margin:0 0 1.55rem;padding:.8rem 1rem .8rem 1.15rem;background:rgba(18,27,47,.88);border:1px solid var(--line);border-radius:16px;box-shadow:0 18px 55px rgba(0,0,0,.22)}.brand{display:flex;align-items:center;gap:.72rem;font-weight:800;font-size:1.06rem;letter-spacing:-.025em;color:#f4f7ff}.brand-mark{width:29px;height:29px;border-radius:9px;display:grid;place-items:center;background:linear-gradient(135deg,#5790ff,#44dfcd);color:#081122;font-size:.76rem;letter-spacing:-.08em}.brandbar small{color:var(--muted);font-size:.74rem}.live-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--cyan);box-shadow:0 0 0 4px rgba(68,229,204,.1);margin-right:.4rem}
div[data-testid="stTabBar"]{gap:.4rem;border-bottom:1px solid var(--line);margin-bottom:1.25rem}button[data-baseweb="tab"]{height:42px!important;color:var(--muted)!important;font-size:.78rem!important;font-weight:700!important;letter-spacing:.045em!important;padding:0 1rem!important;background:transparent!important}button[data-baseweb="tab"][aria-selected="true"]{color:#f4f7ff!important;border-bottom:2px solid var(--cyan)!important}.hero{border:1px solid #30456c;background:linear-gradient(115deg,rgba(28,48,93,.88),rgba(18,27,47,.92) 58%,rgba(19,69,77,.52));border-radius:20px;padding:1.65rem 1.75rem;margin:.25rem 0 1.1rem;position:relative;overflow:hidden}.hero:after{content:"";position:absolute;width:210px;height:210px;right:-55px;top:-110px;border:1px solid rgba(104,163,255,.3);border-radius:50%;box-shadow:0 0 0 34px rgba(104,163,255,.04),0 0 0 70px rgba(104,163,255,.025)}.eyebrow{color:var(--cyan);font-size:.68rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.hero h1{margin:.35rem 0;font-size:clamp(1.65rem,3vw,2.35rem);letter-spacing:-.045em;position:relative;z-index:1}.hero p{margin:0;color:#b6c4df;font-size:.92rem;max-width:650px;position:relative;z-index:1}.status{display:inline-flex;align-items:center;gap:.4rem;margin-top:1rem;padding:.36rem .62rem;border-radius:999px;border:1px solid #365275;background:rgba(8,20,42,.44);font-size:.7rem;font-weight:700;letter-spacing:.06em}.status-dot{width:7px;height:7px;border-radius:50%;background:var(--cyan)}
.metric{min-height:108px;background:rgba(18,27,47,.88);border:1px solid var(--line);border-radius:14px;padding:1rem}.metric .value{font-size:1.7rem;font-weight:800;letter-spacing:-.045em;color:#f4f7ff;margin-top:.1rem}.metric .label{color:var(--muted);font-size:.73rem;font-weight:600;margin-top:.15rem}.metric .hint{color:#71809f;font-size:.68rem;margin-top:.45rem}.panel{background:rgba(18,27,47,.9);border:1px solid var(--line);border-radius:16px;padding:1.15rem;margin-bottom:1rem;box-shadow:0 12px 34px rgba(0,0,0,.11)}.panel-title{font-size:.91rem;font-weight:750;color:#f0f4ff}.panel-subtitle{color:var(--muted);font-size:.73rem;margin-top:.16rem}.case-meta{display:flex;gap:.45rem;flex-wrap:wrap;margin:.85rem 0}.badge{display:inline-flex;align-items:center;line-height:1;padding:.35rem .48rem;border-radius:7px;font-size:.65rem;font-weight:750;letter-spacing:.025em;border:1px solid #31425f;background:#202c45;color:#c7d5ef}.severity-critical{color:#ffbac5;background:rgba(209,64,90,.14);border-color:rgba(255,113,133,.3)}.severity-high{color:#ffc997;background:rgba(220,127,32,.12);border-color:rgba(255,184,106,.25)}.severity-medium{color:#ded1ff;background:rgba(137,106,230,.14);border-color:rgba(169,140,255,.26)}.severity-low{color:#a9ddff;background:rgba(59,129,204,.14);border-color:rgba(104,163,255,.26)}.success{color:#92f1d7;background:rgba(39,179,149,.13);border-color:rgba(68,229,204,.25)}.warning{color:#ffd29a;background:rgba(234,155,47,.12);border-color:rgba(255,184,106,.25)}.danger{color:#ffc2cc;background:rgba(238,80,109,.14);border-color:rgba(255,113,133,.25)}
.terminal{background:#070c17;border:1px solid #263554;border-radius:12px;overflow:hidden}.terminal-head{display:flex;align-items:center;justify-content:space-between;padding:.6rem .8rem;background:#0e1627;border-bottom:1px solid #263554;color:#95a6c4;font-size:.68rem;font-weight:700;letter-spacing:.06em}.terminal-lights{display:flex;gap:5px}.terminal-lights i{width:8px;height:8px;border-radius:50%;background:#52617b}.terminal-lights i:first-child{background:#ff7185}.terminal-lights i:nth-child(2){background:#ffb86a}.terminal-lights i:nth-child(3){background:#44e5cc}.terminal pre{margin:0;padding:1rem;min-height:300px;color:#c9d5ea;font:13px/1.7 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;word-break:break-word}.terminal-signal{display:block;background:rgba(255,113,133,.1);color:#ffb3c0;margin:0 -.25rem;padding:0 .25rem;border-left:2px solid #ff7185}
.diagnosis-empty{min-height:300px;display:grid;place-content:center;text-align:center;color:var(--muted);padding:1.5rem}.diagnosis-empty .orbit{margin:auto auto .75rem;width:45px;height:45px;border:2px solid #304767;border-top-color:var(--cyan);border-radius:50%}.result-title{font-size:1.08rem;color:#f4f7ff;font-weight:750;line-height:1.38;margin:.75rem 0}.confidence{display:flex;align-items:baseline;gap:.5rem;margin-top:.9rem}.confidence strong{font-size:2.1rem;letter-spacing:-.06em;color:var(--cyan)}.confidence span{color:var(--muted);font-size:.72rem}.confidence-bar{height:6px;background:#263554;border-radius:9px;overflow:hidden;margin:.7rem 0 1rem}.confidence-bar span{display:block;height:100%;background:linear-gradient(90deg,#5a8fff,#44e5cc);border-radius:inherit}.evidence{border-left:2px solid #597cbd;padding:.6rem .75rem;background:#101a2d;color:#b9c7df;font-size:.77rem;line-height:1.5;border-radius:0 8px 8px 0}.command-box{margin:.75rem 0;background:#0a1221;border:1px solid #2a3c5c;border-radius:10px;padding:.75rem;color:#bfcef2;font:12px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap}
.stButton>button{border-radius:9px!important;font-weight:700!important;font-size:.78rem!important;min-height:38px!important;border-color:#3c5075!important;background:#202d47!important;color:#e7edf9!important}.stButton>button[kind="primary"]{background:linear-gradient(135deg,#4f80e9,#2ebea9)!important;border-color:transparent!important;color:#061222!important}.stTextArea textarea,.stSelectbox [data-baseweb="select"]>div,.stTextInput input,.stMultiSelect [data-baseweb="select"]>div{background:#0c1424!important;border-color:#2e4161!important;color:#e7edf9!important;border-radius:9px!important}.stSelectbox label,.stTextInput label,.stMultiSelect label,.stTextArea label{color:#b1c0da!important;font-size:.74rem!important;font-weight:700!important}.stDataFrame{border:1px solid var(--line);border-radius:10px;overflow:hidden}.stAlert{border-radius:10px!important}.empty-note{color:var(--muted);font-size:.8rem;padding:1rem 0;text-align:center}.footnote{font-size:.71rem;color:#71809f;margin-top:.15rem}.rule-count{font-size:2.25rem;font-weight:800;color:var(--cyan);letter-spacing:-.07em}
</style>
""", unsafe_allow_html=True)

summary = audit_summary(audit)
metrics = compute_metrics()
total_cases = len(cases)
reviewed = int(cases["case_id"].astype(str).isin(summary["case_id"].astype(str)).sum()) if not summary.empty else 0
critical = int(cases["severity"].str.lower().eq("critical").sum())
st.markdown(f'''<div class="brandbar"><div class="brand"><span class="brand-mark">NS</span>{html.escape(APP_TITLE)}</div><small><span class="live-dot"></span>Connected to {total_cases} live cases · {len(RULE_CATALOG)} active rules</small></div>''', unsafe_allow_html=True)
tab_console, tab_cases, tab_rules, tab_audit = st.tabs(["OPERATOR CONSOLE", "CASE EXPLORER", "RULE COVERAGE", "AUDIT INSIGHTS"])

with tab_console:
    diagnosis = st.session_state.diagnosis
    if diagnosis is None: status, description = "READY FOR REVIEW", "Select a case and request a diagnosis."
    elif diagnosis.get("source") == "error": status, description = "ENGINE ATTENTION", "The diagnosis engine returned an error."
    elif st.session_state.decision_logged: status, description = "DECISION RECORDED", "The latest operator decision is in the audit trail."
    else: status, description = "ANALYSIS READY", "Review the evidence before recording an operator decision."
    st.markdown(f'''<section class="hero"><div class="eyebrow">Human-in-the-loop network operations</div><h1>Diagnose with evidence. Decide with confidence.</h1><p>{description}</p><div class="status"><span class="status-dot"></span>{status}</div></section>''', unsafe_allow_html=True)
    cards = [(total_cases,"Cases in catalogue","Read directly from cases.csv"),(reviewed,"Cases reviewed","Latest audit decision per case"),(f"{metrics.get('agreement_rate', 0):.0f}%","Operator agreement","Approved diagnoses / decisions"),(critical,"Critical cases","Current severity distribution")]
    for column, (value,label,hint) in zip(st.columns(4), cards):
        column.markdown(f'<div class="metric"><div class="value">{value}</div><div class="label">{label}</div><div class="hint">{hint}</div></div>', unsafe_allow_html=True)
    st.markdown("<div style='height:.9rem'></div>", unsafe_allow_html=True)
    select_col, refresh_col = st.columns([2.5, 1])
    with select_col:
        chosen = st.selectbox("Active incident", case_ids, index=case_ids.index(st.session_state.selected_case), format_func=lambda item: f"{item}  ·  {cases.loc[cases['case_id'].astype(str) == item, 'symptom'].iloc[0]}")
    with refresh_col:
        st.markdown("<div style='height:1.58rem'></div>", unsafe_allow_html=True)
        if st.button("Refresh data", width="stretch"):
            load_cases.clear(); load_audit.clear(); st.rerun()
    if chosen != st.session_state.selected_case:
        select_case(chosen); st.rerun()
    case = cases.loc[cases["case_id"].astype(str) == st.session_state.selected_case].iloc[0]
    left, right = st.columns([1.38, 1])
    with left:
        st.markdown(f'''<div class="panel"><div class="panel-title">{html.escape(str(case['symptom']))}</div><div class="panel-subtitle">{html.escape(str(case['topology_note']))}</div><div class="case-meta">{badge(case['case_id'])}{badge(layer_for_tag(case['concept_tag']))}{badge(case['severity'],severity_class(case['severity']))}{badge(case['concept_tag'])}</div><div class="terminal"><div class="terminal-head"><span>RAW CISCO IOS OUTPUT · {html.escape(str(case['case_id']))}</span><span class="terminal-lights"><i></i><i></i><i></i></span></div><pre>{terminal_html(case['show_outputs'], diagnosis.get('evidence','') if diagnosis else '')}</pre></div></div>''', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        if diagnosis is None:
            st.markdown('<div class="diagnosis-empty"><div><div class="orbit"></div><div class="panel-title">Analysis is waiting</div><p class="panel-subtitle">The rule engine runs first. Gemini is used only if no live rule matches.</p></div></div>', unsafe_allow_html=True)
            if st.button("Run diagnosis", type="primary", width="stretch"):
                with st.spinner("Checking live case evidence…"):
                    st.session_state.diagnosis = diagnose(str(case["case_id"]))
                    st.session_state.commands = "\n".join(st.session_state.diagnosis.get("fix_steps", []))
                    st.session_state.decision_logged = False; st.session_state.editing = False
                st.rerun()
        else:
            source = diagnosis.get("source", "error"); confidence = float(diagnosis.get("confidence", 0))
            source_text = "RULE ENGINE" if source == "checker" else "GEMINI" if source == "llm" else "ENGINE ERROR"
            source_style = "success" if source == "checker" else "warning" if source == "llm" else "danger"
            st.markdown(f'''<div class="panel-title">Proposed root cause</div><div class="case-meta">{badge(source_text,source_style)}{badge(diagnosis.get('osi_layer','Unknown'),'warning' if confidence < WARNING_THRESHOLD else 'neutral')}</div><div class="result-title">{html.escape(str(diagnosis.get('root_cause','No conclusion returned.')))}</div><div class="confidence"><strong>{confidence:.0%}</strong><span>confidence score</span></div><div class="confidence-bar"><span style="width:{max(0,min(confidence,1))*100:.0f}%"></span></div><div class="evidence"><b>Evidence</b><br>{html.escape(str(diagnosis.get('evidence','No evidence returned.')))}</div>''', unsafe_allow_html=True)
            if source == "error":
                st.error("No proposal was generated. Check the configured Gemini credentials or select another case.")
            elif st.session_state.editing:
                st.session_state.commands = st.text_area("Review or edit proposed Cisco IOS commands", value=st.session_state.commands, height=145)
                edit_one, edit_two = st.columns(2)
                if edit_one.button("Save edited decision", type="primary", width="stretch"):
                    log_decision(str(case["case_id"]),source,diagnosis.get("root_cause",""),diagnosis.get("osi_layer",""),confidence,"Edit Commands",edited=True)
                    load_audit.clear(); st.session_state.decision_logged=True; st.session_state.editing=False; st.toast("Edited decision recorded in the audit log."); st.rerun()
                if edit_two.button("Cancel", width="stretch"):
                    st.session_state.editing=False; st.rerun()
            else:
                commands = "\n".join(f"• {step}" for step in diagnosis.get("fix_steps", [])) or "No command steps were returned."
                next_command = diagnosis.get("next_command", "")
                st.markdown(f'<div class="panel-subtitle" style="margin-top:1rem">RECOMMENDED REMEDIATION</div><div class="command-box">{html.escape(commands)}</div>' + (f'<div class="footnote">Next inspection: <code>{html.escape(str(next_command))}</code></div>' if next_command else ""), unsafe_allow_html=True)
                approve, edit, reject = st.columns(3)
                if approve.button("Approve", type="primary", width="stretch"):
                    log_decision(str(case["case_id"]),source,diagnosis.get("root_cause",""),diagnosis.get("osi_layer",""),confidence,"Approve & Deploy",edited=False)
                    load_audit.clear(); st.session_state.decision_logged=True; st.toast("Approval recorded. No command was executed."); st.rerun()
                if edit.button("Edit", width="stretch"):
                    st.session_state.editing=True; st.rerun()
                if reject.button("Reject", width="stretch"):
                    log_decision(str(case["case_id"]),source,diagnosis.get("root_cause",""),diagnosis.get("osi_layer",""),confidence,"Reject",edited=False)
                    load_audit.clear(); st.session_state.decision_logged=True; st.toast("Rejection recorded in the audit log."); st.rerun()
            if st.session_state.decision_logged:
                st.success("Operator decision recorded. The console remains display-only.")
        st.markdown("</div>", unsafe_allow_html=True)

with tab_cases:
    st.markdown('<div class="panel"><div class="panel-title">Case explorer</div><div class="panel-subtitle">Filter the live case catalogue and open any incident in the operator console.</div></div>', unsafe_allow_html=True)
    filter_one, filter_two, filter_three = st.columns([1,1,1.5])
    severities = sorted(cases["severity"].astype(str).str.title().unique().tolist())
    layers = sorted(cases["concept_tag"].map(layer_for_tag).unique().tolist())
    with filter_one: active_severities = st.multiselect("Severity",severities,default=severities)
    with filter_two: active_layers = st.multiselect("OSI layer",layers,default=layers)
    with filter_three: search = st.text_input("Search symptoms, tags, or case IDs",placeholder="e.g. VLAN, NET-004, gateway")
    explorer = cases.copy(); explorer["osi_layer"] = explorer["concept_tag"].map(layer_for_tag)
    explorer = explorer[explorer["severity"].str.title().isin(active_severities) & explorer["osi_layer"].isin(active_layers)]
    if search.strip():
        searchable = explorer[["case_id","symptom","concept_tag","topology_note"]].astype(str).agg(" ".join,axis=1)
        explorer = explorer[searchable.str.contains(search.strip(),case=False,na=False)]
    explorer = explorer.merge(summary,on="case_id",how="left")
    display = explorer[["case_id","symptom","concept_tag","osi_layer","severity","last_decision","last_action_at"]].copy()
    display["last_action_at"] = display["last_action_at"].map(format_time); display["last_decision"] = display["last_decision"].replace("", "Unreviewed").fillna("Unreviewed")
    st.dataframe(display,width="stretch",hide_index=True,column_config={"case_id":"Case","symptom":"Reported symptom","concept_tag":"Fault tag","osi_layer":"OSI layer","severity":"Severity","last_decision":"Latest decision","last_action_at":"Last action"})
    if explorer.empty: st.info("No cases match the selected filters.")
    else:
        open_case = st.selectbox("Open a filtered case", explorer["case_id"].astype(str).tolist(),key="explorer_case")
        if st.button("Open in operator console",type="primary"):
            select_case(open_case); st.toast(f"{open_case} is ready in the Operator Console tab.")

with tab_rules:
    deterministic_results = cases["show_outputs"].map(run_checker)
    deterministic_count = int(deterministic_results.notna().sum())
    st.markdown(f'''<div class="panel"><div class="eyebrow">Executable coverage only</div><div class="rule-count">{len(RULE_CATALOG)} active rules</div><div class="panel-subtitle">{deterministic_count} of {total_cases} catalogue cases match the deterministic engine; {total_cases-deterministic_count} use the configured LLM fallback.</div></div>''',unsafe_allow_html=True)
    rule_table = pd.DataFrame(RULE_CATALOG).rename(columns={"id":"Rule ID","title":"Fault signature","osi_layer":"OSI layer","signature":"Detection evidence","remediation":"Operator remediation"})
    st.dataframe(rule_table,width="stretch",hide_index=True)
    coverage = cases[["case_id","concept_tag","severity","symptom"]].copy(); coverage["diagnostic_path"] = deterministic_results.map(lambda result: "Rule engine" if isinstance(result,dict) else "LLM fallback"); coverage["rule_result"] = deterministic_results.map(lambda result: result.get("root_cause","") if isinstance(result,dict) else "")
    st.markdown("<div class='panel-title' style='margin:1.15rem 0 .55rem'>Live case coverage</div>",unsafe_allow_html=True); st.dataframe(coverage,width="stretch",hide_index=True)

with tab_audit:
    st.markdown('<div class="panel"><div class="panel-title">Audit insights</div><div class="panel-subtitle">Metrics are calculated from recorded operator decisions, not placeholders.</div></div>',unsafe_allow_html=True)
    audit_cards=[(metrics.get("total_cases",0),"Decisions logged"),(f"{metrics.get('agreement_rate',0):.1f}%","Agreement rate"),(f"{metrics.get('override_rate',0):.1f}%","Edited proposals"),(f"{metrics.get('false_positive_rate',0):.1f}%","Rejected proposals")]
    for column,(value,label) in zip(st.columns(4),audit_cards): column.markdown(f'<div class="metric"><div class="value">{value}</div><div class="label">{label}</div></div>',unsafe_allow_html=True)
    st.markdown("<div style='height:1rem'></div>",unsafe_allow_html=True)
    if audit.empty:
        st.markdown('<div class="panel"><div class="empty-note">No audit decisions yet. Approve, edit, or reject a live diagnosis to begin the audit trail.</div></div>',unsafe_allow_html=True)
    else:
        audit_display=audit.copy(); audit_display["timestamp"]=audit_display["timestamp"].map(format_time); st.dataframe(audit_display.sort_values("timestamp",ascending=False),width="stretch",hide_index=True)
        by_source=pd.DataFrame([{"Source":name,"Decisions":value["total"],"Agreement":f"{value['agreement_rate']:.1f}%"} for name,value in metrics.get("by_source",{}).items()]); by_layer=pd.DataFrame([{"OSI layer":name,"Decisions":value["total"],"Agreement":f"{value['agreement_rate']:.1f}%"} for name,value in metrics.get("by_osi",{}).items()])
        source_col, layer_col = st.columns(2)
        with source_col:
            st.markdown("<div class='panel-title' style='margin:.9rem 0 .5rem'>By diagnostic source</div>",unsafe_allow_html=True)
            st.dataframe(by_source,width="stretch",hide_index=True) if not by_source.empty else st.caption("No source data yet.")
        with layer_col:
            st.markdown("<div class='panel-title' style='margin:.9rem 0 .5rem'>By OSI layer</div>",unsafe_allow_html=True)
            st.dataframe(by_layer,width="stretch",hide_index=True) if not by_layer.empty else st.caption("No OSI layer data yet.")

st.markdown('<div class="footnote" style="padding-top:1rem;text-align:center">NetSage AI · Human approval required · Cisco commands are display-only</div>',unsafe_allow_html=True)
