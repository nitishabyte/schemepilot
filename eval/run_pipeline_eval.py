"""Two things measured here:

1. Turn-1 verdict accuracy: run just the raw text through extraction + the engine,
   compare against the true verdict computed from the persona's FULL (stated+hidden)
   profile. This shows how much a single message alone can resolve.
2. Adaptive vs fixed-form questioning: how many follow-up questions does SchemePilot's
   adaptive picker need to fully resolve every scheme, vs a fixed form that always
   asks every field in a set order, regardless of relevance?
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from engine import load_schemes, evaluate_all, POTENTIAL
from user_profile import FIELDS, coerce, rule_based_extract
from questions import next_question
from metrics import verdict_accuracy, markdown_table

PERSONAS = json.loads((Path(__file__).parent / "personas.json").read_text())
SCHEMES = load_schemes()


def true_verdicts(full_profile):
    return {r.scheme_id: r.verdict for r in evaluate_all(SCHEMES, full_profile)}


def turn1_eval():
    rows = []
    for p in PERSONAS:
        raw = rule_based_extract(p["text"]) or {}
        extracted = {k: v for k, v in ((k, coerce(k, v)) for k, v in raw.items()) if v is not None}
        pred = {r.scheme_id: r.verdict for r in evaluate_all(SCHEMES, extracted)}
        truth = true_verdicts({**p["stated"], **p["hidden"]})
        score = verdict_accuracy(pred, truth)
        rows.append((p["id"], score["accuracy"], score["false_likely_count"]))
    accs = [r[1] for r in rows]
    print("=== Turn-1 verdict accuracy (text alone, before any follow-up questions) ===")
    print(markdown_table(rows, ["persona", "accuracy", "false LIKELY"]))
    print(f"\nMean accuracy: {sum(accs)/len(accs):.3f}")
    return rows


def adaptive_turns(persona):
    """Simulate answering whatever SchemePilot's picker asks, using the persona's true values."""
    full = {**persona["stated"], **persona["hidden"]}
    profile = dict(persona["stated"])
    asked = set()
    turns = 0
    while True:
        results = evaluate_all(SCHEMES, profile)
        if not any(r.verdict == POTENTIAL for r in results):
            break
        q = next_question(results, asked)
        if not q:
            break
        asked.add(q["field"])
        if q["field"] in full:
            profile[q["field"]] = full[q["field"]]
        turns += 1
        if turns > len(FIELDS):  # safety net against infinite loops
            break
    return turns


def fixed_form_turns(persona):
    """A fixed form asks every field the initial text didn't already cover, in schema order."""
    return sum(1 for f in FIELDS if f not in persona["stated"])


def questioning_eval():
    rows = []
    for p in PERSONAS:
        a, f = adaptive_turns(p), fixed_form_turns(p)
        rows.append((p["id"], a, f, f - a))
    print("\n=== Follow-up questions needed: adaptive vs fixed-form ===")
    print(markdown_table(rows, ["persona", "adaptive", "fixed-form", "saved"]))
    avg_a = sum(r[1] for r in rows) / len(rows)
    avg_f = sum(r[2] for r in rows) / len(rows)
    print(f"\nMean adaptive: {avg_a:.2f}   Mean fixed-form: {avg_f:.2f}   "
          f"Reduction: {100*(1 - avg_a/avg_f):.0f}%")
    return rows


if __name__ == "__main__":
    t1 = turn1_eval()
    qt = questioning_eval()
    out = Path(__file__).parent / "pipeline_results.json"
    out.write_text(json.dumps({"turn1": t1, "questioning": qt}, indent=2))
    print(f"\nSaved -> {out}")
