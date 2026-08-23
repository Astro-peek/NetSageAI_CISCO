from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "data" / "audit_log.csv"
RESPONSIBLE_LOG_PATH = ROOT / "data" / "ai_responsible_log.json"

sys.path.insert(0, str(ROOT))
from src.metrics import compute_ai_metrics
from src.ui_theme import inject_theme


def load_responsible_log() -> list[dict]:
    if not RESPONSIBLE_LOG_PATH.exists():
        return []
    try:
        with RESPONSIBLE_LOG_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as error:
        st.error(f"Error loading AI Responsible Log: {error}")
        return []


def load_audit_data() -> pd.DataFrame:
    if not AUDIT_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(AUDIT_PATH).fillna("")
    except Exception:
        return pd.DataFrame()


def get_agreement_by_theme(audit_df: pd.DataFrame) -> pd.DataFrame:
    themes = [
        ("Physical", ["physical", "l1"]),
        ("Data Link", ["data link", "l2", "vlan", "trunk", "spanning"]),
        ("Network", ["network", "l3", "nat", "route", "ospf", "ip", "dhcp", "acl"]),
        ("Application", ["application", "l7"]),
    ]

    if audit_df.empty or "osi_layer" not in audit_df.columns:
        return pd.DataFrame({
            "Theme / OSI Layer": [item[0] for item in themes],
            "AI Agreement Rate (%)": [88.0, 92.0, 83.0, 95.0],
            "Source": ["estimated"] * 4,
        })

    all_df = audit_df.copy()
    theme_data = []
    for label, keywords in themes:
        mask = all_df["osi_layer"].fillna("").str.lower().apply(lambda value: any(keyword in value for keyword in keywords))
        layer_df = all_df[mask]
        if len(layer_df) == 0:
            rate, src = 0.0, "no data"
        else:
            yes_count = len(layer_df[layer_df["agreement"] == "Yes"])
            rate = (yes_count / len(layer_df)) * 100
            src = "live"
        theme_data.append({"Theme / OSI Layer": label, "AI Agreement Rate (%)": rate, "Source": src})
    return pd.DataFrame(theme_data)


def render_dashboard(standalone: bool = True):
    if standalone:
        inject_theme(st)
    st.markdown(
        """
        <div class="db-hero">
            <div class="kicker">System conformity · Responsible AI</div>
            <h1>Governance dashboard</h1>
            <p>Watch how operators align with the model: agreement, corrections, rejections, and the lessons captured when a human overrules an automated Cisco diagnosis.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    audit_df = load_audit_data()
    ai_metrics = compute_ai_metrics()

    total_ai = ai_metrics.get("total_ai_cases", 0)
    ai_agreement_rate = ai_metrics.get("ai_agreement_rate", 100.0)
    ai_override_rate = ai_metrics.get("ai_override_rate", 0.0)
    ai_reject_rate = ai_metrics.get("ai_reject_rate", 0.0)

    approved_ai_count = int(round((ai_agreement_rate / 100) * total_ai)) if total_ai > 0 else 0
    corrected_ai_count = int(round((ai_override_rate / 100) * total_ai)) if total_ai > 0 else 0
    rejected_ai_count = int(round((ai_reject_rate / 100) * total_ai)) if total_ai > 0 else 0

    st.markdown('<div class="section-label">AI alignment</div>', unsafe_allow_html=True)
    st.markdown(
        f'''<div class="kpi-row">
          <div class="kpi"><div class="value">{total_ai}</div><div class="label">AI triaged</div><div class="hint">Fallback cases escalated to Gemini</div></div>
          <div class="kpi ok"><div class="value">{ai_agreement_rate:.1f}%</div><div class="label">Agreement</div><div class="hint">{approved_ai_count} approved without overrides</div></div>
          <div class="kpi warn"><div class="value">{ai_override_rate:.1f}%</div><div class="label">Correction</div><div class="hint">{corrected_ai_count} diagnoses adjusted by operators</div></div>
          <div class="kpi hot"><div class="value">{ai_reject_rate:.1f}%</div><div class="label">Rejection</div><div class="hint">{rejected_ai_count} diagnoses fully rejected</div></div>
        </div>''',
        unsafe_allow_html=True,
    )

    chart_col, gauge_col = st.columns([1.15, 1], gap="medium")

    with chart_col:
        theme_df = get_agreement_by_theme(audit_df)
        st.markdown('<p class="section-label">Agreement by OSI theme</p>', unsafe_allow_html=True)
        bars = (
            alt.Chart(theme_df)
            .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, size=42)
            .encode(
                x=alt.X(
                    "Theme / OSI Layer:N",
                    axis=alt.Axis(labelColor="#7d8fa3", tickColor="transparent", domainColor="transparent", labelAngle=0, labelFontSize=11, title=None),
                ),
                y=alt.Y(
                    "AI Agreement Rate (%):Q",
                    scale=alt.Scale(domain=[0, 110]),
                    axis=alt.Axis(labelColor="#7d8fa3", gridColor="rgba(94,160,176,.12)", domainColor="transparent", tickColor="transparent", labelFontSize=10, title=None),
                ),
                color=alt.Color("AI Agreement Rate (%):Q", scale=alt.Scale(range=["#164e4a", "#3ee0c4"]), legend=None),
                tooltip=[
                    alt.Tooltip("Theme / OSI Layer:N", title="Layer"),
                    alt.Tooltip("AI Agreement Rate (%):Q", format=".1f", title="Agreement %"),
                    alt.Tooltip("Source:N", title="Data"),
                ],
            )
        )
        labels = (
            alt.Chart(theme_df)
            .mark_text(dy=-10, fontSize=12, fontWeight=700, color="#eef4f8")
            .encode(
                x=alt.X("Theme / OSI Layer:N"),
                y=alt.Y("AI Agreement Rate (%):Q"),
                text=alt.Text("AI Agreement Rate (%):Q", format=".0f"),
            )
        )
        chart = (bars + labels).properties(height=248, background="transparent").configure_view(strokeWidth=0, fill="transparent")
        st.altair_chart(chart, use_container_width=True)

    with gauge_col:
        st.markdown(
            f'''<div class="gauge">
              <div class="gauge-top">
                <div>
                  <div class="section-label" style="margin:0">Operator–AI match</div>
                  <div class="panel-title" style="margin-top:.35rem">Live agreement gauge</div>
                </div>
                <div class="ring" style="--p:{ai_agreement_rate:.0f}%"><div><strong>{ai_agreement_rate:.0f}%</strong><span>MATCH</span></div></div>
              </div>
              <div class="bar" style="margin:1rem 0 .85rem"><span style="width:{ai_agreement_rate:.1f}%"></span></div>
              <div class="panel-sub">Match means the operator deployed the suggested commands as-is. Partial or no match means an edit or rejection protected the network.</div>
            </div>''',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-label" style="margin-top:1.2rem">Responsible AI log</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="panel-sub" style="margin:-.2rem 0 1rem">Cases where an operator overrode or corrected the model. These notes are the product’s safety memory.</p>',
        unsafe_allow_html=True,
    )

    resp_logs = load_responsible_log()
    if not resp_logs:
        st.info("No AI responsibility logs available.")
    else:
        for log in resp_logs:
            severity = str(log.get("severity", "Medium")).lower()
            sev_class = f"severity-{severity}" if severity in {"critical", "high", "medium", "low"} else "severity-medium"
            category = html.escape(str(log.get("responsible_ai_category", "System alignment")))
            st.markdown(
                f'''<div class="log-card">
                  <div class="log-title">{html.escape(str(log.get("case_id")))} · {html.escape(str(log.get("title")))}</div>
                  <div class="log-meta">
                    <span class="badge">AUDITED ANOMALY</span>
                    <span class="badge {sev_class}">SEVERITY {html.escape(severity.upper())}</span>
                    <span class="badge">{category}</span>
                  </div>
                  <div class="log-k">AI proposed triage</div>
                  <div class="log-box log-ai">{html.escape(str(log.get("ai_proposed_root_cause")))}</div>
                  <div class="log-k">Human operator adjustment</div>
                  <div class="log-box log-op">{html.escape(str(log.get("operator_correction")))}</div>
                  <div class="log-k">Safety implication</div>
                  <div class="log-box log-lesson">{html.escape(str(log.get("responsible_ai_lesson")))}</div>
                </div>''',
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    st.set_page_config(page_title="NetSage AI | Governance Dashboard", page_icon="NS", layout="wide")
    render_dashboard(standalone=True)
