from __future__ import annotations

import html
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.audit import log_decision, append_responsible_log
from src import checker
from src.engine import diagnose, diagnose_custom
from src.metrics import compute_metrics
from src.dashboard import render_dashboard
from src.ui_theme import inject_theme

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
    del modified_at
    data = pd.read_csv(path).fillna("")
    required = {"case_id", "symptom", "topology_note", "concept_tag", "severity", "show_outputs"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Cases CSV is missing: {', '.join(sorted(missing))}")
    return data


@st.cache_data(show_spinner=False)
def load_audit(path: str, modified_at: float | None) -> pd.DataFrame:
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


def commands_html(steps: list, next_command: str = "") -> str:
    if not steps:
        rows = '<div class="cli-row"><span class="cli-n">–</span><span>No command steps were returned.</span></div>'
    else:
        rows = "".join(
            f'<div class="cli-row"><span class="cli-n">{index:02d}</span><span>{html.escape(str(step))}</span></div>'
            for index, step in enumerate(steps, 1)
        )
    next_line = (
        f'<div class="footnote">Next inspection: <code>{html.escape(str(next_command))}</code></div>'
        if next_command
        else ""
    )
    return f'<div class="cli-box">{rows}</div>{next_line}'


def decision_style(decision: str) -> str:
    value = str(decision).lower()
    if "approve" in value:
        return "success"
    if "edit" in value:
        return "warning"
    if "reject" in value:
        return "danger"
    return "neutral"


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
for key, default in {"selected_case": initial_case, "diagnosis": None, "decision_logged": False, "editing": False, "commands": "", "rejecting": False, "custom_diagnosis": None, "custom_running": False, "custom_decision_logged": False, "custom_editing": False, "custom_rejecting": False, "custom_commands": ""}.items():
    if key not in st.session_state:
        st.session_state[key] = default
if st.session_state.selected_case not in case_ids:
    select_case(case_ids[0])

inject_theme(st)
summary = audit_summary(audit)
metrics = compute_metrics()
total_cases = len(cases)
reviewed_ids = set(summary["case_id"].astype(str)) if not summary.empty else set()
reviewed = int(cases["case_id"].astype(str).isin(reviewed_ids).sum())
critical = int(cases["severity"].str.lower().eq("critical").sum())
high = int(cases["severity"].str.lower().eq("high").sum())

st.markdown(
    f'''<div class="topbar">
      <div class="brand">
        <div class="brand-mark">NS</div>
        <div>
          <h1>{html.escape(APP_TITLE.split("—")[0].strip() if "—" in APP_TITLE else APP_TITLE)}</h1>
          <p>Human-in-the-loop Cisco diagnostics · display-only commands</p>
        </div>
      </div>
      <div class="top-meta">
        <span class="chip live"><span class="live-dot"></span>ENGINE READY</span>
        <span class="chip">{total_cases} LIVE CASES</span>
        <span class="chip">{len(RULE_CATALOG)} RULES</span>
        <span class="chip">{reviewed} REVIEWED</span>
      </div>
    </div>''',
    unsafe_allow_html=True,
)

tab_console, tab_dashboard, tab_audit, tab_new = st.tabs(["CONSOLE", "GOVERNANCE", "AUDIT", "➕ NEW INCIDENT"])

with tab_dashboard:
    render_dashboard(standalone=False)

with tab_console:
    diagnosis = st.session_state.diagnosis
    if diagnosis is None:
        step_select, step_diag, step_decide = "on", "", ""
        status = "Awaiting diagnosis"
    elif diagnosis.get("source") == "error":
        step_select, step_diag, step_decide = "done", "on", ""
        status = "Engine attention required"
    elif st.session_state.decision_logged:
        step_select, step_diag, step_decide = "done", "done", "done"
        status = "Decision recorded"
    else:
        step_select, step_diag, step_decide = "done", "done", "on"
        status = "Review evidence, then decide"

    st.markdown(
        f'''<div class="page-head" style="margin-bottom:.7rem">
          <div>
            <div class="kicker">Operator console</div>
            <h2>Incident workspace</h2>
            <p>{html.escape(status)}. Rule engine first · Gemini only on unknown patterns · commands stay display-only.</p>
          </div>
          <div class="steps">
            <span class="step {step_select}"><b>1</b> Select</span>
            <span class="step {step_diag}"><b>2</b> Diagnose</span>
            <span class="step {step_decide}"><b>3</b> Decide</span>
          </div>
        </div>''',
        unsafe_allow_html=True,
    )

    queue_col, evidence_col, decision_col = st.columns([1.05, 1.45, 1.2], gap="small")

    with queue_col:
        search = st.text_input("Search incidents", placeholder="NET-014, VLAN, NAT, trunk…")
        filter_a, filter_b = st.columns(2)
        with filter_a:
            severity_filter = st.selectbox("Severity", ["All", "Critical", "High", "Medium", "Low"])
        with filter_b:
            status_filter = st.selectbox("Review status", ["All", "Unreviewed", "Reviewed"])

        queue = cases.copy()
        queue["_id"] = queue["case_id"].astype(str)
        if search.strip():
            needle = search.strip().lower()
            mask = (
                queue["_id"].str.lower().str.contains(needle, na=False)
                | queue["symptom"].astype(str).str.lower().str.contains(needle, na=False)
                | queue["concept_tag"].astype(str).str.lower().str.contains(needle, na=False)
            )
            queue = queue[mask]
        if severity_filter != "All":
            queue = queue[queue["severity"].astype(str).str.lower() == severity_filter.lower()]
        if status_filter == "Reviewed":
            queue = queue[queue["_id"].isin(reviewed_ids)]
        elif status_filter == "Unreviewed":
            queue = queue[~queue["_id"].isin(reviewed_ids)]

        filtered_ids = queue["_id"].tolist()
        if st.session_state.selected_case not in filtered_ids:
            filtered_ids = [st.session_state.selected_case] + filtered_ids

        st.markdown(
            f'''<div class="block-head">
              <div>
                <div class="col-kicker" style="margin:0">Incident queue</div>
                <h3>Open cases</h3>
              </div>
              <span class="count-pill">{len(queue)} shown</span>
            </div>''',
            unsafe_allow_html=True,
        )

        def queue_label(case_id: str) -> str:
            row = cases.loc[cases["case_id"].astype(str) == case_id].iloc[0]
            state = "reviewed" if case_id in reviewed_ids else "open"
            symptom = str(row["symptom"])
            if len(symptom) > 54:
                symptom = symptom[:51] + "…"
            return f"{case_id}  ·  {str(row['severity']).upper()}  ·  {state}\n{symptom}"

        picked = st.radio(
            "Select an incident",
            filtered_ids,
            index=filtered_ids.index(st.session_state.selected_case),
            format_func=queue_label,
            label_visibility="collapsed",
        )
        if picked != st.session_state.selected_case:
            select_case(picked)
            st.rerun()

        if st.button("Refresh data", width="stretch"):
            load_cases.clear()
            load_audit.clear()
            st.rerun()

    case = cases.loc[cases["case_id"].astype(str) == st.session_state.selected_case].iloc[0]
    last_decision = ""
    if not summary.empty:
        hit = summary[summary["case_id"].astype(str) == str(case["case_id"])]
        if not hit.empty:
            last_decision = str(hit.iloc[0]["last_decision"])

    with evidence_col:
        last_badge = badge(last_decision, decision_style(last_decision)) if last_decision else badge("UNREVIEWED", "warning")
        st.markdown(
            f'''<div class="col-kicker">Active incident</div>
              <div class="incident-title">{html.escape(str(case["symptom"]))}</div>
              <div class="panel-sub">{html.escape(str(case["topology_note"]))}</div>
              <div class="meta">
                {badge(case["case_id"])}{badge(layer_for_tag(case["concept_tag"]))}{badge(case["severity"], severity_class(case["severity"]))}{badge(case["concept_tag"])}{last_badge}
              </div>''',
            unsafe_allow_html=True,
        )
        if diagnosis and not st.session_state.decision_logged and diagnosis.get("source") != "error" and not st.session_state.editing and not st.session_state.get("rejecting"):
            if st.button("Approve & Deploy", type="primary", width="stretch", key="approve_center"):
                source = diagnosis.get("source", "error")
                confidence = float(diagnosis.get("confidence", 0))
                log_decision(str(case["case_id"]), source, diagnosis.get("root_cause", ""), diagnosis.get("osi_layer", ""), confidence, "Approve & Deploy", edited=False)
                load_audit.clear()
                st.session_state.decision_logged = True
                st.toast("Approval recorded. No command was executed.")
                st.rerun()
        st.markdown(
            f'''<div class="terminal">
                <div class="terminal-head"><span>CISCO IOS · SHOW OUTPUT · {html.escape(str(case["case_id"]))}</span><span class="lights"><i></i><i></i><i></i></span></div>
                <pre>{terminal_html(case["show_outputs"], diagnosis.get("evidence", "") if diagnosis else "")}</pre>
              </div>''',
            unsafe_allow_html=True,
        )

    with decision_col:
        st.markdown(
            '<div class="col-kicker">Review</div><div class="review-title">Diagnosis &amp; decision</div>',
            unsafe_allow_html=True,
        )
        if diagnosis is None:
            st.markdown(
                '''<div class="empty">
                  <div>
                    <div class="orbit"></div>
                    <div class="panel-title">Ready when you are</div>
                    <p class="panel-sub">Run the checker against live case evidence. Gemini is a fallback, not the first pass.</p>
                    <ul class="empty-steps">
                      <li>1. Deterministic rules inspect show output</li>
                      <li>2. Unknown patterns escalate to Gemini</li>
                      <li>3. You approve, edit, or reject</li>
                    </ul>
                  </div>
                </div>''',
                unsafe_allow_html=True,
            )
            if st.button("Run diagnosis", type="primary", width="stretch"):
                with st.spinner("Checking live case evidence…"):
                    st.session_state.diagnosis = diagnose(str(case["case_id"]))
                    st.session_state.commands = "\n".join(st.session_state.diagnosis.get("fix_steps", []))
                    st.session_state.decision_logged = False
                    st.session_state.editing = False
                    st.session_state.rejecting = False
                st.rerun()
        else:
            source = diagnosis.get("source", "error")
            confidence = float(diagnosis.get("confidence", 0))
            source_text = "RULE ENGINE" if source == "checker" else "GEMINI" if source == "llm" else "ENGINE ERROR"
            source_style = "success" if source == "checker" else "warning" if source == "llm" else "danger"
            conf_note = "Low confidence — inspect evidence before acting." if confidence < WARNING_THRESHOLD else "Confidence is above the review warning threshold."
            percent = max(0, min(confidence, 1)) * 100
            st.markdown(
                f'''<div class="panel-title">Proposed root cause</div>
                <div class="meta">{badge(source_text, source_style)}{badge(diagnosis.get("osi_layer", "Unknown"), "warning" if confidence < WARNING_THRESHOLD else "neutral")}</div>
                <div class="result-title">{html.escape(str(diagnosis.get("root_cause", "No conclusion returned.")))}</div>
                <div class="conf-row">
                  <div class="ring" style="--p:{percent:.0f}%"><div><strong>{confidence:.0%}</strong><span>CONF</span></div></div>
                  <div class="conf-copy"><b>Model confidence</b><br>{html.escape(conf_note)}</div>
                </div>
                <div class="evidence"><b>Evidence</b><br>{html.escape(str(diagnosis.get("evidence", "No evidence returned.")))}</div>''',
                unsafe_allow_html=True,
            )
            if source == "error":
                st.error("No proposal was generated. Check Gemini credentials or select another case.")
            elif st.session_state.editing:
                st.session_state.commands = st.text_area("Review or edit proposed Cisco IOS commands", value=st.session_state.commands, height=145)
                edit_justification = st.text_input("Responsible AI notes / correction justification", key="edit_justification", placeholder="Why did you change this command?")
                edit_one, edit_two = st.columns(2)
                if edit_one.button("Save edited decision", type="primary", width="stretch"):
                    log_decision(str(case["case_id"]), source, diagnosis.get("root_cause", ""), diagnosis.get("osi_layer", ""), confidence, "Edit Commands", edited=True)
                    just_str = edit_justification.strip() if edit_justification.strip() else "Operator modified recommended commands to fix parameters before deployment."
                    append_responsible_log(
                        str(case["case_id"]),
                        str(case["symptom"]),
                        diagnosis.get("root_cause", ""),
                        f"Operator edited commands to:\n{st.session_state.commands}",
                        str(case["severity"]),
                        just_str,
                    )
                    load_audit.clear()
                    st.session_state.decision_logged = True
                    st.session_state.editing = False
                    st.toast("Edited decision and operator notes recorded.")
                    st.rerun()
                if edit_two.button("Cancel", width="stretch"):
                    st.session_state.editing = False
                    st.rerun()
            else:
                st.markdown('<div class="remediation-label">Recommended remediation</div>', unsafe_allow_html=True)
                st.markdown(commands_html(diagnosis.get("fix_steps", []), diagnosis.get("next_command", "")), unsafe_allow_html=True)

                if st.session_state.get("rejecting", False):
                    reject_justification = st.text_input("Responsible AI notes / rejection justification", key="reject_justification", placeholder="Why is this diagnosis incorrect or unsafe?")
                    rej_btn_1, rej_btn_2 = st.columns(2)
                    if rej_btn_1.button("Confirm rejection", type="primary", width="stretch"):
                        log_decision(str(case["case_id"]), source, diagnosis.get("root_cause", ""), diagnosis.get("osi_layer", ""), confidence, "Reject", edited=False)
                        just_str = reject_justification.strip() if reject_justification.strip() else "Operator rejected the AI diagnosis as incorrect."
                        append_responsible_log(
                            str(case["case_id"]),
                            str(case["symptom"]),
                            diagnosis.get("root_cause", ""),
                            "Operator rejected proposed diagnosis.",
                            str(case["severity"]),
                            just_str,
                        )
                        st.session_state.rejecting = False
                        load_audit.clear()
                        st.session_state.decision_logged = True
                        st.toast("Rejection and safety notes logged.")
                        st.rerun()
                    if rej_btn_2.button("Cancel reject", width="stretch"):
                        st.session_state.rejecting = False
                        st.rerun()
                else:
                    st.markdown('<div class="action-label">Operator decision</div>', unsafe_allow_html=True)
                    approve, edit, reject = st.columns(3)
                    if approve.button("Approve", type="primary", width="stretch"):
                        log_decision(str(case["case_id"]), source, diagnosis.get("root_cause", ""), diagnosis.get("osi_layer", ""), confidence, "Approve & Deploy", edited=False)
                        load_audit.clear()
                        st.session_state.decision_logged = True
                        st.toast("Approval recorded. No command was executed.")
                        st.rerun()
                    if edit.button("Edit", width="stretch"):
                        st.session_state.editing = True
                        st.rerun()
                    if reject.button("Reject", width="stretch"):
                        st.session_state.rejecting = True
                        st.rerun()
            if st.session_state.decision_logged:
                st.success("Decision recorded. The console stays display-only — nothing was pushed to the network.")

with tab_audit:
    st.markdown(
        '''<div class="page-head">
          <div>
            <div class="kicker">Audit insights</div>
            <h2>Every operator decision, in order.</h2>
            <p>Approvals, edits, and rejections stay in the trail so the console can be reviewed without replaying the network.</p>
          </div>
        </div>''',
        unsafe_allow_html=True,
    )

    if audit.empty:
        st.markdown('<div class="panel"><div class="empty-note">No audit decisions yet. Approve, edit, or reject a live diagnosis to begin the trail.</div></div>', unsafe_allow_html=True)
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total decisions", metrics.get("total_cases", 0))
        c2.metric("Agreement rate", f"{metrics.get('agreement_rate', 0):.1f}%")
        c3.metric("Override rate", f"{metrics.get('override_rate', 0):.1f}%")

        st.markdown('<div class="section-label" style="margin-top:1.1rem">Recent activity</div>', unsafe_allow_html=True)
        recent = audit.copy()
        recent["_sort"] = pd.to_datetime(recent.get("timestamp"), errors="coerce")
        recent = recent.sort_values("_sort", ascending=False).head(8)
        items = []
        for _, row in recent.iterrows():
            items.append(
                f'''<div class="t-item">
                  <div class="t-time">{html.escape(format_time(row.get("timestamp")))}</div>
                  <div class="t-body">
                    <div class="t-head">
                      <div class="meta" style="margin:0">{badge(row.get("case_id"))}{badge(row.get("decision"), decision_style(row.get("decision")))}{badge(row.get("source"))}{badge("Agree" if str(row.get("agreement")) == "Yes" else str(row.get("agreement") or "—"))}</div>
                    </div>
                    <div class="t-cause">{html.escape(str(row.get("root_cause") or "")[:180])}</div>
                  </div>
                </div>'''
            )
        st.markdown(f'<div class="timeline">{"".join(items)}</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-label" style="margin-top:1.2rem">Full trail</div>', unsafe_allow_html=True)
        audit_display = audit.copy()
        audit_display["timestamp"] = audit_display["timestamp"].map(format_time)
        display_cols = [col for col in ["timestamp", "case_id", "decision", "agreement", "source", "osi_layer"] if col in audit_display]
        st.dataframe(audit_display[display_cols].sort_values("timestamp", ascending=False), width="stretch", hide_index=True)


# ── NEW INCIDENT TAB ────────────────────────────────────────────────────────
with tab_new:
    cd = st.session_state.custom_diagnosis
    if cd is None:
        step_desc, step_diag, step_rev = "on", "", ""
    elif cd.get("source") == "error":
        step_desc, step_diag, step_rev = "done", "on", ""
    elif st.session_state.custom_decision_logged:
        step_desc, step_diag, step_rev = "done", "done", "done"
    else:
        step_desc, step_diag, step_rev = "done", "done", "on"

    st.markdown(
        f'''<div class="page-head" style="margin-bottom:.7rem">
          <div>
            <div class="kicker">Custom incident</div>
            <h2>Submit a new incident</h2>
            <p>Paste any Cisco IOS show output below. The rule engine checks first — Gemini AI is the fallback for unknown patterns.</p>
          </div>
          <div class="steps">
            <span class="step {step_desc}"><b>1</b> Describe</span>
            <span class="step {step_diag}"><b>2</b> Diagnose</span>
            <span class="step {step_rev}"><b>3</b> Review</span>
          </div>
        </div>''',
        unsafe_allow_html=True,
    )

    form_col, result_col = st.columns([1.15, 1.55], gap="small")

    with form_col:
        st.markdown('<div class="col-kicker">Incident input</div>', unsafe_allow_html=True)
        st.markdown(
            '''<div class="block-head" style="margin-bottom:.5rem">
              <div><h3 style="margin:0">Incident details</h3></div>
            </div>''',
            unsafe_allow_html=True,
        )

        custom_symptom = st.text_input(
            "Symptom",
            placeholder="e.g. PC1 cannot reach Server2 in VLAN 50",
            key="ci_symptom",
        )
        custom_topology = st.text_input(
            "Topology note",
            placeholder="e.g. Router-on-a-stick, Gi0/0.50, Switch3 Fa0/7",
            key="ci_topology",
        )
        custom_severity = st.selectbox(
            "Severity",
            ["High", "Critical", "Medium", "Low"],
            index=2,
            key="ci_severity",
        )
        custom_show = st.text_area(
            "Paste show output  (use  |  to separate multiple commands)",
            placeholder="GigabitEthernet0/0.50 is administratively down, line protocol is down\n---\nshow ip route: ...",
            height=220,
            key="ci_show",
        )

        st.markdown(
            '''<div style="margin:.6rem 0 .3rem;font-size:.75rem;color:var(--text-dim)">
              Pipeline: deterministic rules checked first → Gemini AI only when no rule matches
            </div>''',
            unsafe_allow_html=True,
        )

        run_disabled = not custom_symptom.strip() or not custom_show.strip()
        if st.button("Run diagnosis", type="primary", width="stretch", key="ci_run", disabled=run_disabled):
            with st.spinner("Running deterministic rules… then AI if needed…"):
                st.session_state.custom_diagnosis = diagnose_custom(
                    custom_symptom.strip(),
                    custom_topology.strip(),
                    custom_show.strip(),
                )
                if st.session_state.custom_diagnosis:
                    st.session_state.custom_commands = "\n".join(st.session_state.custom_diagnosis.get("fix_steps", []))
                else:
                    st.session_state.custom_commands = ""
                st.session_state.custom_decision_logged = False
                st.session_state.custom_editing = False
                st.session_state.custom_rejecting = False
            st.rerun()

        if run_disabled and (not custom_symptom.strip() or not custom_show.strip()):
            st.caption("Fill in Symptom and Show output to enable diagnosis.")

        if st.button("Clear result", key="ci_clear", disabled=st.session_state.custom_diagnosis is None):
            st.session_state.custom_diagnosis = None
            st.session_state.custom_commands = ""
            st.session_state.custom_decision_logged = False
            st.session_state.custom_editing = False
            st.session_state.custom_rejecting = False
            st.rerun()

    with result_col:
        st.markdown('<div class="col-kicker">Diagnosis result</div>', unsafe_allow_html=True)

        if cd is None:
            st.markdown(
                '''<div class="empty" style="min-height:320px">
                  <div>
                    <div class="orbit"></div>
                    <div class="panel-title">Awaiting your incident</div>
                    <p class="panel-sub">Fill in the form and click <b>Run diagnosis</b>. The 26-rule engine runs instantly — AI is the fallback, not the first pass.</p>
                    <ul class="empty-steps">
                      <li>1. Paste any raw Cisco IOS show output</li>
                      <li>2. Deterministic rules scan for known patterns</li>
                      <li>3. Unknown faults escalate to Gemini AI</li>
                    </ul>
                  </div>
                </div>''',
                unsafe_allow_html=True,
            )
        else:
            cd_source = cd.get("source", "error")
            cd_conf = float(cd.get("confidence", 0))
            cd_pct = max(0, min(cd_conf, 1)) * 100

            if cd_source == "checker":
                src_label, src_style = "RULE ENGINE", "success"
                src_note = "Matched a known fault pattern deterministically — highest confidence."
            elif cd_source == "llm":
                src_label, src_style = "GEMINI AI", "warning"
                src_note = "No deterministic rule matched. AI reasoning applied — verify evidence carefully."
            else:
                src_label, src_style = "ENGINE ERROR", "danger"
                src_note = "Diagnosis failed. Check API credentials or try again."

            conf_note = "Low confidence — inspect evidence before acting." if cd_conf < WARNING_THRESHOLD else "Confidence above review threshold."

            st.markdown(
                f'''<div class="panel-title">Proposed root cause</div>
                <div class="meta">
                  {badge(src_label, src_style)}
                  {badge(cd.get("osi_layer", "Unknown"), "warning" if cd_conf < WARNING_THRESHOLD else "neutral")}
                </div>
                <div class="result-title">{html.escape(str(cd.get("root_cause", "No conclusion returned.")))}</div>
                <div class="conf-row">
                  <div class="ring" style="--p:{cd_pct:.0f}%"><div><strong>{cd_conf:.0%}</strong><span>CONF</span></div></div>
                  <div class="conf-copy">
                    <b>Model confidence</b><br>
                    {html.escape(conf_note)}<br>
                    <span style="font-size:.72rem;opacity:.7">{html.escape(src_note)}</span>
                  </div>
                </div>
                <div class="evidence"><b>Evidence</b><br>{html.escape(str(cd.get("evidence", "No evidence returned.")))}</div>''',
                unsafe_allow_html=True,
            )

            if cd_source == "error":
                st.error("No proposal generated. Check Gemini credentials or try a different input.")
            elif st.session_state.custom_editing:
                st.session_state.custom_commands = st.text_area("Review or edit proposed Cisco IOS commands", value=st.session_state.custom_commands, height=145, key="ci_edit_commands")
                edit_justification = st.text_input("Responsible AI notes / correction justification", key="ci_edit_justification", placeholder="Why did you change this command?")
                edit_one, edit_two = st.columns(2)
                if edit_one.button("Save edited decision", type="primary", width="stretch", key="ci_save_edit"):
                    log_decision("CUSTOM", cd_source, cd.get("root_cause", ""), cd.get("osi_layer", ""), cd_conf, "Edit Commands", edited=True)
                    just_str = edit_justification.strip() if edit_justification.strip() else "Operator modified recommended commands to fix parameters before deployment."
                    append_responsible_log(
                        "CUSTOM",
                        custom_symptom.strip(),
                        cd.get("root_cause", ""),
                        f"Operator edited commands to:\n{st.session_state.custom_commands}",
                        custom_severity,
                        just_str,
                    )
                    load_audit.clear()
                    st.session_state.custom_decision_logged = True
                    st.session_state.custom_editing = False
                    st.toast("Edited decision and operator notes recorded.")
                    st.rerun()
                if edit_two.button("Cancel", width="stretch", key="ci_cancel_edit"):
                    st.session_state.custom_editing = False
                    st.rerun()
            else:
                st.markdown('<div class="remediation-label">Recommended remediation</div>', unsafe_allow_html=True)
                st.markdown(commands_html(cd.get("fix_steps", []), cd.get("next_command", "")), unsafe_allow_html=True)

                if st.session_state.custom_rejecting:
                    reject_justification = st.text_input("Responsible AI notes / rejection justification", key="ci_reject_justification", placeholder="Why is this diagnosis incorrect or unsafe?")
                    rej_btn_1, rej_btn_2 = st.columns(2)
                    if rej_btn_1.button("Confirm rejection", type="primary", width="stretch", key="ci_confirm_reject"):
                        log_decision("CUSTOM", cd_source, cd.get("root_cause", ""), cd.get("osi_layer", ""), cd_conf, "Reject", edited=False)
                        just_str = reject_justification.strip() if reject_justification.strip() else "Operator rejected the AI diagnosis as incorrect."
                        append_responsible_log(
                            "CUSTOM",
                            custom_symptom.strip(),
                            cd.get("root_cause", ""),
                            "Operator rejected proposed diagnosis.",
                            custom_severity,
                            just_str,
                        )
                        st.session_state.custom_rejecting = False
                        load_audit.clear()
                        st.session_state.custom_decision_logged = True
                        st.toast("Rejection and safety notes logged.")
                        st.rerun()
                    if rej_btn_2.button("Cancel reject", width="stretch", key="ci_cancel_reject"):
                        st.session_state.custom_rejecting = False
                        st.rerun()
                else:
                    st.markdown('<div class="action-label">Operator decision</div>', unsafe_allow_html=True)
                    approve, edit, reject = st.columns(3)
                    if approve.button("Approve", type="primary", width="stretch", key="ci_approve"):
                        log_decision("CUSTOM", cd_source, cd.get("root_cause", ""), cd.get("osi_layer", ""), cd_conf, "Approve & Deploy", edited=False)
                        load_audit.clear()
                        st.session_state.custom_decision_logged = True
                        st.toast("Approval recorded. No command was executed.")
                        st.rerun()
                    if edit.button("Edit", width="stretch", key="ci_edit"):
                        st.session_state.custom_editing = True
                        st.rerun()
                    if reject.button("Reject", width="stretch", key="ci_reject"):
                        st.session_state.custom_rejecting = True
                        st.rerun()

            if st.session_state.custom_decision_logged:
                st.success("Decision recorded. The console stays display-only — nothing was pushed to the network.")

            st.markdown(
                f'''<div style="margin-top:.8rem;padding:.55rem .75rem;border-radius:8px;background:var(--surface-alt,rgba(255,255,255,.04));font-size:.75rem;color:var(--text-dim)">
                  <b>Diagnostics</b> · Source: {html.escape(src_label)} · OSI Layer: {html.escape(str(cd.get("osi_layer","?")))} · Confidence: {cd_conf:.0%}
                </div>''',
                unsafe_allow_html=True,
            )

# ── FOOTER ───────────────────────────────────────────────────────────────────
st.markdown(
    f'''<div class="site-footer">
      <div class="footer-grid">
        <div class="footer-brand">
          <div class="footer-mark">NS</div>
          <div>
            <h4>NetSage AI</h4>
            <p>Human-in-the-loop diagnostics for Cisco IOS. The console proposes a root cause and a fix. Operators approve, edit, or reject. Nothing is pushed to the network from this screen.</p>
          </div>
        </div>
        <div class="footer-col">
          <h5>Workspace</h5>
          <span>Operator console</span>
          <span>Governance metrics</span>
          <span>Audit trail</span>
          <span>Responsible AI log</span>
        </div>
        <div class="footer-col">
          <h5>Safety</h5>
          <span>Rule engine first</span>
          <span>Gemini fallback only</span>
          <span>Display-only commands</span>
          <span>Human sign-off required</span>
        </div>
        <div class="footer-col">
          <h5>System</h5>
          <div class="footer-status">
            <em><i></i>Engine ready · {total_cases} live cases</em>
            <em><i></i>{len(RULE_CATALOG)} deterministic rules</em>
            <em><i></i>{reviewed} cases reviewed</em>
          </div>
        </div>
      </div>
      <div class="footer-bar">
        <span>© 2026 NetSage AI · Cisco networking lab console</span>
        <span>No device access · No auto-deploy · Operator remains accountable</span>
      </div>
    </div>''',
    unsafe_allow_html=True,
)
