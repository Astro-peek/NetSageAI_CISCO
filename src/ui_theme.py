"""Shared visual system for the NetSage operator console."""

THEME_CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Manrope:wght@400;500;600;700;800&display=swap');

:root{
  --bg:#070b10;
  --bg-2:#0b1118;
  --surface:#101820;
  --surface-2:#141e28;
  --ink:#eef4f8;
  --muted:#7d8fa3;
  --faint:#5b6d80;
  --line:rgba(94,160,176,.16);
  --line-strong:rgba(94,160,176,.28);
  --accent:#3ee0c4;
  --accent-2:#5ee7ff;
  --accent-dim:rgba(62,224,196,.12);
  --amber:#ffb020;
  --rose:#ff5d73;
  --violet:#9b8cff;
  --ok:#3ee0c4;
  --shadow:0 18px 50px rgba(0,0,0,.35);
  --radius:16px;
  --mono:'IBM Plex Mono',ui-monospace,Consolas,monospace;
  --sans:'Manrope',ui-sans-serif,system-ui,sans-serif;
}

html,body,.stApp{
  background:var(--bg);
  color:var(--ink);
  font-family:var(--sans);
  min-height:100vh!important;
  margin:0!important;
  padding:0!important;
}
.stApp{
  background:
    radial-gradient(1200px 520px at 8% -10%,rgba(62,224,196,.08),transparent 42%),
    radial-gradient(900px 480px at 100% 0%,rgba(94,231,255,.06),transparent 36%),
    linear-gradient(180deg,#070b10 0%,#080d13 100%);
  min-height:100vh!important;
}
.stApp:before{
  content:"";
  position:fixed;inset:0;pointer-events:none;opacity:.35;z-index:0;
  background-image:
    linear-gradient(rgba(94,160,176,.05) 1px,transparent 1px),
    linear-gradient(90deg,rgba(94,160,176,.05) 1px,transparent 1px);
  background-size:48px 48px;
  mask-image:linear-gradient(180deg,#000 0%,transparent 78%);
}
.stApp>div{position:relative;z-index:1}
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],
#MainMenu,header[data-testid="stHeader"],div[data-testid="stStatusWidget"],.stDeployButton{display:none!important}
.block-container{
  max-width:1520px;
  padding:1rem 1.35rem 0!important;
  padding-bottom:0!important;
  min-height:100vh!important;
  display:flex!important;
  flex-direction:column!important;
}
@media(max-width:900px){.block-container{padding:.8rem .75rem 0!important;padding-bottom:0!important}}
[data-testid="stAppViewBlockContainer"]{padding-bottom:0!important}
[data-testid="stBottom"],[data-testid="stBottomBlockContainer"]{display:none!important;height:0!important}
.stApp > div[data-testid="stAppViewContainer"]{padding-bottom:0!important;min-height:100vh!important}
footer,[data-testid="stFooter"]{display:none!important;height:0!important}
section[tabindex="0"]{padding-bottom:0!important}

/* Main vertical block must stretch to force sticky footer behavior */
.block-container > [data-testid="stVerticalBlock"] {
  flex: 1 1 auto!important;
  display: flex!important;
  flex-direction: column!important;
  gap: .62rem!important;
}

/* Ensure the stElementContainer with footer goes to bottom of page */
.stElementContainer:has(.site-footer) {
  margin-top: auto!important;
  padding-bottom: 0!important;
  margin-bottom: 0!important;
}

h1,h2,h3,p,label,span{font-family:var(--sans)}
hr{border:none;border-top:1px solid var(--line);margin:1.2rem 0}

.topbar{
  display:flex;align-items:center;justify-content:space-between;gap:1rem;
  padding:.7rem .9rem;margin:0 0 1.05rem;
  background:linear-gradient(180deg,rgba(16,24,32,.92),rgba(16,24,32,.78));
  border:1px solid var(--line);border-radius:18px;
  box-shadow:var(--shadow),inset 0 1px 0 rgba(255,255,255,.04);
  backdrop-filter:blur(16px);
}
.brand{display:flex;align-items:center;gap:.75rem;min-width:0}
.brand-mark{
  width:38px;height:38px;border-radius:12px;flex:none;
  display:grid;place-items:center;font-weight:800;letter-spacing:-.08em;
  color:#04140f;background:linear-gradient(135deg,#5ee7ff,#3ee0c4);
  box-shadow:0 0 0 4px rgba(62,224,196,.12),0 8px 20px rgba(62,224,196,.18);
}
.brand h1{margin:0;font-size:1.02rem;font-weight:800;letter-spacing:-.03em;color:var(--ink);line-height:1.1}
.brand p{margin:.12rem 0 0;color:var(--muted);font-size:.72rem;font-weight:600}
.top-meta{display:flex;flex-wrap:wrap;gap:.45rem;justify-content:flex-end}
.chip{
  display:inline-flex;align-items:center;gap:.4rem;
  padding:.32rem .62rem;border-radius:999px;
  border:1px solid var(--line);background:rgba(255,255,255,.03);
  color:var(--muted);font-size:.68rem;font-weight:700;letter-spacing:.04em;
}
.chip.live{color:var(--accent);border-color:rgba(62,224,196,.28);background:var(--accent-dim)}
.live-dot{width:7px;height:7px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 4px rgba(62,224,196,.16);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}

div[data-testid="stTabs"]{gap:0}
div[data-testid="stTabBar"]{
  gap:.35rem;padding:.28rem;margin:0 0 1.15rem;
  background:rgba(16,24,32,.8);border:1px solid var(--line);border-radius:14px;
}
button[data-baseweb="tab"]{
  height:40px!important;border:none!important;border-radius:10px!important;
  background:transparent!important;color:var(--muted)!important;
  font-size:.78rem!important;font-weight:800!important;letter-spacing:.08em!important;
  padding:0 1.05rem!important;
}
button[data-baseweb="tab"] *{color:inherit!important}
button[data-baseweb="tab"]:hover{color:var(--ink)!important;background:rgba(255,255,255,.04)!important}
button[data-baseweb="tab"][aria-selected="true"]{
  color:#04140f!important;background:linear-gradient(135deg,#5ee7ff,#3ee0c4)!important;
  box-shadow:0 6px 18px rgba(62,224,196,.22)!important;
}

.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:.6rem;margin:0 0 .65rem}
.kicker{color:var(--accent);font-size:.68rem;font-weight:800;letter-spacing:.16em;text-transform:uppercase}
.page-head h2{margin:.2rem 0 0;font-size:clamp(1.35rem,2.4vw,1.85rem);letter-spacing:-.04em;font-weight:800}
.page-head p{margin:.28rem 0 0;color:var(--muted);font-size:.86rem;max-width:42rem}
.steps{display:flex;gap:.45rem;flex-wrap:wrap}
.step{
  display:flex;align-items:center;gap:.4rem;padding:.34rem .65rem;border-radius:999px;
  border:1px solid var(--line);color:var(--faint);font-size:.68rem;font-weight:700;
}
.step b{width:16px;height:16px;border-radius:50%;display:grid;place-items:center;font-size:.62rem;background:#1a2430}
.step.on{color:var(--ink);border-color:rgba(62,224,196,.3);background:var(--accent-dim)}
.step.on b{background:var(--accent);color:#04140f}
.step.done{color:var(--accent)}

.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin:0 0 1.1rem}
@media(max-width:900px){.kpi-row{grid-template-columns:1fr 1fr}}
.kpi{
  min-height:92px;padding:1rem 1.05rem;border-radius:14px;
  background:linear-gradient(180deg,rgba(20,30,40,.9),rgba(16,24,32,.86));
  border:1px solid var(--line);box-shadow:inset 0 1px 0 rgba(255,255,255,.03);
}
.kpi .value{font-size:1.55rem;font-weight:800;letter-spacing:-.05em;line-height:1}
.kpi .label{margin-top:.35rem;color:var(--muted);font-size:.72rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase}
.kpi .hint{margin-top:.28rem;color:var(--faint);font-size:.7rem}
.kpi.warn .value{color:var(--amber)}
.kpi.ok .value{color:var(--accent)}
.kpi.hot .value{color:var(--rose)}

.panel{
  background:linear-gradient(180deg,rgba(16,24,32,.94),rgba(13,18,25,.92));
  border:1px solid var(--line);border-radius:var(--radius);
  padding:1.05rem 1.1rem 1.15rem;margin-bottom:.85rem;
  box-shadow:var(--shadow);
}
.panel-title{font-size:.92rem;font-weight:800;letter-spacing:-.02em}
.panel-sub{color:var(--muted);font-size:.75rem;margin-top:.2rem;line-height:1.45}
.section-label{font-size:.68rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 .55rem}

.badge{
  display:inline-flex;align-items:center;line-height:1;
  padding:.32rem .5rem;border-radius:7px;font-size:.64rem;font-weight:800;
  letter-spacing:.03em;border:1px solid var(--line);background:#15202a;color:#c5d4e0;
}
.meta{display:flex;gap:.4rem;flex-wrap:wrap;margin:.7rem 0 .85rem}
.severity-critical{color:#ffc2cb;background:rgba(255,93,115,.12);border-color:rgba(255,93,115,.32)}
.severity-high{color:#ffd59a;background:rgba(255,176,32,.12);border-color:rgba(255,176,32,.3)}
.severity-medium{color:#c9c4ff;background:rgba(155,140,255,.12);border-color:rgba(155,140,255,.28)}
.severity-low{color:#b7fff0;background:rgba(62,224,196,.1);border-color:rgba(62,224,196,.28)}
.success{color:#b7fff0;background:rgba(62,224,196,.1);border-color:rgba(62,224,196,.28)}
.warning{color:#ffd59a;background:rgba(255,176,32,.1);border-color:rgba(255,176,32,.28)}
.danger{color:#ffc2cb;background:rgba(255,93,115,.12);border-color:rgba(255,93,115,.3)}

.terminal{background:#05080c;border:1px solid var(--line);border-radius:12px;overflow:hidden}
.terminal-head{
  display:flex;align-items:center;justify-content:space-between;
  padding:.55rem .75rem;background:#0c141c;border-bottom:1px solid var(--line);
  color:var(--faint);font-size:.66rem;font-weight:800;letter-spacing:.08em;font-family:var(--mono)
}
.lights{display:flex;gap:5px}
.lights i{width:8px;height:8px;border-radius:50%;background:#2a3a48}
.lights i:first-child{background:#ff5d73}
.lights i:nth-child(2){background:#ffb020}
.lights i:nth-child(3){background:#3ee0c4}
.terminal pre{
  margin:0;padding:1rem 1.05rem;min-height:280px;max-height:420px;overflow:auto;
  color:#9fe8d8;font:12.5px/1.7 var(--mono);white-space:pre-wrap;word-break:break-word;
}
.terminal-signal{display:block;background:rgba(255,93,115,.1);color:#ffb3be;margin:0 -.2rem;padding:0 .2rem;border-left:2px solid var(--rose)}

.queue-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:.35rem}
.queue-count{color:var(--accent);font-size:.72rem;font-weight:800}

div[data-testid="stRadio"]{max-height:520px;overflow:auto;padding-right:.2rem}
div[data-testid="stRadio"]>div{gap:.4rem!important}
div[data-testid="stRadio"] label{
  background:rgba(255,255,255,.025)!important;
  border:1px solid var(--line)!important;border-radius:10px!important;
  padding:.55rem .65rem!important;color:var(--ink)!important;
}
div[data-testid="stRadio"] label:hover{border-color:var(--line-strong)!important;background:rgba(62,224,196,.05)!important}
div[data-testid="stRadio"] label:has(input:checked){
  border-color:rgba(62,224,196,.45)!important;
  background:linear-gradient(90deg,rgba(62,224,196,.14),rgba(62,224,196,.04))!important;
  box-shadow:inset 3px 0 0 var(--accent);
}
div[data-testid="stRadio"] p{font-size:.74rem!important;font-weight:650!important;line-height:1.35!important}

.empty{
  min-height:280px;display:grid;place-content:center;text-align:center;
  color:var(--muted);padding:1.4rem;
}
.orbit{margin:0 auto .8rem;width:42px;height:42px;border:2px solid #243140;border-top-color:var(--accent);border-radius:50%;animation:spin 1.1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.empty-steps{margin:.9rem auto 0;padding:0;list-style:none;text-align:left;max-width:240px;color:var(--faint);font-size:.74rem}
.empty-steps li{margin:.28rem 0}

.result-title{font-size:1.05rem;font-weight:800;line-height:1.4;margin:.55rem 0 .85rem;color:var(--ink)}
.conf-row{display:flex;align-items:center;gap:1rem;margin:.2rem 0 .85rem}
.ring{
  width:76px;height:76px;border-radius:50%;flex:none;
  display:grid;place-items:center;
  background:conic-gradient(var(--accent) var(--p),#1c2833 0);
  box-shadow:0 0 0 4px rgba(62,224,196,.08);
}
.ring>div{
  width:58px;height:58px;border-radius:50%;background:#101820;
  display:grid;place-items:center;text-align:center;
}
.ring strong{font-size:.92rem;letter-spacing:-.04em}
.ring span{display:block;color:var(--faint);font-size:.55rem;font-weight:700;letter-spacing:.06em}
.conf-copy{color:var(--muted);font-size:.75rem;line-height:1.45}
.conf-copy b{color:var(--ink)}
.evidence{
  border-left:3px solid var(--accent-2);padding:.7rem .8rem;border-radius:0 10px 10px 0;
  background:rgba(94,231,255,.05);color:#d5e7ef;font-size:.78rem;line-height:1.5;
}
.cli-box{margin-top:.35rem;background:#05080c;border:1px solid var(--line);border-radius:10px;overflow:hidden}
.cli-row{display:flex;gap:.7rem;align-items:flex-start;padding:.55rem .75rem;border-bottom:1px solid rgba(94,160,176,.1);font-family:var(--mono);font-size:12px;line-height:1.5;color:#b7fff0}
.cli-row:last-child{border-bottom:none}
.cli-n{color:var(--faint);min-width:1.1rem}
.footnote{font-size:.7rem;color:var(--faint);margin-top:.55rem}
.action-label{margin:1rem 0 .45rem;font-size:.68rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}

.stButton>button{
  border-radius:10px!important;font-weight:800!important;font-size:.84rem!important;
  min-height:42px!important;border:1px solid var(--line-strong)!important;
  background:rgba(255,255,255,.04)!important;color:var(--ink)!important;
  transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease!important;
}
.stButton>button:hover{transform:translateY(-1px)!important;border-color:var(--accent)!important;box-shadow:0 8px 20px rgba(62,224,196,.12)!important}
.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#5ee7ff,#3ee0c4)!important;
  border-color:transparent!important;color:#04140f!important;
  box-shadow:0 8px 22px rgba(62,224,196,.22)!important;
}
.stButton>button[kind="primary"]:hover{filter:brightness(1.05)!important;color:#04140f!important}

.stTextArea textarea,.stSelectbox [data-baseweb="select"]>div,.stTextInput input,.stMultiSelect [data-baseweb="select"]>div{
  background:#0c141c!important;border-color:var(--line)!important;color:var(--ink)!important;border-radius:10px!important;
  font-family:var(--sans)!important;
}
.stTextArea textarea{font-family:var(--mono)!important;font-size:.8rem!important}
.stSelectbox label,.stTextInput label,.stMultiSelect label,.stTextArea label,.stRadio label{
  color:var(--muted)!important;font-size:.72rem!important;font-weight:800!important;letter-spacing:.04em!important;
}
.stDataFrame{border:1px solid var(--line);border-radius:12px;overflow:hidden}
.stAlert{border-radius:12px!important}
[data-testid="stMetric"] label{color:var(--muted)!important;font-size:.72rem!important;font-weight:800!important}
[data-testid="stMetricValue"]{color:var(--ink)!important;font-weight:800!important}
[data-testid="stSpinner"]{color:var(--accent)!important}

.db-hero,.hero{
  border:1px solid var(--line);border-radius:20px;padding:1.35rem 1.45rem;margin:0 0 1.15rem;
  background:
    radial-gradient(500px 180px at 92% -20%,rgba(62,224,196,.16),transparent 55%),
    linear-gradient(135deg,rgba(16,24,32,.95),rgba(10,16,22,.92));
}
.db-hero h1,.hero h1{margin:.2rem 0 .35rem;font-size:clamp(1.5rem,2.6vw,2.05rem);letter-spacing:-.045em}
.db-hero p,.hero p{margin:0;color:var(--muted);max-width:46rem}

.gauge{
  background:#0c141c;border:1px solid var(--line);border-radius:14px;padding:1.1rem 1.15rem;min-height:230px
}
.gauge-top{display:flex;justify-content:space-between;gap:1rem;margin-bottom:.7rem}
.bar{height:10px;background:#1c2833;border-radius:99px;overflow:hidden}
.bar>span{display:block;height:100%;background:linear-gradient(90deg,#5ee7ff,#3ee0c4)}

.log-card{
  background:rgba(16,24,32,.94);border:1px solid var(--line);border-radius:16px;
  padding:1.2rem 1.25rem;margin-bottom:1rem;border-left:4px solid var(--accent);
}
.log-title{font-size:1.02rem;font-weight:800}
.log-meta{display:flex;gap:.4rem;flex-wrap:wrap;margin:.45rem 0 .7rem}
.log-k{font-size:.68rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0.7rem 0 .3rem}
.log-box{border-radius:10px;padding:.7rem .8rem;font-size:.82rem;line-height:1.5}
.log-ai{background:rgba(255,176,32,.06);border:1px dashed rgba(255,176,32,.28);color:#ffd59a}
.log-op{background:rgba(94,231,255,.06);border:1px dashed rgba(94,231,255,.25);color:#c9f3ff}
.log-lesson{background:rgba(62,224,196,.06);border:1px solid rgba(62,224,196,.2);color:#d7fff6}

.timeline{display:flex;flex-direction:column;gap:.65rem}
.t-item{
  display:grid;grid-template-columns:118px 1fr;gap:.8rem;align-items:start;
  padding:.85rem .95rem;border:1px solid var(--line);border-radius:12px;background:rgba(16,24,32,.8)
}
.t-time{font-family:var(--mono);font-size:.68rem;color:var(--faint);padding-top:.15rem}
.t-body{min-width:0}
.t-head{display:flex;justify-content:space-between;gap:.6rem;flex-wrap:wrap}
.t-cause{margin:.35rem 0 0;color:var(--muted);font-size:.78rem;line-height:1.4}
.empty-note{color:var(--muted);text-align:center;padding:1.4rem .5rem}
.foot{text-align:center;color:var(--faint);font-size:.7rem;margin-top:1.4rem;letter-spacing:.04em}

.block-head{display:flex;align-items:flex-end;justify-content:space-between;gap:.75rem;margin:.15rem 0 .55rem}
.block-head h3{margin:.12rem 0 0;font-size:1.05rem;letter-spacing:-.03em;color:var(--ink)}
.count-pill{
  flex:none;padding:.28rem .55rem;border-radius:999px;
  border:1px solid var(--line);background:rgba(62,224,196,.08);
  color:var(--accent);font-size:.68rem;font-weight:800;letter-spacing:.04em
}
.panel:empty,.stMarkdown:empty,[data-testid="stMarkdownContainer"]:empty{display:none!important;height:0!important;margin:0!important;padding:0!important;border:none!important}

[data-testid="stVerticalBlock"]{gap:.62rem!important}
[data-testid="stHorizontalBlock"]{gap:.7rem!important}
.stElementContainer:has(> .stMarkdown > div > div.panel:empty){display:none!important}

[data-testid="stWidgetLabel"] p,[data-testid="stWidgetLabel"] label{
  color:#9eb0c0!important;font-size:.78rem!important;font-weight:700!important
}
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-baseweb="input"] input{
  background:#0e161e!important;color:#e8f0f4!important;
  border:1px solid rgba(94,160,176,.22)!important;border-radius:10px!important;
  caret-color:#3ee0c4!important
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder{
  color:#7d93a6!important;opacity:1!important
}
[data-testid="stTextInput"]>div>div,
[data-baseweb="base-input"]{
  background:#0e161e!important;border-color:rgba(94,160,176,.22)!important
}

[data-baseweb="select"]>div{
  background-color:#0e161e!important;
  color:#e8f0f4!important;
  border-color:rgba(94,160,176,.22)!important;
  border-radius:10px!important;
  min-height:42px!important
}
[data-baseweb="select"] span,[data-baseweb="select"] svg{color:#e8f0f4!important;fill:#9bb0c2!important}
[data-baseweb="popover"],[data-baseweb="menu"],ul[role="listbox"]{
  background-color:#121c26!important;color:#e8f0f4!important;border:1px solid rgba(94,160,176,.2)!important
}
li[role="option"]{background:#121c26!important;color:#e8f0f4!important}
li[role="option"][aria-selected="true"],li[role="option"]:hover{background:#173038!important}

[data-testid="stRadio"]{background:transparent!important}
[data-testid="stRadio"]>div{gap:.42rem!important}
[data-testid="stRadio"] *,
[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p,
[data-testid="stRadio"] label,
[data-testid="stRadio"] span,
[data-testid="stRadio"] p,
[data-baseweb="radio"],
[data-baseweb="radio"] *{
  color:#e8f0f4!important;font-size:.8rem!important;line-height:1.4!important;font-weight:600!important
}
[data-testid="stRadio"] label{
  align-items:flex-start!important;
  background:#101820!important;
  border:1px solid rgba(94,160,176,.16)!important;
  border-radius:12px!important;
  padding:.7rem .8rem!important
}
[data-testid="stRadio"] label:hover{border-color:rgba(62,224,196,.35)!important;background:#132028!important}
[data-testid="stRadio"] label:has(input:checked){
  border-color:rgba(62,224,196,.5)!important;
  background:linear-gradient(90deg,rgba(62,224,196,.16),rgba(16,24,32,.4))!important;
  box-shadow:inset 3px 0 0 #3ee0c4
}
[data-testid="stRadio"] input{
  accent-color:#3ee0c4!important;margin-top:.28rem!important;
  width:16px!important;height:16px!important;flex:none!important;
  font-size:16px!important;filter:none!important
}
[data-testid="stRadio"] [data-testid="stWidgetLabel"]{display:none!important;height:0!important;margin:0!important}

.stMarkdown,[data-testid="stMarkdown"],[data-testid="stElementContainer"]:has(> .stMarkdown){
  margin-bottom:0!important
}
[data-testid="InputInstructions"],[data-testid="stToolbarActions"]{display:none!important}
div[data-testid="stTextInput"] label p{color:#9eb0c0!important}

[data-testid="stDataFrame"]{background:#101820!important}
[data-testid="stMetricValue"]{color:#e8f0f4!important}

[data-testid="stHorizontalBlock"]:has([data-testid="stRadio"]){
  display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;
  align-items:stretch!important;gap:12px!important;margin:.15rem 0 0!important
}
[data-testid="stHorizontalBlock"]:has([data-testid="stRadio"]) > div{
  background:linear-gradient(180deg,rgba(14,20,28,.96),rgba(10,15,20,.94));
  border:1px solid var(--line);border-radius:20px;
  padding:14px 14px 16px!important;min-width:0!important;flex:1 1 0!important;
  box-shadow:0 16px 40px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.03)
}
[data-testid="stHorizontalBlock"]:has([data-testid="stRadio"]) [data-testid="stHorizontalBlock"] > div{
  background:transparent!important;border:none!important;box-shadow:none!important;padding:0!important;flex:1 1 auto!important
}
[data-testid="stRadio"]{max-height:52vh;overflow:auto;padding-right:4px}
[data-testid="stHorizontalBlock"]:has([data-testid="stRadio"]) .panel{
  background:transparent;border:none;box-shadow:none;padding:0;margin:0
}

.col-kicker{color:var(--accent);font-size:.66rem;font-weight:800;letter-spacing:.16em;text-transform:uppercase;margin:0 0 .35rem}
.incident-title{font-size:1.22rem;font-weight:800;letter-spacing:-.035em;line-height:1.28;margin:.1rem 0 .4rem;color:var(--ink)}
.review-title{font-size:1.08rem;font-weight:800;letter-spacing:-.03em;margin:.15rem 0 .55rem}
.remediation-label{margin:1rem 0 .4rem;font-size:.66rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}

.site-footer{
  margin:1.6rem -1.35rem 0;padding:1.35rem 1.6rem 1.2rem;
  border-top:1px solid var(--line);
  background:linear-gradient(180deg,rgba(10,14,20,.4),rgba(6,9,13,.95));
}
.footer-grid{
  max-width:1520px;margin:0 auto;
  display:grid;grid-template-columns:1.4fr .9fr .9fr 1fr;gap:1.4rem;
}
@media(max-width:900px){.footer-grid{grid-template-columns:1fr 1fr;gap:1rem}}
.footer-brand{display:flex;gap:.7rem;align-items:flex-start}
.footer-mark{
  width:34px;height:34px;border-radius:10px;flex:none;display:grid;place-items:center;
  font-weight:800;color:#04140f;background:linear-gradient(135deg,#5ee7ff,#3ee0c4);letter-spacing:-.08em
}
.footer-brand h4{margin:0;font-size:.92rem;font-weight:800}
.footer-brand p{margin:.28rem 0 0;color:var(--muted);font-size:.74rem;line-height:1.45;max-width:22rem}
.footer-col h5{margin:0 0 .45rem;font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.footer-col span,.footer-col a{display:block;color:#c5d4e0;font-size:.8rem;margin:.28rem 0;text-decoration:none}
.footer-status{display:flex;flex-direction:column;gap:.4rem}
.footer-status em{
  font-style:normal;display:flex;align-items:center;gap:.4rem;
  color:var(--muted);font-size:.74rem;font-weight:650
}
.footer-status i{width:7px;height:7px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px rgba(62,224,196,.16)}
.footer-bar{
  max-width:1520px;margin:.95rem auto 0;padding-top:.8rem;
  border-top:1px solid rgba(94,160,176,.12);
  display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;
  color:var(--faint);font-size:.68rem;letter-spacing:.03em
}
"""


def inject_theme(st) -> None:
    st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)
