# SchemePilot — Personal Government Benefits Agent

An agentic AI project that turns "which government schemes am I eligible for?" into a
conversational, evidence-based process instead of a static keyword search — built for
an agentic AI coursework assignment.

**The core design choice:** the LLM only ever *reads and asks*; it never *decides*.
Eligibility is computed by a deterministic Python rules engine, not by asking a model
to judge eligibility directly. This makes every verdict auditable, reproducible, and
unit-testable — which the evaluation results below back up with real numbers, not just
a design claim.

## How it works

```
  User message
       │
       ▼
  Profile extraction  (LLM, with a regex fallback if no API key is set)
       │
       ▼
  Deterministic eligibility engine  (plain Python — PASS / FAIL / UNKNOWN per criterion)
       │
       ▼
  Verdict: LIKELY / POTENTIAL / INELIGIBLE, per scheme, with a full breakdown
       │
       ▼
  Adaptive follow-up question  (picks whichever unknown field affects the most
  still-undecided schemes — not a fixed form)
```

A "why am I not eligible?" explanation and a "what if my income changes?" simulator are
both just re-runs of the same deterministic engine, so they're cheap, instant, and
consistent by construction.

### Agent orchestration: LangGraph

The loop above (extract → evaluate → ask, repeated per turn) is orchestrated by a
compiled **LangGraph `StateGraph`** (`graph_agent.py`), not just a hand-written Python
loop. Each of the three steps is its own graph node; conversation state persists
across turns via LangGraph's `MemorySaver` checkpointer, keyed by a `thread_id` — the
standard LangGraph pattern for a multi-turn conversational agent.

Deliberately unchanged by this: `engine.py` still has zero LLM calls in it. The
framework governs *when* to extract, evaluate, and ask — it still never decides
eligibility itself. That hybrid separation (LLM extracts, deterministic engine
decides) is the same regardless of which orchestration layer sits on top of it.

`app.py` tries to import the LangGraph-backed agent first and falls back to a plain
Python version (`agent.py`, no framework) if `langgraph` isn't installed, so the app
still runs in a bare environment. The sidebar shows which one is active
(`Orchestration: LangGraph` or the fallback message).

## Project layout

| File | Role |
|---|---|
| `engine.py` | The deterministic rules engine. No LLM calls anywhere in this file — that's deliberate. Produces per-criterion PASS/FAIL/UNKNOWN, a scheme verdict, `explain()`, `what_if()`, and a document checklist. |
| `user_profile.py` | The profile schema, value validation, and a regex-based extractor that works fully offline. |
| `llm.py` | LLM-based profile extraction, with support for either a free provider (Groq) or a paid one (Anthropic) — see Setup below. Falls back to the regex extractor if neither is configured. |
| `questions.py` | The adaptive question picker: asks about whichever field is unknown across the most schemes that haven't already failed. |
| `agent.py` | The plain-Python orchestration loop: extract → update profile → evaluate → pick next question. No agent framework — used as the fallback if `langgraph` isn't installed. |
| `graph_agent.py` | The same loop, expressed as a compiled **LangGraph** `StateGraph` with a checkpointer for multi-turn state. See "Agent orchestration" above. |
| `audit.py` | Appends every evaluation to `logs/audit.jsonl`, so any verdict can be traced back to the profile that produced it. |
| `app.py` | The Streamlit UI — a case-file/dossier-styled interface with chat, a live scheme "ledger," and a what-if simulator. |
| `data/schemes.json` | Scheme eligibility rules. **Sample data — see Limitations below.** |
| `eval/` | The evaluation harness (see Evaluation below). |
| `tests/` | Unit tests for the engine, extraction logic, and the LangGraph agent (`test_graph_agent.py`). |

## Setup

```bash
pip install -r requirements.txt   # now includes langgraph
streamlit run app.py
pytest
```

LLM-based extraction and the eval harness's LLM comparisons need an API key. Either
works — the code auto-detects which one is set:

```bash
export GROQ_API_KEY=gsk_...        # free, no billing: console.groq.com/keys
# or
export ANTHROPIC_API_KEY=sk-ant-... # paid
```

Without either, the app and all tests still run fully offline using the regex
extractor in `user_profile.py`.

## Evaluation

Run the full harness (personas, extraction, and LLM comparisons):

```bash
python eval/run_all.py       # writes eval/report.md
```

Individual scripts (`eval/run_extraction_eval.py`, `eval/run_pipeline_eval.py`,
`eval/run_llm_baseline.py`) can also be run on their own.

The evaluation is built around 15 hand-labeled personas (`eval/personas.json`), each
split into what the persona's message actually *states* vs. *hidden* facts only
revealed through follow-up — so extraction and downstream verdict accuracy are graded
fairly against what a message could plausibly convey on its own.

### Headline results (from a real run — regenerate with `eval/run_all.py` for current numbers)

| Metric | Result |
|---|---|
| Adaptive vs. fixed-form questions needed | **2.87 vs 6.73** (57% fewer questions) |
| Regex extraction F1 | 0.796 (precision 0.934, recall 0.729) |
| LLM extraction F1 | 0.862 (precision 0.978, recall 0.780) |
| LLM-only eligibility baseline, mean accuracy | 0.853 |
| LLM-only baseline, false-LIKELY rate | **0** across all 15 personas |
| LLM-only baseline, run-to-run consistency | 97.3% (2/75 verdicts flipped between identical runs) |
| Hybrid rules engine, run-to-run consistency | **100%**, by construction (see `tests/test_engine.py`) |

### Honest interpretation

The accuracy gap between the LLM-only baseline and the hybrid approach is real but
modest — this project's strongest evidence for the rules-engine design isn't "the LLM
gets it wrong," it's:

- **Determinism** — 100% vs 97.3% consistency is a structural guarantee, not a lucky
  sample.
- **Auditability** — every hybrid verdict comes with a criterion-by-criterion
  breakdown; the LLM-only baseline returns a single word with no inspectable reasoning.
- **Testability** — the rules engine has hand-verified unit tests; "does the LLM reason
  correctly" can't be pinned down the same way.

The LLM-only baseline's zero false-LIKELY rate is a genuinely good result for it,
worth reporting honestly rather than downplaying — the prompt did give it an explicit
"say POTENTIAL if unsure" escape hatch, which likely helped.

## Limitations

- **The 5 schemes in `data/schemes.json` are unverified samples**, written from
  general knowledge, not checked against [myScheme](https://www.myscheme.gov.in/) or
  official sources. Each is marked `"verified": false` and the UI shows a warning on
  every card. Replacing these with real, source-checked criteria is the most
  important next step before treating this as more than a proof of concept.
- The regex fallback extractor doesn't yet handle `is_head_of_family` or
  `is_income_tax_payer` — these fields rely on the LLM path or a direct follow-up
  question.
- The 15 personas were hand-labeled by reasoning through the (sample) scheme criteria,
  not sourced independently — if the schemes change, the personas' expected verdicts
  need re-checking too.
- `graph_agent.py`'s LangGraph orchestration is a linear three-node graph per turn
  (extract → evaluate → ask), not a branching multi-agent graph — an appropriate scope
  for what this task needs, but worth being precise about if asked to describe the
  architecture in more depth.

## Possible extensions

- Verified scheme data across more states and central schemes
- An LLM-assisted drafting step for turning official scheme text into structured
  criteria (human-reviewed before use)
- A harder LLM-only baseline that doesn't offer POTENTIAL as an explicit escape hatch
- Document upload / OCR for automatically confirming "have" vs. "need" documents
- A genuinely branching LangGraph (e.g. parallel category-specific sub-agents for
  education/housing/financial schemes) instead of the current linear per-turn graph