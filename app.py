import streamlit as st
from agent import SchemePilot
from engine import LIKELY, POTENTIAL, INELIGIBLE, document_checklist, PASS, FAIL, UNKNOWN
from user_profile import FIELDS

st.set_page_config(page_title="SchemePilot", page_icon="⚖️", layout="wide")

VERDICT_META = {
    LIKELY:     {"label": "LIKELY",     "class": "stamp-likely",     "tab": "Likely"},
    POTENTIAL:  {"label": "POTENTIAL",  "class": "stamp-potential",  "tab": "Potential"},
    INELIGIBLE: {"label": "INELIGIBLE", "class": "stamp-ineligible", "tab": "Ineligible"},
}
CRIT_ICON = {PASS: "✓", FAIL: "✗", UNKNOWN: "?"}

OP_WORDS = {"==": "is", "!=": "is not", ">=": "is at least", "<=": "is at most", ">": "is more than", "<": "is less than"}

BOOL_PHRASES = {
    "is_student": ("a student", "not currently a student"),
    "owns_house": ("owns a house", "does not own a house"),
    "is_farmer": ("farms land", "does not farm land"),
    "is_income_tax_payer": ("has an income-tax payer in the household", "has no income-tax payer in the household"),
    "is_head_of_family": ("is the head of household", "is not the head of household"),
}


def format_value(field, v):
    if v is None:
        return "not on file"
    if field == "household_income":
        return f"₹{v:,}"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    return str(v)


def phrase_criterion(field, op, expected):
    """Turn a raw (field, op, value) rule into a plain-language requirement."""
    if isinstance(expected, bool) and field in BOOL_PHRASES:
        pos, neg = BOOL_PHRASES[field]
        want_true = expected if op == "==" else not expected
        return f"Applicant {pos if want_true else neg}"
    if field == "household_income":
        return f"Household income {OP_WORDS.get(op, op)} ₹{expected:,}"
    if field == "age":
        return f"Age {OP_WORDS.get(op, op)} {expected}"
    if field == "state":
        return f"Lives in {expected}" if op == "==" else f"Does not live in {expected}"
    if field == "residence":
        return f"Lives in a {expected} area" if op == "==" else f"Does not live in a {expected} area"
    if field == "gender":
        return f"Gender {OP_WORDS.get(op, op)} {expected}"
    if field == "social_category":
        return f"Social category {OP_WORDS.get(op, op)} {expected}"
    return f"{field.replace('_', ' ').capitalize()} {OP_WORDS.get(op, op)} {expected}"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
  --ink: #1B2A4A;
  --paper: #EDEAE0;
  --paper-line: #D8D3C3;
  --seal-gold: #B08A3E;
  --stamp-likely: #2F6B4F;
  --stamp-potential: #9C6B1F;
  --stamp-ineligible: #8C2F2A;
}

.stApp { background: var(--paper); }
section[data-testid="stSidebar"] { background: #E6E2D4; border-right: 1px solid var(--paper-line); }
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; color: var(--ink); }

/* ---- Masthead ---- */
.masthead { display:flex; align-items:baseline; justify-content:space-between;
  border-bottom: 3px double var(--ink); padding-bottom: 10px; margin-bottom: 4px; }
.masthead h1 { font-family:'Zilla Slab', serif; font-weight:700; font-size:2.3rem;
  margin:0; letter-spacing:0.2px; color: var(--ink); }
.masthead .file-ref { font-family:'IBM Plex Mono', monospace; font-size:0.78rem; color:#6b6455; text-align:right; }
.dossier-sub { font-family:'IBM Plex Mono', monospace; font-size:0.82rem; color:#6b6455; margin: 2px 0 18px 0; }

/* ---- Sidebar dossier heading ---- */
.dossier-head { font-family:'Zilla Slab', serif; font-weight:700; font-size:1.05rem;
  border-bottom: 1px solid var(--ink); padding-bottom:4px; margin-bottom:10px; }
.field-row { font-family:'IBM Plex Mono', monospace; font-size:0.83rem; padding:2px 0;
  border-bottom: 1px dotted var(--paper-line); }
.field-row b { color:#6b6455; font-weight:500; }

/* ---- Ledger summary strip ---- */
.ledger { display:flex; gap:0; border:1px solid var(--ink); margin-bottom:18px; }
.ledger-cell { flex:1; text-align:center; padding:10px 6px; border-right:1px solid var(--ink); }
.ledger-cell:last-child { border-right:none; }
.ledger-num { font-family:'Source Serif 4', serif; font-size:1.6rem; font-weight:700; line-height:1; }
.ledger-lab { font-family:'IBM Plex Mono', monospace; font-size:0.68rem; letter-spacing:0.5px; color:#6b6455; margin-top:2px; }

/* ---- File cards ---- */
.file-card { position:relative; background:#F6F4ED; border:1px solid var(--paper-line);
  border-top:1px solid var(--paper-line); padding:16px 18px 14px 18px; margin-bottom:16px; }
.file-head { display:flex; justify-content:space-between; align-items:flex-start;
  border-bottom:1px dashed var(--paper-line); padding-bottom:8px; margin-bottom:10px; }
.file-num { font-family:'IBM Plex Mono', monospace; font-size:0.72rem; color:#6b6455; }
.file-title { font-family:'Zilla Slab', serif; font-weight:600; font-size:1.15rem; margin-top:2px; }
.stamp { font-family:'IBM Plex Mono', monospace; font-weight:600; font-size:0.72rem;
  letter-spacing:1px; padding:4px 10px; border:2.5px solid; border-radius:3px;
  transform: rotate(-6deg); white-space:nowrap; }
.stamp-likely { color:var(--stamp-likely); border-color:var(--stamp-likely); }
.stamp-potential { color:var(--stamp-potential); border-color:var(--stamp-potential); }
.stamp-ineligible { color:var(--stamp-ineligible); border-color:var(--stamp-ineligible); }

.crit-row { font-family:'IBM Plex Mono', monospace; font-size:0.85rem; padding:1px 0; }
.crit-mark { display:inline-block; width:1.1em; }
.crit-yours { color:#8a8272; }
.crit-fail .crit-mark, .crit-fail b { color:var(--stamp-ineligible); }
.crit-pass .crit-mark { color:var(--stamp-likely); }
.crit-unk .crit-mark { color:var(--stamp-potential); }

.doc-section { margin-top:12px; padding-top:10px; border-top:1px dashed var(--paper-line); }
.doc-label { font-family:'IBM Plex Mono', monospace; font-size:0.68rem; letter-spacing:0.6px;
  color:#8a8272; text-transform:uppercase; margin-bottom:5px; }
.doc-chips { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px; }
.doc-chips:last-of-type { margin-bottom:0; }
.chip { font-family:'IBM Plex Mono', monospace; font-size:0.76rem; padding:3px 9px;
  border:1px solid; border-radius:2px; white-space:nowrap; }
.chip-have { color:var(--stamp-likely); border-color:var(--stamp-likely); background:rgba(47,107,79,0.07); }
.chip-need { color:var(--stamp-potential); border-color:var(--stamp-potential); background:rgba(156,107,31,0.07); }
.chip-none { font-family:'IBM Plex Mono', monospace; font-size:0.76rem; color:#a39c8c; font-style:italic; }

.file-foot { font-family:'IBM Plex Mono', monospace; font-size:0.76rem; color:#6b6455;
  margin-top:10px; padding-top:8px; border-top:1px dashed var(--paper-line); }
.warn-line { color:var(--stamp-potential); }

/* ---- Tabs restyle (best-effort; Streamlit internals) ---- */
button[data-baseweb="tab"] { font-family:'IBM Plex Mono', monospace !important; font-size:0.82rem !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="masthead">
  <h1>SchemePilot</h1>
  <div class="file-ref">DOSSIER&nbsp;SYSTEM<br>BENEFITS&nbsp;DIVISION</div>
</div>
<div class="dossier-sub">personal government benefits case file — advisory only, verify sample entries against the official source</div>
""", unsafe_allow_html=True)

if "agent" not in st.session_state:
    st.session_state.agent = SchemePilot()
    st.session_state.chat = [("assistant", "Tell me about yourself and your family — age, state, income, "
                              "occupation/studies, housing — in your own words. I'll ask about anything I need.")]
    st.session_state.results = None
agent = st.session_state.agent

chat_col, res_col = st.columns([1, 1.5])

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown('<div class="dossier-head">Applicant record</div>', unsafe_allow_html=True)
    filled = agent.profile
    total_fields = len(FIELDS)
    st.progress(min(len(filled) / total_fields, 1.0), text=f"{len(filled)}/{total_fields} fields on record")
    if filled:
        rows = "".join(f'<div class="field-row"><b>{k.replace("_"," ")}</b><br>{v}</div>' for k, v in filled.items())
        st.markdown(rows, unsafe_allow_html=True)
    else:
        st.caption("No entries yet — start the intake in chat.")

    st.divider()
    st.markdown('<div class="dossier-head">What-if simulation</div>', unsafe_allow_html=True)
    new_inc = st.number_input("Household income (₹)", 0, 10_000_000,
                               int(agent.profile.get("household_income", 300000)), 50_000)
    states = ["(unchanged)", "Karnataka", "Maharashtra", "Tamil Nadu", "Kerala", "Delhi"]
    new_state = st.selectbox("State", states)
    if st.button("Run simulation", use_container_width=True) and agent.profile:
        ch = {"household_income": new_inc}
        if new_state != "(unchanged)":
            ch["state"] = new_state
        diff = agent.simulate(ch)
        if diff:
            for d in diff:
                st.markdown(f'<div class="field-row"><b>{d["name"]}</b><br>'
                            f'{VERDICT_META[d["before"]]["label"]} → {VERDICT_META[d["after"]]["label"]}</div>',
                            unsafe_allow_html=True)
        else:
            st.caption("No verdicts change under this scenario.")

    st.divider()
    held = st.multiselect("Documents already on file",
                          ["income_certificate", "aadhaar", "bank_account", "enrollment_proof", "caste_certificate",
                           "address_proof", "ration_card", "land_records"])

# ---------- Chat ----------
with chat_col:
    for role, msg in st.session_state.chat:
        st.chat_message(role).write(msg)
    if text := st.chat_input("Describe your situation, or answer the question above…"):
        st.session_state.chat.append(("user", text))
        out = agent.handle(text)
        st.session_state.results = out["results"]
        q = out["next_question"]
        reply = (f"Got it. (Updated: {', '.join(out['updates']) or 'nothing new'}.)\n\n"
                 + (f"**Next question:** {q['question']}  \n*(Affects {q['affects']} scheme(s) still in play.)*"
                    if q else "I have enough information on file to evaluate every scheme in the dataset."))
        st.session_state.chat.append(("assistant", reply))
        st.rerun()

# ---------- Results ----------
with res_col:
    results = st.session_state.results
    if not results:
        st.info("Case file results will appear here once you've shared some details.")
    else:
        counts = {v: sum(1 for r in results if r.verdict == v) for v in (LIKELY, POTENTIAL, INELIGIBLE)}
        st.markdown(
            '<div class="ledger">' + "".join(
                f'<div class="ledger-cell"><div class="ledger-num" style="color:var(--{VERDICT_META[v]["class"]})">'
                f'{counts[v]}</div><div class="ledger-lab">{VERDICT_META[v]["tab"].upper()}</div></div>'
                for v in (LIKELY, POTENTIAL, INELIGIBLE)) + '</div>', unsafe_allow_html=True)

        tabs = st.tabs([f"{VERDICT_META[v]['tab']} ({counts[v]})" for v in (LIKELY, POTENTIAL, INELIGIBLE)])

        def render(results_subset):
            if not results_subset:
                st.caption("No files in this category yet.")
                return
            for i, r in enumerate(results_subset, 1):
                crit_html = ""
                for c in r.criteria:
                    cls = {PASS: "crit-pass", FAIL: "crit-fail", UNKNOWN: "crit-unk"}[c.status]
                    clause = phrase_criterion(c.field, c.op, c.expected)
                    yours = format_value(c.field, c.actual)
                    crit_html += (f'<div class="crit-row {cls}"><span class="crit-mark">{CRIT_ICON[c.status]}</span>'
                                  f'{clause} <span class="crit-yours">(yours: {yours})</span></div>')
                cl = document_checklist(r, held)
                have_chips = "".join(f'<span class="chip chip-have">✓ {d.replace("_"," ")}</span>' for d in cl["have"]) \
                    or '<span class="chip-none">none on file</span>'
                need_chips = "".join(f'<span class="chip chip-need">+ {d.replace("_"," ")}</span>' for d in cl["need"]) \
                    or '<span class="chip-none">none — all documents on file</span>'
                warn = '<div class="warn-line">⚠ sample criteria — unverified, check official source</div>' if not r.verified else ""
                st.markdown(
                    f'<div class="file-card">'
                    f'<div class="file-head"><div><div class="file-num">FILE NO. {i:02d}</div>'
                    f'<div class="file-title">{r.name}</div></div>'
                    f'<div class="stamp {VERDICT_META[r.verdict]["class"]}">{VERDICT_META[r.verdict]["label"]}</div></div>'
                    f'{crit_html}'
                    f'<div class="doc-section">'
                    f'<div class="doc-label">Have</div><div class="doc-chips">{have_chips}</div>'
                    f'<div class="doc-label">Still need</div><div class="doc-chips">{need_chips}</div>'
                    f'</div>'
                    f'<div class="file-foot">filed under: {r.source_url}{warn}</div></div>', unsafe_allow_html=True)

        for tab, v in zip(tabs, (LIKELY, POTENTIAL, INELIGIBLE)):
            with tab:
                render([r for r in results if r.verdict == v])