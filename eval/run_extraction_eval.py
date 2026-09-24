"""Extraction accuracy: does extract_profile(text) recover the fields the text actually states?

Only `stated` fields are graded — `hidden` fields aren't mentioned in the text, so an
extractor has no way to know them yet (that's what the adaptive follow-up questions are for).
"""
import json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from user_profile import coerce, rule_based_extract
from metrics import field_prf, aggregate_prf, markdown_table

PERSONAS = json.loads((Path(__file__).parent / "personas.json").read_text())


def run(extractor_name, extractor_fn):
    per_persona = []
    for p in PERSONAS:
        raw = extractor_fn(p["text"]) or {}
        extracted = {k: v for k, v in ((k, coerce(k, v)) for k, v in raw.items()) if v is not None}
        score = field_prf(extracted, p["stated"])
        score["id"] = p["id"]
        per_persona.append(score)
    agg = aggregate_prf(per_persona)
    print(f"\n=== Extraction eval: {extractor_name} ===")
    print(json.dumps(agg, indent=2))
    worst = sorted(per_persona, key=lambda r: r["f1"])[:3]
    if worst:
        print("Lowest-scoring personas:")
        for w in worst:
            print(f"  {w['id']}: f1={w['f1']:.2f} missed={w['missed']} wrong={w['wrong_value']} unsupported={w['unsupported']}")
    return agg, per_persona


if __name__ == "__main__":
    results = {}
    agg, _ = run("rule_based (regex fallback)", rule_based_extract)
    results["rule_based"] = agg

    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("GROQ_API_KEY"):
        from llm import llm_extract
        agg_llm, _ = run("LLM extraction", lambda t: llm_extract(t) or {})
        results["llm"] = agg_llm
    else:
        print("\n(No GROQ_API_KEY or ANTHROPIC_API_KEY set — skipping LLM extraction eval, rule-based only.)")

    out = Path(__file__).parent / "extraction_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nSaved -> {out}")