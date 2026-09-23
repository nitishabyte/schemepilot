import streamlit as st
from agent import SchemePilot
from engine import LIKELY, POTENTIAL, INELIGIBLE, document_checklist, PASS, FAIL, UNKNOWN
from user_profile import FIELDS

st.set_page_config(page_title="SchemePilot", page_icon="🏛️", layout="wide")

st.markdown("""
<style>
.verdict-card { border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;
    border-left: 6px solid var(--bc); background: var(--bg); }
.verdict-LIKELY    { --bc:#22c55e; --bg:rgba(34,197,94,0.08); }
.verdict-POTENTIAL { --bc:#eab308; --bg:rgba(234,179,8,0.08); }
.verdict-INELIGIBLE{ --bc:#ef4444; --bg:rgba(239,68,68,0.06); }
.verdict-title { font-weight:600; font-size:1.02rem; margin-bottom:4px; }
.crit-row { font-size:0.92rem; margin:2px 0; }
.doc-line { font-size:0.85rem; color:#888; margin-top:6px; }
</style>
""", unsafe_allow_html=True)

st.title("🏛️ SchemePilot — Personal Government Benefits Agent")
st.caption("Advisory only. Sample schemes are unverified — check the official source before applying.")

if "agent" not in st.session_state:
    st.session_state.agent = SchemePilot()
    st.session_state.chat = [("assistant", "Tell me about yourself and your family — age, state, income, "
                              "occupation/studies, housing — in your own words. I'll ask about anything I need.")]
    st.session_state.results = None
agent = st.session_state.agent
CRIT_ICON = {PASS: "✅", FAIL: "❌", UNKNOWN: "❔"}
VERDICT_LABEL = {LIKELY: "🟢 Likely eligible", POTENTIAL: "🟡 Potentially eligible", INELIGIBLE: "🔴 Appears ineligible"}

chat_col, res_col = st.columns([1, 1.5])

# ---------- Sidebar ----------
with st.sidebar:
    st.subheader("Your profile")
    filled = agent.profile
    total_fields = len(FIELDS)
    st.progress(min(len(filled) / total_fields, 1.0), text=f"{len(filled)}/{total_fields} fields known")
    if filled:
        for k, v in filled.items():
            st.markdown(f"**{k.replace('_', ' ')}:** {v}")
    else:
        st.caption("Nothing yet — start chatting.")

    st.divider()
    st.subheader("What-if simulator")
    new_inc = st.number_input("Household income (₹)", 0, 10_000_000,
                               int(agent.profile.get("household_income", 300000)), 50_000)
    states = ["(unchanged)", "Karnataka", "Maharashtra", "Tamil Nadu", "Kerala", "Delhi"]
    new_state = st.selectbox("State", states)
    if st.button("Simulate", use_container_width=True) and agent.profile:
        ch = {"household_income": new_inc}
        if new_state != "(unchanged)":
            ch["state"] = new_state
        diff = agent.simulate(ch)
        if diff:
            for d in diff:
                st.markdown(f"**{d['name']}**  \n{VERDICT_LABEL[d['before']]} → {VERDICT_LABEL[d['after']]}")
        else:
            st.caption("No verdicts change with this scenario.")

    st.divider()
    held = st.multiselect("Documents you already have",
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
                    if q else "I have enough information to evaluate every scheme in the dataset."))
        st.session_state.chat.append(("assistant", reply))
        st.rerun()

# ---------- Results ----------
with res_col:
    results = st.session_state.results
    if not results:
        st.info("Scheme results will appear here once you've shared some details.")
    else:
        counts = {v: sum(1 for r in results if r.verdict == v) for v in (LIKELY, POTENTIAL, INELIGIBLE)}
        c1, c2, c3 = st.columns(3)
        c1.metric("🟢 Likely", counts[LIKELY])
        c2.metric("🟡 Potential", counts[POTENTIAL])
        c3.metric("🔴 Ineligible", counts[INELIGIBLE])

        tab_likely, tab_potential, tab_ineligible = st.tabs([
            f"🟢 Likely ({counts[LIKELY]})", f"🟡 Potential ({counts[POTENTIAL]})", f"🔴 Ineligible ({counts[INELIGIBLE]})"])

        def render(results_subset):
            if not results_subset:
                st.caption("None here yet.")
                return
            for r in results_subset:
                crit_html = "".join(
                    f"<div class='crit-row'>{CRIT_ICON[c.status]} <b>{c.field.replace('_',' ')}</b> "
                    f"{c.op} {c.expected} — yours: {c.actual if c.actual is not None else 'not provided'}</div>"
                    for c in r.criteria)
                cl = document_checklist(r, held)
                doc_html = (f"<div class='doc-line'>📄 Have: {', '.join(cl['have']) or 'none'} "
                            f"&nbsp;|&nbsp; Need: {', '.join(cl['need']) or 'none'}</div>")
                unverified = "" if r.verified else "<div class='doc-line'>⚠️ Sample criteria — not verified against the official source.</div>"
                st.markdown(
                    f"<div class='verdict-card verdict-{r.verdict}'>"
                    f"<div class='verdict-title'>{r.name}</div>{crit_html}{doc_html}{unverified}"
                    f"<div class='doc-line'>Source: {r.source_url}</div></div>", unsafe_allow_html=True)

        with tab_likely: render([r for r in results if r.verdict == LIKELY])
        with tab_potential: render([r for r in results if r.verdict == POTENTIAL])
        with tab_ineligible: render([r for r in results if r.verdict == INELIGIBLE])