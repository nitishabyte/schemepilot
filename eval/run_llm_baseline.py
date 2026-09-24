"""The centerpiece comparison: ask the LLM to decide eligibility directly from scheme
text (no rules engine), and compare it against SchemePilot's hybrid (LLM extracts
fields -> Python rules engine decides). Requires ANTHROPIC_API_KEY; otherwise this
prints instructions and exits without spending any results into the final report.

Also measures run-to-run consistency: ask the SAME question twice and see how often
the LLM-only baseline changes its answer, vs the engine, which is deterministic by
construction (see tests/test_engine.py) and will always be 100% consistent.
"""
import json, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from engine import load_schemes, evaluate_all
from llm import chat
from metrics import verdict_accuracy, markdown_table

PERSONAS = json.loads((Path(__file__).parent / "personas.json").read_text())
DESCRIPTIONS = json.loads((Path(__file__).parent / "scheme_descriptions.json").read_text())
SCHEMES = load_schemes()
VALID = {"LIKELY", "POTENTIAL", "INELIGIBLE"}

SYSTEM = """You are deciding eligibility for a government scheme from a plain-language
profile and a plain-language scheme description. Answer LIKELY if the profile clearly
meets every stated condition, INELIGIBLE if it clearly fails at least one condition,
or POTENTIAL if the profile doesn't give enough information to be sure.
Reply with exactly one word: LIKELY, POTENTIAL, or INELIGIBLE. No other text."""


def profile_text(persona):
    full = {**persona["stated"], **persona["hidden"]}
    return "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in full.items())


def ask_llm(profile_txt, scheme_desc):
    raw = chat(SYSTEM, f"Profile: {profile_txt}\nScheme: {scheme_desc}", max_tokens=60)
    word = re.sub(r"[^A-Z]", "", (raw or "").strip().upper())
    return word if word in VALID else "POTENTIAL"


def true_verdicts(persona):
    full = {**persona["stated"], **persona["hidden"]}
    return {r.scheme_id: r.verdict for r in evaluate_all(SCHEMES, full)}


def hybrid_verdicts():
    """The rules-engine verdicts, given full information -- deterministic by construction."""
    return {p["id"]: true_verdicts(p) for p in PERSONAS}


def main():
    if not (os.getenv("GROQ_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
        print("No API key set. Set ONE of these and re-run:\n"
              "  export GROQ_API_KEY=gsk_...        # free, no billing: console.groq.com/keys\n"
              "  export ANTHROPIC_API_KEY=sk-ant-... # paid\n"
              "  python eval/run_llm_baseline.py\n"
              "Skipping -- the hybrid engine's own numbers still come from run_pipeline_eval.py.")
        return

    acc_rows, consistency_rows = [], []
    total_pairs = flips = 0

    for p in PERSONAS:
        truth = true_verdicts(p)
        ptxt = profile_text(p)
        pred_run1, pred_run2 = {}, {}
        for sid, desc in DESCRIPTIONS.items():
            pred_run1[sid] = ask_llm(ptxt, desc)
            pred_run2[sid] = ask_llm(ptxt, desc)  # same question again
            total_pairs += 1
            if pred_run1[sid] != pred_run2[sid]:
                flips += 1
        score = verdict_accuracy(pred_run1, truth)
        acc_rows.append((p["id"], score["accuracy"], score["false_likely_count"]))
        agree = sum(1 for sid in pred_run1 if pred_run1[sid] == pred_run2[sid])
        consistency_rows.append((p["id"], f"{agree}/{len(pred_run1)}"))

    accs = [r[1] for r in acc_rows]
    print("=== LLM-only baseline: verdict accuracy (run 1) ===")
    print(markdown_table(acc_rows, ["persona", "accuracy", "false LIKELY"]))
    print(f"\nMean accuracy: {sum(accs)/len(accs):.3f}")

    print("\n=== LLM-only baseline: run-1 vs run-2 agreement (same question, asked twice) ===")
    print(markdown_table(consistency_rows, ["persona", "agreeing pairs"]))
    print(f"\nOverall consistency: {100*(1 - flips/total_pairs):.1f}%  "
          f"({flips}/{total_pairs} scheme verdicts flipped between identical runs)")
    print("\nFor comparison, the hybrid rules engine is 100% consistent on every run by "
          "construction (see tests/test_engine.py::test_likely etc.) since it's plain "
          "Python, not a model call.")

    out = Path(__file__).parent / "llm_baseline_results.json"
    out.write_text(json.dumps({
        "accuracy_rows": acc_rows, "mean_accuracy": sum(accs) / len(accs),
        "consistency_pct": 100 * (1 - flips / total_pairs), "flips": flips, "total_pairs": total_pairs,
    }, indent=2))
    print(f"\nSaved -> {out}")


if __name__ == "__main__":
    main()
